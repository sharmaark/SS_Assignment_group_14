import json
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from .business import BusinessRuleViolation
from .config import get_settings
from .data import WorkforceRepository

settings = get_settings()

repository = WorkforceRepository(
    settings.workforce_database_url
)

correlation_id_context: ContextVar[str] = ContextVar(
    "correlation_id",
    default="",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)

logger = logging.getLogger(
    settings.service_name
)


# ---------------------------------------------------------
# LOGGING
# ---------------------------------------------------------

def log_event(
        event: str,
        **values,
) -> None:

    logger.info(
        json.dumps(
            {
                "service": settings.service_name,
                "event": event,
                "correlation_id":
                    correlation_id_context.get(),
                **values,
            },
            default=str,
        )
    )


# ---------------------------------------------------------
# APPLICATION LIFECYCLE
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialise()
    yield


app = FastAPI(
    title="GeoInspect Workforce Service",
    version="1.2.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------
# CORRELATION ID
# ---------------------------------------------------------

@app.middleware("http")
async def correlation_middleware(
        request: Request,
        call_next,
):

    correlation_id = (
            request.headers.get("X-Correlation-ID")
            or str(uuid4())
    )

    token = correlation_id_context.set(
        correlation_id
    )

    try:

        response = await call_next(
            request
        )

        response.headers[
            "X-Correlation-ID"
        ] = correlation_id

        return response
    finally:

        correlation_id_context.reset(
            token
        )


# ---------------------------------------------------------
# ERROR HANDLING
# ---------------------------------------------------------

@app.exception_handler(BusinessRuleViolation)
async def business_error(
        _: Request,
        exc: BusinessRuleViolation,
):

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": {},
            },
            "correlation_id":
                correlation_id_context.get(),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(
        _: Request,
        exc: RequestValidationError,
):

    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message":
                        "Request validation failed",
                    "details": {
                        "violations":
                            exc.errors(),
                    },
                },
                "correlation_id":
                    correlation_id_context.get(),
            }
        ),
    )


# ---------------------------------------------------------
# REQUEST / RESPONSE MODELS
# ---------------------------------------------------------

class InspectorCreate(BaseModel):

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    skills: list[str] = Field(
        min_length=1
    )

    min_longitude: float = Field(
        ge=-180,
        le=180,
    )

    min_latitude: float = Field(
        ge=-90,
        le=90,
    )

    max_longitude: float = Field(
        ge=-180,
        le=180,
    )

    max_latitude: float = Field(
        ge=-90,
        le=90,
    )

    @model_validator(mode="after")
    def valid_bounds(self):
        if (
                self.min_longitude
                > self.max_longitude
                or self.min_latitude
                > self.max_latitude
        ):
            raise ValueError(
                "service-area minimum bounds "
                "must not exceed maximum bounds"
            )

        return self


class ReservationCreate(BaseModel):
    assignment_id: UUID
    inspector_id: UUID

    required_skill: str = Field(
        min_length=1,
        max_length=50,
    )

    longitude: float = Field(
        ge=-180,
        le=180,
    )

    latitude: float = Field(
        ge=-90,
        le=90,
    )

    slot: datetime

    @field_validator("slot")
    @classmethod
    def slot_must_have_timezone(
            cls,
            value: datetime,
    ) -> datetime:

        if value.tzinfo is None:

            raise ValueError(
                "slot must include a timezone"
            )

        return value


class AvailabilityResponse(BaseModel):
    inspector_id: UUID
    slot: datetime
    available: bool


class EligibleInspectorSearch(BaseModel):

    required_skill: str = Field(
        min_length=1,
        max_length=50,
    )

    longitude: float = Field(
        ge=-180,
        le=180,
    )

    latitude: float = Field(
        ge=-90,
        le=90,
    )

    slot: datetime

    @field_validator("slot")
    @classmethod
    def slot_must_have_timezone(
            cls,
            value: datetime,
    ) -> datetime:

        if value.tzinfo is None:

            raise ValueError(
                "slot must include a timezone"
            )

        return value


# ---------------------------------------------------------
# HEALTH
# ---------------------------------------------------------

@app.get("/health")
def health():
    repository.health()

    return {
        "status": "UP",
        "service": settings.service_name,
    }


# ---------------------------------------------------------
# INSPECTORS
# ---------------------------------------------------------

@app.post(
    "/api/v1/inspectors",
    status_code=201,
)
def create_inspector(
        payload: InspectorCreate,
):

    result = repository.create_inspector(
        payload.model_dump()
    )

    log_event(
        "inspector_created",
        inspector_id=result["id"],
    )

    return result


# ---------------------------------------------------------
# AVAILABILITY
# ---------------------------------------------------------

@app.get(
    "/api/v1/inspectors/{inspector_id}/availability",
    response_model=AvailabilityResponse,
)
def get_inspector_availability(
        inspector_id: UUID,
        slot: datetime,
):
    if slot.tzinfo is None:
        raise BusinessRuleViolation(
            "INVALID_SLOT",
            "slot must include a timezone",
            422,
        )

    result = (
        repository.get_inspector_availability(
            str(inspector_id),
            slot,
        )
    )

    log_event(
        "inspector_availability_checked",
        inspector_id=str(inspector_id),
        slot=slot,
        available=result["available"],
    )

    return result


# ---------------------------------------------------------
# SMART INSPECTOR DISCOVERY
# ---------------------------------------------------------

@app.post(
    "/api/v1/inspectors/search-eligible",
)
def search_eligible_inspectors(
        payload: EligibleInspectorSearch,
):

    items = (
        repository.find_eligible_inspectors(
            required_skill=
            payload.required_skill,
            longitude=
            payload.longitude,
            latitude=
            payload.latitude,
            slot=
            payload.slot,
        )
    )

    log_event(
        "eligible_inspector_search",
        required_skill=
        payload.required_skill,
        longitude=
        payload.longitude,
        latitude=
        payload.latitude,
        slot=
        payload.slot,
        result_count=
        len(items),
    )

    return {
        "items": items,
        "count": len(items),
    }


# ---------------------------------------------------------
# RESERVATIONS
# ---------------------------------------------------------

@app.post(
    "/api/v1/reservations",
    status_code=201,
)
def create_reservation(
        payload: ReservationCreate,
):

    data = payload.model_dump()

    data["assignment_id"] = str(
        data["assignment_id"]
    )

    data["inspector_id"] = str(
        data["inspector_id"]
    )

    result, replayed = (
        repository.reserve(data)
    )

    log_event(
        (
            "reservation_replayed"
            if replayed
            else "reservation_created"
        ),
        reservation_id=
        result["id"],
        assignment_id=
        result["assignment_id"],
    )

    return result


@app.get(
    "/api/v1/reservations"
)
def list_reservations():
    return {
        "items":
            repository.list_reservations()
    }