import pytest

from services.dispatch.src.business import (
    BusinessRuleViolation,
    ensure_matching_fingerprint,
    request_fingerprint,
    retry_delay,
)


def test_br5_fingerprint_is_independent_of_key_order():
    assert request_fingerprint({"work_order_id": "a", "inspector_id": "b"}) == request_fingerprint(
        {"inspector_id": "b", "work_order_id": "a"}
    )


def test_br5_changed_payload_is_rejected():
    stored = request_fingerprint({"work_order_id": "a", "inspector_id": "b"})
    received = request_fingerprint({"work_order_id": "a", "inspector_id": "c"})
    with pytest.raises(BusinessRuleViolation) as error:
        ensure_matching_fingerprint(stored, received)
    assert error.value.code == "IDEMPOTENCY_KEY_REUSED"


def test_exponential_backoff_increases_and_includes_bounded_jitter():
    assert retry_delay(0.2, 1, random_value=0.5) == pytest.approx(0.3)
    assert retry_delay(0.2, 2, random_value=0.5) == pytest.approx(0.5)
    assert retry_delay(0.2, 3, random_value=0.5) == pytest.approx(0.9)
