import pytest
from pydantic import ValidationError

from services.dispatch.src.config import Settings


@pytest.mark.parametrize("field,value", [
    ("downstream_timeout_seconds", 0), ("notification_max_attempts", 0),
    ("notification_max_attempts", 11), ("retry_base_seconds", -1),
    ("idempotency_wait_seconds", -1), ("dispatch_port", 0),
])
def test_invalid_runtime_limits_are_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
