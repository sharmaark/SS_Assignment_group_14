import os

import pytest

from services.dispatch.src.business import request_fingerprint
from services.dispatch.src.data import DispatchRepository


pytestmark = pytest.mark.skipif(not os.getenv("DISPATCH_TEST_DATABASE_URL"), reason="set DISPATCH_TEST_DATABASE_URL for real PostgreSQL locks")


def test_execution_lock_excludes_another_connection_and_releases_on_failure(repository):
    other = DispatchRepository(repository.engine.url)
    try:
        with pytest.raises(RuntimeError):
            with repository.execution_lock("same-key") as acquired:
                assert acquired
                with other.execution_lock("same-key") as duplicate:
                    assert not duplicate
                with other.execution_lock("independent-key") as independent:
                    assert independent
                raise RuntimeError("simulated worker exit")
        with other.execution_lock("same-key") as recovered:
            assert recovered
    finally:
        other.engine.dispose()
        other.lock_engine.dispose()


def test_committed_checkpoint_is_visible_to_a_new_repository(repository):
    repository.initialise()
    payload = {"work_order_id": "work-order", "inspector_id": "inspector"}
    assignment, _, _ = repository.claim_request("durable-key", request_fingerprint(payload), payload)
    repository.update_stage(assignment["id"], "SLOT_RESERVED", "reservation")
    other = DispatchRepository(repository.engine.url)
    try:
        saved = other.get_assignment(assignment["id"])
        assert saved["stage"] == "SLOT_RESERVED"
        assert saved["reservation_id"] == "reservation"
        assert other.get_idempotency_result("durable-key") is None
    finally:
        other.engine.dispose()
        other.lock_engine.dispose()
