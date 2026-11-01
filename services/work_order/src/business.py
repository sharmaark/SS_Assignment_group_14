ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png"}


class BusinessRuleViolation(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def ensure_can_confirm(state: str, owner: str | None, assignment_id: str) -> None:
    """BR4: only the assignment which owns a claim may confirm it."""
    if state == "ASSIGNED" and owner == assignment_id:
        return
    if state != "CLAIMED" or owner != assignment_id:
        raise BusinessRuleViolation(
            "INVALID_WORK_ORDER_TRANSITION",
            "Only the assignment owning a claimed work order may confirm it",
        )


def ensure_photo_allowed(
    work_order_state: str, content_type: str | None, size: int, max_size: int
) -> None:
    """BR6: inspection evidence is accepted only in supported form after assignment."""
    if work_order_state != "ASSIGNED":
        raise BusinessRuleViolation(
            "WORK_ORDER_NOT_ASSIGNED",
            "Photos can be attached only after the work order is assigned",
        )
    if content_type not in ALLOWED_PHOTO_TYPES:
        raise BusinessRuleViolation(
            "UNSUPPORTED_PHOTO_TYPE", "Only JPEG and PNG photos are accepted", 422
        )
    if size > max_size:
        raise BusinessRuleViolation(
            "PHOTO_TOO_LARGE", f"Photo exceeds the {max_size}-byte limit", 413
        )
