import pytest

from services.work_order.src.business import (
    BusinessRuleViolation,
    ensure_can_confirm,
    ensure_photo_allowed,
)


def test_br4_only_claim_owner_can_confirm():
    ensure_can_confirm("CLAIMED", "assignment-1", "assignment-1")
    with pytest.raises(BusinessRuleViolation) as error:
        ensure_can_confirm("CLAIMED", "assignment-2", "assignment-1")
    assert error.value.code == "INVALID_WORK_ORDER_TRANSITION"


def test_br6_photo_requires_assigned_work_order():
    ensure_photo_allowed("ASSIGNED", "image/jpeg", 100, 1000)
    with pytest.raises(BusinessRuleViolation) as error:
        ensure_photo_allowed("OPEN", "image/jpeg", 100, 1000)
    assert error.value.code == "WORK_ORDER_NOT_ASSIGNED"


@pytest.mark.parametrize("content_type", ["text/plain", "application/pdf"])
def test_br6_photo_type_is_limited(content_type):
    with pytest.raises(BusinessRuleViolation) as error:
        ensure_photo_allowed("ASSIGNED", content_type, 100, 1000)
    assert error.value.code == "UNSUPPORTED_PHOTO_TYPE"


def test_br6_photo_size_is_limited():
    with pytest.raises(BusinessRuleViolation) as error:
        ensure_photo_allowed("ASSIGNED", "image/png", 1001, 1000)
    assert error.value.code == "PHOTO_TOO_LARGE"
