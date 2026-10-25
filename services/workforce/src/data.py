from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, String, UniqueConstraint, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .business import BusinessRuleViolation, ensure_eligible


class Base(DeclarativeBase):
    pass


class Inspector(Base):
    __tablename__ = "inspectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    skills: Mapped[list[str]] = mapped_column(JSON)
    min_longitude: Mapped[float] = mapped_column(Float)
    min_latitude: Mapped[float] = mapped_column(Float)
    max_longitude: Mapped[float] = mapped_column(Float)
    max_latitude: Mapped[float] = mapped_column(Float)


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        UniqueConstraint("inspector_id", "slot", name="uq_inspector_slot"),
        UniqueConstraint("assignment_id", name="uq_reservation_assignment"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    inspector_id: Mapped[str] = mapped_column(String(36), index=True)
    assignment_id: Mapped[str] = mapped_column(String(36), index=True)
    slot: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def inspector_dict(item: Inspector) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "skills": item.skills,
        "service_area": {
            "min_longitude": item.min_longitude,
            "min_latitude": item.min_latitude,
            "max_longitude": item.max_longitude,
            "max_latitude": item.max_latitude,
        },
    }


def reservation_dict(item: Reservation) -> dict:
    return {
        "id": item.id,
        "inspector_id": item.inspector_id,
        "assignment_id": item.assignment_id,
        "slot": item.slot,
        "state": "RESERVED",
        "created_at": item.created_at,
    }


class WorkforceRepository:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, pool_pre_ping=True)

    def initialise(self) -> None:
        Base.metadata.create_all(self.engine)

    def health(self) -> None:
        with Session(self.engine) as session:
            session.execute(select(1))

    def create_inspector(self, payload: dict) -> dict:
        item = Inspector(id=str(uuid4()), **payload)
        with Session(self.engine) as session:
            session.add(item)
            session.commit()
            session.refresh(item)
            return inspector_dict(item)

    def get_inspector(self, inspector_id: str) -> Inspector | None:
        with Session(self.engine) as session:
            return session.get(Inspector, inspector_id)

    def reserve(self, payload: dict) -> tuple[dict, bool]:
        with Session(self.engine) as session:
            existing = session.scalar(
                select(Reservation).where(Reservation.assignment_id == payload["assignment_id"])
            )
            if existing:
                return reservation_dict(existing), True

            inspector = session.get(Inspector, payload["inspector_id"])
            if not inspector:
                raise BusinessRuleViolation("INSPECTOR_NOT_FOUND", "Inspector not found", 404)
            flattened = {
                "skills": inspector.skills,
                "min_longitude": inspector.min_longitude,
                "min_latitude": inspector.min_latitude,
                "max_longitude": inspector.max_longitude,
                "max_latitude": inspector.max_latitude,
            }
            ensure_eligible(
                flattened,
                payload["required_skill"],
                payload["longitude"],
                payload["latitude"],
            )

            reservation = Reservation(
                id=str(uuid4()),
                inspector_id=payload["inspector_id"],
                assignment_id=payload["assignment_id"],
                slot=payload["slot"],
                created_at=datetime.now(timezone.utc),
            )
            session.add(reservation)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = session.scalar(
                    select(Reservation).where(
                        Reservation.assignment_id == payload["assignment_id"]
                    )
                )
                if existing:
                    return reservation_dict(existing), True
                raise BusinessRuleViolation(
                    "SLOT_UNAVAILABLE", "Inspector is already reserved for this slot"
                )
            session.refresh(reservation)
            return reservation_dict(reservation), False

    def list_reservations(self) -> list[dict]:
        with Session(self.engine) as session:
            return [reservation_dict(item) for item in session.scalars(select(Reservation)).all()]
