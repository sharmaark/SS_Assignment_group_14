import hashlib
import json
import random


class BusinessRuleViolation(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def request_fingerprint(payload: dict) -> str:
    """BR5: identical meaning produces a stable request fingerprint."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ensure_matching_fingerprint(stored: str, received: str) -> None:
    if stored != received:
        raise BusinessRuleViolation(
            "IDEMPOTENCY_KEY_REUSED",
            "Idempotency-Key was already used with a different request payload",
        )


def retry_delay(base_seconds: float, attempt_number: int, random_value: float | None = None) -> float:
    jitter = random.uniform(0, base_seconds) if random_value is None else random_value * base_seconds
    return base_seconds * (2 ** (attempt_number - 1)) + jitter
