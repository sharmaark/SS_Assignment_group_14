import json
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from .business import BusinessRuleViolation, ensure_photo_allowed
from .config import get_settings
from .data import WorkOrderRepository

settings = get_settings()
repository = WorkOrderRepository(settings.work_order_mongodb_url, settings.work_order_mongodb_database)
correlation_id_context: ContextVar[str] = ContextVar("correlation_id", default="")
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(settings.service_name)


def log_event(event: str, **values) -> None:
    logger.info(
        json.dumps(
            {
                "service": settings.service_name,
                "event": event,
                "correlation_id": correlation_id_context.get(),
                **values,
            },
            default=str,
        )
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialise()
    yield


app = FastAPI(title="GeoInspect Work Order Service", version="1.0.0", lifespan=lifespan)


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
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": exc.code, "message": exc.message, "details": {}},
            "correlation_id": correlation_id_context.get(),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({
            "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": {"violations": exc.errors()}},
            "correlation_id": correlation_id_context.get(),
        }),
    )


class WorkOrderCreate(BaseModel):
    asset_id: str = Field(min_length=1, max_length=100)
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    required_skill: str = Field(min_length=1, max_length=50)
    slot: datetime

    @field_validator("slot")
    @classmethod
    def slot_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("slot must include a timezone")
        return value


class AssignmentOperation(BaseModel):
    assignment_id: UUID


@app.get("/health")
def health():
    repository.health()
    return {"status": "UP", "service": settings.service_name}


@app.post("/api/v1/work-orders", status_code=201)
def create_work_order(payload: WorkOrderCreate):
    result = repository.create(payload.model_dump(mode="json"))
    log_event("work_order_created", work_order_id=result["id"])
    return result


@app.get("/api/v1/work-orders/{work_order_id}")
def get_work_order(work_order_id: UUID):
    result = repository.get(str(work_order_id))
    if not result:
        raise BusinessRuleViolation("WORK_ORDER_NOT_FOUND", "Work order not found", 404)
    return result


@app.post("/api/v1/work-orders/{work_order_id}/claim")
def claim_work_order(work_order_id: UUID, payload: AssignmentOperation):
    result = repository.claim(str(work_order_id), str(payload.assignment_id))
    log_event("work_order_claimed", work_order_id=work_order_id, assignment_id=payload.assignment_id)
    return result


@app.post("/api/v1/work-orders/{work_order_id}/confirm")
def confirm_work_order(work_order_id: UUID, payload: AssignmentOperation):
    result = repository.confirm(str(work_order_id), str(payload.assignment_id))
    log_event("work_order_confirmed", work_order_id=work_order_id, assignment_id=payload.assignment_id)
    return result


@app.post("/api/v1/work-orders/{work_order_id}/release-claim")
def release_claim(work_order_id: UUID, payload: AssignmentOperation):
    result = repository.release_claim(str(work_order_id), str(payload.assignment_id))
    log_event("work_order_claim_released", work_order_id=work_order_id, assignment_id=payload.assignment_id)
    return result


@app.post("/api/v1/work-orders/{work_order_id}/photos", status_code=201)
async def upload_photo(work_order_id: UUID, photo: UploadFile = File(...)):
    work_order = repository.get(str(work_order_id))
    if not work_order:
        raise BusinessRuleViolation("WORK_ORDER_NOT_FOUND", "Work order not found", 404)
    content = await photo.read(settings.max_photo_bytes + 1)
    ensure_photo_allowed(
        work_order["state"], photo.content_type, len(content), settings.max_photo_bytes
    )
    result = repository.add_photo(
        str(work_order_id), photo.filename or "inspection-photo", photo.content_type or "", content
    )
    log_event("inspection_photo_uploaded", work_order_id=work_order_id, photo_id=result["id"])
    return result


@app.get("/api/v1/work-orders/{work_order_id}/photos")
def list_photos(work_order_id: UUID):
    if not repository.get(str(work_order_id)):
        raise BusinessRuleViolation("WORK_ORDER_NOT_FOUND", "Work order not found", 404)
    return {"items": repository.list_photos(str(work_order_id))}


@app.get("/api/v1/photos/{photo_id}")
def download_photo(photo_id: str):
    stream = repository.open_photo(photo_id)
    return StreamingResponse(
        stream,
        media_type=stream.metadata.get("content_type", "application/octet-stream"),
        headers={"Content-Disposition": f'inline; filename="{stream.filename}"'},
    )
