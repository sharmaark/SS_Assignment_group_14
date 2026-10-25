from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest

from services.dispatch.src import api


def submit(system, payload=None, headers=None):
    return system.client.post("/api/v1/assignments", json=payload or system.payload, headers=headers if headers is not None else system.headers)


def assert_confirmed(system, response):
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == body["stage"] == "CONFIRMED"
    assert body["notification_status"] == "SENT"
    assert len(system.repository.list_assignments()) == 1
    assert len(system.peers.reservations) == len(system.peers.notifications) == 1
    assert system.peers.work_order["state"] == "ASSIGNED"
    return body


def test_assignment_replay_preserves_response_and_forwards_contract_and_correlation(system):
    body = assert_confirmed(system, submit(system))
    replay = submit(system)
    assert replay.status_code == 201
    assert replay.json() == body
    assert replay.headers["X-Correlation-ID"] == "dispatch-contract-test"
    assert system.peers.counts == {"claim": 1, "reserve": 1, "confirm": 1, "notify": 1}
    assert all(correlation == "dispatch-contract-test" for _, _, correlation in system.peers.calls)
    reservation = next(iter(system.peers.reservations.values()))
    for field in ("required_skill", "longitude", "latitude", "slot"):
        assert reservation[field] == system.peers.work_order[field]
    assert reservation["inspector_id"] == system.payload["inspector_id"]
    changed = submit(system, {**system.payload, "inspector_id": str(uuid4())})
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert sum(system.peers.counts.values()) == 4


@pytest.mark.parametrize("headers", [{}, {"Idempotency-Key": ""}, {"Idempotency-Key": "x" * 101}])
def test_invalid_idempotency_headers_have_no_side_effects(system, headers):
    response = submit(system, headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert system.repository.list_assignments() == []
    assert not system.peers.calls


def test_invalid_ids_and_assignment_queries(system):
    assert submit(system, {**system.payload, "work_order_id": "invalid"}).status_code == 422
    assert system.client.get("/health").json()["status"] == "UP"
    assert system.client.get("/api/v1/assignments").json() == {"items": []}
    assert system.client.get(f"/api/v1/assignments/{uuid4()}").status_code == 404
    assert system.client.post(f"/api/v1/assignments/{uuid4()}/retry-notification").status_code == 404
    result = assert_confirmed(system, submit(system))
    persisted = system.client.get(f"/api/v1/assignments/{result['id']}")
    assert persisted.json()["reservation_id"] == result["reservation_id"]


@pytest.mark.parametrize("operation,stage", [("claim", "CREATED"), ("reserve", "WORK_ORDER_CLAIMED"), ("confirm", "SLOT_RESERVED")])
def test_lost_committed_response_resumes_same_assignment(system, operation, stage):
    system.peers.failures[operation] = ["timeout_after"]
    assert submit(system).status_code == 503
    assignment = system.repository.list_assignments()[0]
    assert assignment["stage"] == stage
    assert system.repository.get_idempotency_result(system.headers["Idempotency-Key"]) is None
    result = assert_confirmed(system, submit(system))
    assert result["id"] == assignment["id"]
    if operation == "confirm":
        assert system.peers.counts["claim"] == system.peers.counts["reserve"] == 1


@pytest.mark.parametrize("operation", ["claim", "reserve"])
def test_server_error_is_retryable_without_releasing_unknown_outcome(system, operation):
    system.peers.failures[operation] = ["503"]
    assert submit(system).status_code == 503
    assert system.peers.counts["release"] == 0
    assert_confirmed(system, submit(system))


def test_definite_rejection_releases_claim_and_replays_without_side_effects(system):
    system.peers.failures["reserve"] = ["409"]
    first = submit(system)
    assert first.status_code == 409
    assert system.peers.work_order["state"] == "OPEN"
    assert system.repository.list_assignments()[0]["status"] == "REJECTED"
    calls = list(system.peers.calls)
    replay = submit(system)
    assert replay.status_code == first.status_code
    assert replay.json() == first.json()
    assert system.peers.calls == calls
    assignment_id = system.repository.list_assignments()[0]["id"]
    assert system.client.post(f"/api/v1/assignments/{assignment_id}/retry-notification").status_code == 409


def test_unresolved_compensation_is_not_stored_as_terminal_rejection(system):
    system.peers.failures["reserve"] = ["409", "409"]
    system.peers.failures["release"] = ["timeout_after"]
    first = submit(system)
    assert first.status_code == 503
    assert first.json()["error"]["code"] == "CLAIM_RELEASE_UNRESOLVED"
    assert system.repository.get_idempotency_result(system.headers["Idempotency-Key"]) is None
    assert submit(system).status_code == 409
    assert system.peers.work_order["state"] == "OPEN"


@pytest.mark.parametrize("failure", ["processing", "provider_failure"])
def test_notification_failure_preserves_confirmation_and_manual_retry_keeps_stored_response(system, failure):
    if failure == "processing":
        system.peers.notification_statuses = ["PROCESSING"] * 3
    else:
        system.peers.failures["notify"] = ["503"] * 3
    response = submit(system)
    assert response.status_code == 201
    assert response.json()["status"] == "CONFIRMED"
    assert response.json()["notification_status"] == "PENDING"
    assert system.peers.counts["notify"] == 3
    notification_payloads = [payload for operation, payload, _ in system.peers.calls if operation == "notify"]
    assert len({payload["delivery_key"] for payload in notification_payloads}) == 1
    path = f"/api/v1/assignments/{response.json()['id']}/retry-notification"
    assert system.client.post(path).json()["notification_status"] == "SENT"
    assert system.client.post(path).json()["notification_status"] == "SENT"
    assert system.peers.counts["notify"] == 4
    assert submit(system).json() == response.json()
    assert len(system.peers.notifications) == 1


def test_lost_notification_response_reuses_delivery_key(system):
    system.peers.failures["notify"] = ["timeout_after"]
    assert_confirmed(system, submit(system))
    assert system.peers.counts["notify"] == 2
    assert len(system.peers.notifications) == 1


def test_confirmed_checkpoint_survives_failure_before_response_storage(system, monkeypatch):
    original = system.repository.complete

    def crash_once(*args, **kwargs):
        monkeypatch.setattr(system.repository, "complete", original)
        raise RuntimeError("simulated worker failure")

    monkeypatch.setattr(system.repository, "complete", crash_once)
    with pytest.raises(RuntimeError):
        submit(system)
    calls = list(system.peers.calls)
    assert_confirmed(system, submit(system))
    assert system.peers.calls == calls


def test_simultaneous_duplicates_execute_one_flow(system):
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: submit(system), range(8)))
    body = assert_confirmed(system, responses[0])
    assert all(response.status_code == 201 and response.json() == body for response in responses)
    assert sum(system.peers.counts.values()) == 4


def test_duplicate_wait_is_bounded(system, monkeypatch):
    entered, release = Event(), Event()
    original = api.clients.notify

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(api.clients, "notify", blocked)
    monkeypatch.setattr(api.settings, "idempotency_wait_seconds", 0)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(submit, system)
        try:
            assert entered.wait(10)
            duplicate = submit(system)
            assert duplicate.status_code == 202
        finally:
            release.set()
        completed = first.result(timeout=10)
    assert_confirmed(system, completed)
    assert duplicate.json()["id"] == completed.json()["id"]
    assert submit(system).json() == completed.json()


def test_openapi_documents_assignment_outcomes(system):
    schema = system.client.get("/openapi.json").json()
    outcomes = schema["paths"]["/api/v1/assignments"]["post"]["responses"]
    assert {"201", "202", "404", "409", "422", "503"} <= outcomes.keys()
