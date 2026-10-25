from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, String, create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import NullPool

from .business import ensure_matching_fingerprint


class Base(DeclarativeBase):
    pass


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    work_order_id: Mapped[str] = mapped_column(String(36), index=True)
    inspector_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    stage: Mapped[str] = mapped_column(String(30), default="CREATED")
    reservation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notification_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    assignment_id: Mapped[str] = mapped_column(String(36), index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def assignment_dict(item: Assignment) -> dict:
    return {
        "id": item.id,
        "work_order_id": item.work_order_id,
        "inspector_id": item.inspector_id,
        "status": item.status,
        "stage": item.stage,
        "reservation_id": item.reservation_id,
        "notification_status": item.notification_status,
        "created_at": item.created_at,
    }


class DispatchRepository:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, pool_pre_ping=True)
        # Lock holders must not exhaust the pool used to persist checkpoints.
        self.lock_engine = create_engine(database_url, poolclass=NullPool)

    def initialise(self) -> None:
        Base.metadata.create_all(self.engine)

    def health(self) -> None:
        with Session(self.engine) as session:
            session.execute(select(1))

    @contextmanager
    def execution_lock(self, key: str):
        """One orchestrator per key, across workers; released on rollback or disconnect.

        Keep this transaction separate from stage/result writes so checkpoints
        remain durable if a downstream response is lost or the worker exits.
        """
        lock_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)
        with self.lock_engine.begin() as connection:
            acquired = connection.scalar(
                text("SELECT pg_try_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id}
            )
            yield acquired

    def claim_request(self, key: str, fingerprint: str, payload: dict) -> tuple[dict, bool, tuple[int, dict] | None]:
        assignment = Assignment(
            id=str(uuid4()),
            work_order_id=payload["work_order_id"],
            inspector_id=payload["inspector_id"],
            status="PENDING",
            stage="CREATED",
            notification_status="PENDING",
            created_at=datetime.now(timezone.utc),
        )
        record = IdempotencyRecord(
            key=key,
            fingerprint=fingerprint,
            assignment_id=assignment.id,
            created_at=datetime.now(timezone.utc),
        )
        with Session(self.engine) as session:
            session.add_all([assignment, record])
            try:
                session.commit()
                session.refresh(assignment)
                return assignment_dict(assignment), True, None
            except IntegrityError:
                session.rollback()
                existing = session.get(IdempotencyRecord, key)
                ensure_matching_fingerprint(existing.fingerprint, fingerprint)
                assignment = session.get(Assignment, existing.assignment_id)
                stored = None
                if existing.status_code is not None:
                    stored = (existing.status_code, existing.response_body)
                return assignment_dict(assignment), False, stored

    def get_idempotency_result(self, key: str) -> tuple[int, dict] | None:
        with Session(self.engine) as session:
            item = session.get(IdempotencyRecord, key)
            if item and item.status_code is not None:
                return item.status_code, item.response_body
            return None

    def update_stage(self, assignment_id: str, stage: str, reservation_id: str | None = None) -> None:
        with Session(self.engine) as session:
            item = session.get(Assignment, assignment_id)
            item.stage = stage
            if reservation_id:
                item.reservation_id = reservation_id
            session.commit()

    def confirm_assignment(self, assignment_id: str) -> None:
        with Session(self.engine) as session:
            item = session.get(Assignment, assignment_id)
            item.status = "CONFIRMED"
            item.stage = "CONFIRMED"
            session.commit()

    def set_notification_status(self, assignment_id: str, status: str) -> None:
        with Session(self.engine) as session:
            item = session.get(Assignment, assignment_id)
            item.notification_status = status
            session.commit()

    def complete(self, key: str, assignment_id: str, status_code: int, response_body: dict, assignment_status: str | None = None) -> None:
        with Session(self.engine) as session:
            record = session.get(IdempotencyRecord, key)
            assignment = session.get(Assignment, assignment_id)
            record.status_code = status_code
            record.response_body = response_body
            if assignment_status:
                assignment.status = assignment_status
                assignment.stage = assignment_status
            session.commit()

    def get_assignment(self, assignment_id: str) -> dict | None:
        with Session(self.engine) as session:
            item = session.get(Assignment, assignment_id)
            return assignment_dict(item) if item else None

    def list_assignments(self) -> list[dict]:
        with Session(self.engine) as session:
            return [assignment_dict(item) for item in session.scalars(select(Assignment)).all()]
