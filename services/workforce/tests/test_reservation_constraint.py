from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.workforce.src.data import Base, Reservation


def test_br3_database_rejects_double_booking_for_same_inspector_slot():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    slot = datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add(
            Reservation(
                id="r1",
                inspector_id="inspector-1",
                assignment_id="assignment-1",
                slot=slot,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
        session.add(
            Reservation(
                id="r2",
                inspector_id="inspector-1",
                assignment_id="assignment-2",
                slot=slot,
                created_at=datetime.now(timezone.utc),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
