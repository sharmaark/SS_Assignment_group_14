import json
import logging
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .business import BusinessRuleViolation, request_fingerprint, retry_delay
from .clients import DownstreamError, DownstreamTimeout, ServiceClients
from .config import get_settings
from .data import DispatchRepository

settings = get_settings()
repository = DispatchRepository(settings.dispatch_database_url)
clients = ServiceClients(
    settings.work_order_url,
    settings.workforce_url,
    settings.notification_url,
    settings.downstream_timeout_seconds,
)
correlation_id_context: ContextVar[str] = ContextVar("correlation_id", default="")
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(settings.service_name)


def log_event(event: str, **values) -> None:
    logger.info(json.dumps({"service": settings.service_name, "event": event, "correlation_id": correlation_id_context.get(), **values}, default=str))


def error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}, "correlation_id": correlation_id_context.get()}


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialise()
    try:
        yield
    finally:
        repository.engine.dispose()
        repository.lock_engine.dispose()


app = FastAPI(title="GeoInspect Dispatch Service", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    token = correlation_id_context.set(correlation_id)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
    finally:
        correlation_id_context.reset(token)


@app.exception_handler(BusinessRuleViolation)
async def business_error(_: Request, exc: BusinessRuleViolation):
    return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=jsonable_encoder(error_body("VALIDATION_ERROR", "Request validation failed", {"violations": exc.errors()})))


class AssignmentCreate(BaseModel):
    work_order_id: UUID
    inspector_id: UUID


def notify_with_retry(assignment: dict, correlation_id: str) -> str:
    if assignment["notification_status"] == "SENT":
        return "SENT"
    payload = {
        "delivery_key": f"assignment:{assignment['id']}",
        "assignment_id": assignment["id"],
        "work_order_id": assignment["work_order_id"],
        "message": f"Inspection {assignment['work_order_id']} assigned",
    }
    for attempt in range(1, settings.notification_max_attempts + 1):
        try:
            log_event("notification_attempt", assignment_id=assignment["id"], attempt=attempt)
            result = clients.notify(payload, correlation_id)
            if result.get("status") == "SENT":
                repository.set_notification_status(assignment["id"], "SENT")
                return "SENT"
            log_event("notification_delivery_pending", assignment_id=assignment["id"], attempt=attempt)
        except (DownstreamError, DownstreamTimeout) as exc:
            log_event("notification_attempt_failed", assignment_id=assignment["id"], attempt=attempt, reason=str(exc))
        if attempt < settings.notification_max_attempts:
            delay = retry_delay(settings.retry_base_seconds, attempt)
            log_event("notification_retry_scheduled", assignment_id=assignment["id"], delay_seconds=delay)
            time.sleep(delay)
    # Failed/processing attempts must never overwrite a concurrent SENT result.
    return repository.get_assignment(assignment["id"])["notification_status"]


def execute_assignment(idempotency_key: str, assignment: dict, correlation_id: str) -> tuple[int, dict]:
    """Resume durable checkpoints while holding the request's execution lock."""
    assignment_id = assignment["id"]
    if assignment["stage"] not in {"SLOT_RESERVED", "CONFIRMED"}:
        try:
            work_order = clients.claim_work_order(assignment["work_order_id"], assignment_id, correlation_id)
            repository.update_stage(assignment_id, "WORK_ORDER_CLAIMED")
        except DownstreamError as exc:
            if exc.status_code >= 500:
                return 503, error_body("WORK_ORDER_UNAVAILABLE", "Work Order outcome is unknown; retry with the same key")
            body = exc.body if "error" in exc.body else error_body("WORK_ORDER_REJECTED", str(exc))
            repository.complete(idempotency_key, assignment_id, exc.status_code, body, "REJECTED")
            return exc.status_code, body
        except DownstreamTimeout:
            return 503, error_body("WORK_ORDER_UNAVAILABLE", "Work Order service did not respond; retry with the same key")

        reservation_payload = {
            "assignment_id": assignment_id,
            "inspector_id": assignment["inspector_id"],
            "required_skill": work_order["required_skill"],
            "longitude": work_order["longitude"],
            "latitude": work_order["latitude"],
            "slot": work_order["slot"],
        }
        try:
            reservation = clients.reserve(reservation_payload, correlation_id)
            repository.update_stage(assignment_id, "SLOT_RESERVED", reservation["id"])
        except DownstreamError as exc:
            if exc.status_code >= 500:
                return 503, error_body("WORKFORCE_UNAVAILABLE", "Workforce outcome is unknown; retry with the same key")
            try:
                clients.release_work_order(assignment["work_order_id"], assignment_id, correlation_id)
            except (DownstreamError, DownstreamTimeout) as release_error:
                log_event("claim_release_failed", assignment_id=assignment_id, reason=str(release_error))
                return 503, error_body("CLAIM_RELEASE_UNRESOLVED", "Claim release is unresolved; retry with the same key")
            body = exc.body if "error" in exc.body else error_body("RESERVATION_REJECTED", str(exc))
            repository.complete(idempotency_key, assignment_id, exc.status_code, body, "REJECTED")
            return exc.status_code, body
        except DownstreamTimeout:
            return 503, error_body("WORKFORCE_UNAVAILABLE", "Workforce outcome is unknown; retry with the same key")

    if assignment["stage"] != "CONFIRMED":
        try:
            clients.confirm_work_order(assignment["work_order_id"], assignment_id, correlation_id)
        except (DownstreamError, DownstreamTimeout):
            return 503, error_body("CONFIRMATION_UNRESOLVED", "Confirmation outcome is unresolved; retry with the same key")
        repository.confirm_assignment(assignment_id)
    assignment = repository.get_assignment(assignment_id)
    notification_status = notify_with_retry(assignment, correlation_id)
    assignment = repository.get_assignment(assignment_id)
    body = {**assignment, "notification_status": notification_status}
    body = json.loads(json.dumps(body, default=str))
    repository.complete(idempotency_key, assignment_id, 201, body)
    log_event("assignment_confirmed", assignment_id=assignment_id, notification_status=notification_status)
    return 201, body


@app.get("/health")
def health():
    repository.health()
    return {"status": "UP", "service": settings.service_name}


@app.post("/api/v1/assignments", status_code=201, responses={
    202: {"description": "An identical request is still being processed; retry with the same key"},
    404: {"description": "Work order or inspector does not exist"},
    409: {"description": "Assignment rejected or idempotency key reused with another payload"},
    503: {"description": "A downstream outcome is unresolved; retry with the same key"},
})
def create_assignment(payload: AssignmentCreate, idempotency_key: str = Header(min_length=1, max_length=100, alias="Idempotency-Key")):
    serialised = payload.model_dump(mode="json")
    fingerprint = request_fingerprint(serialised)
    assignment, _, stored = repository.claim_request(idempotency_key, fingerprint, serialised)
    if stored:
        log_event("idempotency_replay", key=idempotency_key, assignment_id=assignment["id"])
        return JSONResponse(status_code=stored[0], content=stored[1])
    deadline = time.monotonic() + settings.idempotency_wait_seconds
    while True:
        with repository.execution_lock(idempotency_key) as acquired:
            if acquired:
                # Another worker may have completed while we acquired the lock.
                stored = repository.get_idempotency_result(idempotency_key)
                if stored:
                    return JSONResponse(status_code=stored[0], content=stored[1])
                assignment = repository.get_assignment(assignment["id"])
                status_code, body = execute_assignment(idempotency_key, assignment, correlation_id_context.get())
                return JSONResponse(status_code=status_code, content=body)
            stored = repository.get_idempotency_result(idempotency_key)
            if stored:
                log_event("concurrent_idempotency_replay", key=idempotency_key, assignment_id=assignment["id"])
                return JSONResponse(status_code=stored[0], content=stored[1])
        if time.monotonic() >= deadline:
            return JSONResponse(status_code=202, content={"id": assignment["id"], "status": "PENDING"})
        time.sleep(0.05)


@app.get("/api/v1/assignments/{assignment_id}", responses={404: {"description": "Assignment not found"}})
def get_assignment(assignment_id: UUID):
    item = repository.get_assignment(str(assignment_id))
    if not item:
        return JSONResponse(status_code=404, content=error_body("ASSIGNMENT_NOT_FOUND", "Assignment not found"))
    return item


@app.get("/api/v1/assignments")
def list_assignments():
    return {"items": repository.list_assignments()}


@app.post("/api/v1/assignments/{assignment_id}/retry-notification", responses={
    404: {"description": "Assignment not found"},
    409: {"description": "Only a confirmed assignment can send notifications"},
})
def retry_notification(assignment_id: UUID):
    item = repository.get_assignment(str(assignment_id))
    if not item:
        return JSONResponse(status_code=404, content=error_body("ASSIGNMENT_NOT_FOUND", "Assignment not found"))
    if item["status"] != "CONFIRMED":
        return JSONResponse(status_code=409, content=error_body("ASSIGNMENT_NOT_CONFIRMED", "Only confirmed assignments can send notifications"))
    status = notify_with_retry(item, correlation_id_context.get())
    return {"assignment_id": str(assignment_id), "notification_status": status}
