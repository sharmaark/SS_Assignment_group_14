from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from services.workforce.src.business import BusinessRuleViolation
from services.workforce.src.data import Base, WorkforceRepository


TOTAL_REQUESTS = 20


@pytest.fixture
def repository(tmp_path):
    """
    Creates an isolated file-based SQLite database.

    File-based SQLite is used instead of an in-memory database because
    concurrent worker threads open independent database connections.

    Production uses PostgreSQL; SQLite is used here only for isolated
    automated verification.
    """

    database_path = tmp_path / "workforce_concurrency.db"

    repo = WorkforceRepository(
        f"sqlite:///{database_path}"
    )

    Base.metadata.create_all(repo.engine)

    return repo


@pytest.fixture
def inspector(repository):
    """
    Create one inspector that all concurrent requests will attempt
    to reserve for the exact same slot.
    """

    return repository.create_inspector(
        {
            "name": "Challenge 1 Inspector",
            "skills": ["ELECTRICAL"],
            "min_longitude": 77.50,
            "min_latitude": 12.90,
            "max_longitude": 77.70,
            "max_latitude": 13.10,
        }
    )


def attempt_reservation(
        repository,
        inspector_id,
        slot,
):
    """
    Every concurrent request receives a unique assignment ID.

    This ensures the test exercises inspector-slot contention rather
    than the assignment-id replay/idempotency behavior.
    """

    payload = {
        "assignment_id": str(uuid4()),
        "inspector_id": inspector_id,
        "required_skill": "ELECTRICAL",
        "longitude": 77.5946,
        "latitude": 12.9716,
        "slot": slot,
    }

    try:
        reservation, replayed = repository.reserve(payload)

        return {
            "result": "SUCCESS",
            "reservation_id": reservation["id"],
            "assignment_id": reservation["assignment_id"],
            "replayed": replayed,
        }

    except BusinessRuleViolation as exc:
        return {
            "result": "CONFLICT",
            "code": exc.code,
            "status_code": exc.status_code,
        }


def test_challenge_1_concurrent_reservation_safety(
        repository,
        inspector,
):
    """
    Challenge 1 - Concurrent Reservation Safety

    Twenty independent assignments simultaneously compete for one
    inspector and one exact time slot.

    Expected:
      - exactly 1 successful reservation
      - exactly 19 SLOT_UNAVAILABLE conflicts
      - exactly 1 persisted reservation for the inspector
    """

    slot = (
            datetime.now(timezone.utc)
            + timedelta(days=7)
    ).replace(microsecond=0)

    with ThreadPoolExecutor(
            max_workers=TOTAL_REQUESTS
    ) as executor:

        futures = [
            executor.submit(
                attempt_reservation,
                repository,
                inspector["id"],
                slot,
            )
            for _ in range(TOTAL_REQUESTS)
        ]

        results = [
            future.result()
            for future in as_completed(futures)
        ]

    successes = [
        result
        for result in results
        if result["result"] == "SUCCESS"
    ]

    conflicts = [
        result
        for result in results
        if result["result"] == "CONFLICT"
    ]

    slot_conflicts = [
        result
        for result in conflicts
        if result["code"] == "SLOT_UNAVAILABLE"
    ]

    reservations = repository.list_reservations()

    inspector_reservations = [
        reservation
        for reservation in reservations
        if reservation["inspector_id"] == inspector["id"]
    ]

    # ---------------------------------------------------------
    # Challenge 1 assertions
    # ---------------------------------------------------------

    assert len(results) == TOTAL_REQUESTS

    # Capacity = 1
    assert len(successes) == 1

    # Remaining 19 requests must lose the race.
    assert len(conflicts) == TOTAL_REQUESTS - 1

    # All losing requests must fail specifically because
    # the inspector/slot is already occupied.
    assert len(slot_conflicts) == TOTAL_REQUESTS - 1

    # Only one reservation may exist for this inspector.
    assert len(inspector_reservations) == 1

    # The successful request must represent a newly-created
    # reservation rather than an idempotent replay.
    assert successes[0]["replayed"] is False

    # The persisted reservation must correspond to the
    # reservation returned by the winning request.
    assert (
            inspector_reservations[0]["id"]
            == successes[0]["reservation_id"]
    )