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
            tmp_path
            / "workforce_lifecycle.db"
    )

    repo = WorkforceRepository(
        f"sqlite:///{database_path}"
    )

    Base.metadata.create_all(
        repo.engine
    )

    return repo


def test_discovery_reservation_lifecycle(
        repository,
):
    """
    Verify the complete Workforce lifecycle:

    1. Inspector is discoverable while eligible and free.
    2. Availability reports True.
    3. Reservation succeeds.
    4. Availability reports False.
    5. Reserved inspector is excluded from discovery
       for the same slot.
    """

    inspector = (
        repository.create_inspector(
            {
                "name":
                    "Lifecycle Inspector",

                "skills":
                    ["ELECTRICAL"],

                "min_longitude":
                    77.50,

                "min_latitude":
                    12.90,

                "max_longitude":
                    77.70,

                "max_latitude":
                    13.10,
            }
        )
    )

    slot = (
            datetime.now(timezone.utc)
            + timedelta(days=10)
    ).replace(microsecond=0)

    # -----------------------------------------------------
    # Discovery before reservation
    # -----------------------------------------------------

    discovery_before = (
        repository.find_eligible_inspectors(
            required_skill="ELECTRICAL",
            longitude=77.5946,
            latitude=12.9716,
            slot=slot,
        )
    )

    before_ids = {
        item["id"]
        for item in discovery_before
    }

    assert inspector["id"] in before_ids

    # -----------------------------------------------------
    # Availability before reservation
    # -----------------------------------------------------

    availability_before = (
        repository.get_inspector_availability(
            inspector["id"],
            slot,
        )
    )

    assert (
            availability_before["available"]
            is True
    )

    # -----------------------------------------------------
    # Reservation
    # -----------------------------------------------------

    reservation, replayed = (
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
    )

    assert replayed is False

    assert (
            reservation["inspector_id"]
            == inspector["id"]
    )

    # -----------------------------------------------------
    # Availability after reservation
    # -----------------------------------------------------

    availability_after = (
        repository.get_inspector_availability(
            inspector["id"],
            slot,
        )
    )

    assert (
            availability_after["available"]
            is False
    )

    # -----------------------------------------------------
    # Discovery after reservation
    # -----------------------------------------------------

    discovery_after = (
        repository.find_eligible_inspectors(
            required_skill="ELECTRICAL",
            longitude=77.5946,
            latitude=12.9716,
            slot=slot,
        )
    )

    after_ids = {
        item["id"]
        for item in discovery_after
    }

    assert (
            inspector["id"]
            not in after_ids
    )