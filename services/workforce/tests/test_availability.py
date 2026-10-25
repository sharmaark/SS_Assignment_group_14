from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from services.workforce.src.business import BusinessRuleViolation
from services.workforce.src.data import (
    Base,
    Inspector,
    Reservation,
    WorkforceRepository,
)


@pytest.fixture
def repository(tmp_path):
    database_path = tmp_path / "workforce_test.db"

    repo = WorkforceRepository(
        f"sqlite:///{database_path}"
    )

    Base.metadata.create_all(repo.engine)

    return repo


@pytest.fixture
def inspector(repository):
    return repository.create_inspector(
        {
            "name": "Inspector A",
            "skills": ["ELECTRICAL"],
            "min_longitude": 77.50,
            "min_latitude": 12.90,
            "max_longitude": 77.70,
            "max_latitude": 13.10,
        }
    )


def test_inspector_is_available_for_free_slot(
        repository,
        inspector,
):
    slot = datetime.now(timezone.utc) + timedelta(days=1)

    result = repository.get_inspector_availability(
        inspector["id"],
        slot,
    )

    assert result["inspector_id"] == inspector["id"]
    assert result["slot"] == slot
    assert result["available"] is True


def test_inspector_is_unavailable_for_reserved_slot(
        repository,
        inspector,
):
    slot = datetime.now(timezone.utc) + timedelta(days=1)

    repository.reserve(
        {
            "assignment_id": str(uuid4()),
            "inspector_id": inspector["id"],
            "required_skill": "ELECTRICAL",
            "longitude": 77.5946,
            "latitude": 12.9716,
            "slot": slot,
        }
    )

    result = repository.get_inspector_availability(
        inspector["id"],
        slot,
    )

    assert result["available"] is False


def test_same_inspector_is_available_for_different_slot(
        repository,
        inspector,
):
    reserved_slot = (
            datetime.now(timezone.utc)
            + timedelta(days=1)
    )

    another_slot = (
            reserved_slot
            + timedelta(hours=1)
    )

    repository.reserve(
        {
            "assignment_id": str(uuid4()),
            "inspector_id": inspector["id"],
            "required_skill": "ELECTRICAL",
            "longitude": 77.5946,
            "latitude": 12.9716,
            "slot": reserved_slot,
        }
    )

    result = repository.get_inspector_availability(
        inspector["id"],
        another_slot,
    )

    assert result["available"] is True


def test_unknown_inspector_returns_not_found(
        repository,
):
    slot = datetime.now(timezone.utc) + timedelta(days=1)

    with pytest.raises(BusinessRuleViolation) as error:
        repository.get_inspector_availability(
            str(uuid4()),
            slot,
        )

    assert error.value.code == "INSPECTOR_NOT_FOUND"
    assert error.value.status_code == 404