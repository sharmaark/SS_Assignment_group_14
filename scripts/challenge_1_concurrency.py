import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx


# Allow direct execution:
# python scripts/challenge_1_concurrency.py
REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


WORKFORCE_URL = "http://127.0.0.1:8002"
TOTAL_REQUESTS = 20


def request(method: str, url: str, **kwargs):
    return httpx.request(
        method,
        url,
        timeout=20,
        **kwargs,
    )


def require(response, expected_status: int):
    if response.status_code != expected_status:
        raise RuntimeError(
            f"Expected HTTP {expected_status}, "
            f"got {response.status_code}: "
            f"{response.text}"
        )

    return response.json()


def wait_for_workforce():
    response = request(
        "GET",
        f"{WORKFORCE_URL}/health",
    )

    require(response, 200)


def create_inspector():
    payload = {
        "name": "Challenge 1 Inspector",
        "skills": ["ELECTRICAL"],
        "min_longitude": 77.50,
        "min_latitude": 12.90,
        "max_longitude": 77.70,
        "max_latitude": 13.10,
    }

    response = request(
        "POST",
        f"{WORKFORCE_URL}/api/v1/inspectors",
        json=payload,
    )

    return require(response, 201)


def attempt_reservation(
        inspector_id: str,
        slot: datetime,
):
    """
    Every request uses a different assignment ID.

    This ensures we test contention on the same
    inspector + slot rather than assignment replay.
    """

    payload = {
        "assignment_id": str(uuid4()),
        "inspector_id": inspector_id,
        "required_skill": "ELECTRICAL",
        "longitude": 77.5946,
        "latitude": 12.9716,
        "slot": slot.isoformat(),
    }

    response = request(
        "POST",
        f"{WORKFORCE_URL}/api/v1/reservations",
        json=payload,
    )

    try:
        body = response.json()
    except Exception:
        body = {
            "raw_response": response.text
        }

    return {
        "status_code": response.status_code,
        "body": body,
    }


def main():

    print()
    print("=" * 68)
    print(
        "CHALLENGE 1 - CONCURRENT RESERVATION SAFETY"
    )
    print("=" * 68)

    # -----------------------------------------------------
    # Verify Workforce is running
    # -----------------------------------------------------

    wait_for_workforce()

    print()
    print("Workforce service : UP")

    # -----------------------------------------------------
    # Create one inspector
    # -----------------------------------------------------

    inspector = create_inspector()

    inspector_id = inspector["id"]

    slot = (
            datetime.now(timezone.utc)
            + timedelta(days=8)
    ).replace(microsecond=0)

    print(
        f"Inspector ID      : {inspector_id}"
    )

    print(
        f"Requested slot    : {slot.isoformat()}"
    )

    print(
        f"Concurrent requests: {TOTAL_REQUESTS}"
    )

    print(
        "Slot capacity     : 1"
    )

    print()
    print(
        "Sending 20 concurrent reservation requests..."
    )
    print()

    # -----------------------------------------------------
    # Send 20 simultaneous requests
    # -----------------------------------------------------

    with ThreadPoolExecutor(
            max_workers=TOTAL_REQUESTS
    ) as pool:

        results = list(
            pool.map(
                lambda _:
                attempt_reservation(
                    inspector_id,
                    slot,
                ),
                range(TOTAL_REQUESTS),
            )
        )

    # -----------------------------------------------------
    # Analyse responses
    # -----------------------------------------------------

    successes = [
        item
        for item in results
        if item["status_code"] == 201
    ]

    conflicts = [
        item
        for item in results
        if item["status_code"] == 409
    ]

    slot_conflicts = [
        item
        for item in conflicts
        if (
                item["body"]
                .get("error", {})
                .get("code")
                == "SLOT_UNAVAILABLE"
        )
    ]

    # -----------------------------------------------------
    # Verify final database-visible state through API
    # -----------------------------------------------------

    reservation_response = request(
        "GET",
        f"{WORKFORCE_URL}/api/v1/reservations",
    )

    reservations = require(
        reservation_response,
        200,
    )["items"]

    matching = [
        item
        for item in reservations
        if (
                item["inspector_id"]
                == inspector_id
                and item["slot"].startswith(
            slot.date().isoformat()
        )
        )
    ]

    # -----------------------------------------------------
    # Challenge assertions
    # -----------------------------------------------------

    assert len(successes) == 1, (
        f"Expected 1 successful reservation, "
        f"got {len(successes)}"
    )

    assert len(conflicts) == 19, (
        f"Expected 19 conflicts, "
        f"got {len(conflicts)}"
    )

    assert len(slot_conflicts) == 19, (
        f"Expected 19 SLOT_UNAVAILABLE responses, "
        f"got {len(slot_conflicts)}"
    )

    assert len(matching) == 1, (
        f"Expected exactly 1 final reservation, "
        f"got {len(matching)}"
    )

    # -----------------------------------------------------
    # Clean evidence output
    # -----------------------------------------------------

    print("-" * 68)

    print(
        f"Successful requests : {len(successes)}"
    )

    print(
        f"Slot conflicts      : {len(slot_conflicts)}"
    )

    print(
        f"Final reservations  : {len(matching)}"
    )

    print("-" * 68)

    print()
    print(
        "Invariant:"
    )

    print(
        "At most one reservation may exist "
        "for the same (inspector_id, slot)."
    )

    print()

    print(
        "RESULT: PASS"
    )

    print(
        "Exactly one concurrent reservation succeeded."
    )

    print(
        "All competing requests were rejected "
        "with SLOT_UNAVAILABLE."
    )

    print()

    # Also retain structured evidence.
    output = {
        "timestamp_utc":
            datetime.now(timezone.utc).isoformat(),

        "claim":
            "20 concurrent requests for capacity 1 "
            "produce exactly 1 success",

        "inspector_id":
            inspector_id,

        "slot":
            slot.isoformat(),

        "total_requests":
            TOTAL_REQUESTS,

        "successes":
            len(successes),

        "conflicts":
            len(conflicts),

        "slot_unavailable":
            len(slot_conflicts),

        "final_reservations":
            matching,
    }

    print(
        json.dumps(
            output,
            indent=2,
            default=str,
        )
    )

    print()
    print("=" * 68)


if __name__ == "__main__":
    main()