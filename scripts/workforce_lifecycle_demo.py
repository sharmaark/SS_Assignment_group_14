import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx


WORKFORCE_URL = "http://127.0.0.1:8002"


def request(method: str, path: str, **kwargs):
    return httpx.request(
        method,
        f"{WORKFORCE_URL}{path}",
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


def heading(number: int, text: str):
    print()
    print(f"{number}. {text}")
    print("-" * 68)


def main():
    print()
    print("=" * 68)
    print("WORKFORCE DISCOVERY & RESERVATION LIFECYCLE")
    print("=" * 68)

    # -----------------------------------------------------
    # Health
    # -----------------------------------------------------

    health = require(
        request("GET", "/health"),
        200,
    )

    print()
    print(
        f"Workforce service : "
        f"{health['status']}"
    )

    # Use a fresh slot every time the demo runs.
    slot = (
            datetime.now(timezone.utc)
            + timedelta(days=10)
    ).replace(microsecond=0)

    # -----------------------------------------------------
    # 1. Create eligible inspector
    # -----------------------------------------------------

    heading(
        1,
        "Create eligible ELECTRICAL inspector",
    )

    inspector = require(
        request(
            "POST",
            "/api/v1/inspectors",
            json={
                "name": "Lifecycle Demo Inspector",
                "skills": ["ELECTRICAL"],
                "min_longitude": 77.50,
                "min_latitude": 12.90,
                "max_longitude": 77.70,
                "max_latitude": 13.10,
            },
        ),
        201,
    )

    inspector_id = inspector["id"]

    print(
        f"Inspector ID : {inspector_id}"
    )

    print(
        "Skill        : ELECTRICAL"
    )

    print(
        "Location     : Covered"
    )

    # -----------------------------------------------------
    # 2. Discovery before reservation
    # -----------------------------------------------------

    heading(
        2,
        "Search eligible inspectors before reservation",
    )

    search_payload = {
        "required_skill": "ELECTRICAL",
        "longitude": 77.5946,
        "latitude": 12.9716,
        "slot": slot.isoformat(),
    }

    discovery_before = require(
        request(
            "POST",
            "/api/v1/inspectors/search-eligible",
            json=search_payload,
        ),
        200,
    )

    discovered_before_ids = {
        item["id"]
        for item in discovery_before["items"]
    }

    assert inspector_id in discovered_before_ids

    print(
        f"Search result count : "
        f"{discovery_before['count']}"
    )

    print(
        "Demo inspector      : FOUND"
    )

    # -----------------------------------------------------
    # 3. Availability before reservation
    # -----------------------------------------------------

    heading(
        3,
        "Check availability before reservation",
    )

    availability_before = require(
        request(
            "GET",
            (
                f"/api/v1/inspectors/"
                f"{inspector_id}/availability"
            ),
            params={
                "slot": slot.isoformat()
            },
        ),
        200,
    )

    assert (
            availability_before["available"]
            is True
    )

    print(
        "Available before reservation : TRUE"
    )

    # -----------------------------------------------------
    # 4. Reserve inspector
    # -----------------------------------------------------

    heading(
        4,
        "Reserve inspector",
    )

    reservation = require(
        request(
            "POST",
            "/api/v1/reservations",
            json={
                "assignment_id":
                    str(uuid4()),

                "inspector_id":
                    inspector_id,

                "required_skill":
                    "ELECTRICAL",

                "longitude":
                    77.5946,

                "latitude":
                    12.9716,

                "slot":
                    slot.isoformat(),
            },
        ),
        201,
    )

    print(
        f"Reservation ID : "
        f"{reservation['id']}"
    )

    print(
        f"State          : "
        f"{reservation['state']}"
    )

    # -----------------------------------------------------
    # 5. Availability after reservation
    # -----------------------------------------------------

    heading(
        5,
        "Check availability after reservation",
    )

    availability_after = require(
        request(
            "GET",
            (
                f"/api/v1/inspectors/"
                f"{inspector_id}/availability"
            ),
            params={
                "slot": slot.isoformat()
            },
        ),
        200,
    )

    assert (
            availability_after["available"]
            is False
    )

    print(
        "Available after reservation  : FALSE"
    )

    # -----------------------------------------------------
    # 6. Discovery after reservation
    # -----------------------------------------------------

    heading(
        6,
        "Search eligible inspectors after reservation",
    )

    discovery_after = require(
        request(
            "POST",
            "/api/v1/inspectors/search-eligible",
            json=search_payload,
        ),
        200,
    )

    discovered_after_ids = {
        item["id"]
        for item in discovery_after["items"]
    }

    assert (
            inspector_id
            not in discovered_after_ids
    )

    print(
        f"Search result count : "
        f"{discovery_after['count']}"
    )

    print(
        "Reserved inspector  : EXCLUDED"
    )

    # -----------------------------------------------------
    # Final result
    # -----------------------------------------------------

    print()
    print("=" * 68)
    print("RESULT: PASS")
    print("=" * 68)

    print()
    print(
        "Verified lifecycle:"
    )

    print(
        "Discovery"
        " -> Available"
        " -> Reservation"
        " -> Unavailable"
        " -> Excluded from discovery"
    )

    print()

    evidence = {
        "timestamp_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "inspector_id":
            inspector_id,

        "slot":
            slot.isoformat(),

        "availability_before":
            availability_before[
                "available"
            ],

        "reservation_id":
            reservation["id"],

        "availability_after":
            availability_after[
                "available"
            ],

        "inspector_returned_before_reservation":
            inspector_id
            in discovered_before_ids,

        "inspector_returned_after_reservation":
            inspector_id
            in discovered_after_ids,

        "result":
            "PASS",
    }

    print(
        json.dumps(
            evidence,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()