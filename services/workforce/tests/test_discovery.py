from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from services.workforce.src.data import (
    Base,
    WorkforceRepository,
)


@pytest.fixture
def repository(tmp_path):

    database_path = (
            tmp_path / "workforce_discovery.db"
    )

    repo = WorkforceRepository(
        f"sqlite:///{database_path}"
    )

    Base.metadata.create_all(
        repo.engine
    )

    return repo


def create_inspector(
        repository,
        name,
        skills,
        min_longitude=77.50,
        min_latitude=12.90,
        max_longitude=77.70,
        max_latitude=13.10,
):

    return repository.create_inspector(
        {
            "name": name,
            "skills": skills,
            "min_longitude":
                min_longitude,
            "min_latitude":
                min_latitude,
            "max_longitude":
                max_longitude,
            "max_latitude":
                max_latitude,
        }
    )


def test_matching_inspector_is_returned(
        repository,
):

    inspector = create_inspector(
        repository,
        "Inspector A",
        ["ELECTRICAL"],
    )

    slot = (
            datetime.now(timezone.utc)
            + timedelta(days=1)
    )

    result = (
        repository.find_eligible_inspectors(
            required_skill="ELECTRICAL",
            longitude=77.5946,
            latitude=12.9716,
            slot=slot,
        )
    )

    assert len(result) == 1

    assert (
            result[0]["id"]
            == inspector["id"]
    )


def test_wrong_skill_is_excluded(
        repository,
):

    create_inspector(
        repository,
        "Inspector B",
        ["PLUMBING"],
    )

    slot = (
            datetime.now(timezone.utc)
            + timedelta(days=1)
    )

    result = (
        repository.find_eligible_inspectors(
            required_skill="ELECTRICAL",
            longitude=77.5946,
            latitude=12.9716,
            slot=slot,
        )
    )

    assert result == []


def test_outside_service_area_is_excluded(
        repository,
):

    create_inspector(
        repository,
        "Inspector C",
        ["ELECTRICAL"],
        min_longitude=78.00,
        min_latitude=13.50,
        max_longitude=78.20,
        max_latitude=13.70,
    )

    slot = (
            datetime.now(timezone.utc)
            + timedelta(days=1)
    )

    result = (
        repository.find_eligible_inspectors(
            required_skill="ELECTRICAL",
            longitude=77.5946,
            latitude=12.9716,
            slot=slot,
        )
    )

    assert result == []


def test_service_area_boundary_is_included(
        repository,
):

    inspector = create_inspector(
        repository,
        "Boundary Inspector",
        ["ELECTRICAL"],
    )

    slot = (
            datetime.now(timezone.utc)
            + timedelta(days=1)
    )

    result = (
        repository.find_eligible_inspectors(
            required_skill="ELECTRICAL",
            longitude=77.50,
            latitude=12.90,
            slot=slot,
        )
    )

    ids = [
        item["id"]
        for item in result
    ]

    assert inspector["id"] in ids


def test_reserved_inspector_is_excluded(
        repository,
):

    inspector = create_inspector(
        repository,
        "Inspector D",
        ["ELECTRICAL"],
    )

    slot = (
            datetime.now(timezone.utc)
            + timedelta(days=1)
    )

    repository.reserve(
        {
            "assignment_id":
                str(uuid4()),
            "inspector_id":
                inspector["id"],
            "required_skill":
                "ELECTRICAL",
            "longitude":
                77.5946,
            "latitude":
                12.9716,
            "slot":
                slot,
        }
    )

    result = (
        repository.find_eligible_inspectors(
            required_skill="ELECTRICAL",
            longitude=77.5946,
            latitude=12.9716,
            slot=slot,
        )
    )

    assert result == []


def test_reserved_inspector_is_available_for_different_slot(
        repository,
):

    inspector = create_inspector(
        repository,
        "Inspector E",
        ["ELECTRICAL"],
    )

    reserved_slot = (
            datetime.now(timezone.utc)
            + timedelta(days=1)
    )

    search_slot = (
            reserved_slot
            + timedelta(hours=1)
    )

    repository.reserve(
        {
            "assignment_id":
                str(uuid4()),
            "inspector_id":
                inspector["id"],
            "required_skill":
                "ELECTRICAL",
            "longitude":
                77.5946,
            "latitude":
                12.9716,
            "slot":
                reserved_slot,
        }
    )

    result = (
        repository.find_eligible_inspectors(
            required_skill="ELECTRICAL",
            longitude=77.5946,
            latitude=12.9716,
            slot=search_slot,
        )
    )

    ids = [
        item["id"]
        for item in result
    ]

    assert inspector["id"] in ids


def test_multiple_eligible_inspectors_are_returned(
        repository,
):

    inspector_a = create_inspector(
        repository,
        "Inspector A",
        ["ELECTRICAL"],
    )

    inspector_b = create_inspector(
        repository,
        "Inspector B",
        [
            "ELECTRICAL",
            "PLUMBING",
        ],
    )

    slot = (
            datetime.now(timezone.utc)
            + timedelta(days=1)
    )

    result = (
        repository.find_eligible_inspectors(
            required_skill="ELECTRICAL",
            longitude=77.5946,
            latitude=12.9716,
            slot=slot,
        )
    )

    ids = {
        item["id"]
        for item in result
    }

    assert inspector_a["id"] in ids
    assert inspector_b["id"] in ids
    assert len(result) == 2


def test_no_matching_inspector_returns_empty_list(
        repository,
):

    create_inspector(
        repository,
        "Plumbing Inspector",
        ["PLUMBING"],
    )

    slot = (
            datetime.now(timezone.utc)
            + timedelta(days=1)
    )

    result = (
        repository.find_eligible_inspectors(
            required_skill="ELECTRICAL",
            longitude=77.5946,
            latitude=12.9716,
            slot=slot,
        )
    )

    assert result == []