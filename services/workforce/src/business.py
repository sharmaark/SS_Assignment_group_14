class BusinessRuleViolation(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def point_is_covered(
    longitude: float,
    latitude: float,
    min_longitude: float,
    min_latitude: float,
    max_longitude: float,
    max_latitude: float,
) -> bool:
    """BR1: boundary points are included in the rectangular service area."""
    return (
        min_longitude <= longitude <= max_longitude
        and min_latitude <= latitude <= max_latitude
    )


def ensure_eligible(inspector: dict, required_skill: str, longitude: float, latitude: float) -> None:
    """BR1 and BR2: inspector must cover the point and possess the skill."""
    if required_skill not in inspector["skills"]:
        raise BusinessRuleViolation(
            "SKILL_MISMATCH", "Inspector does not have the required skill", 422
        )
    if not point_is_covered(
        longitude,
        latitude,
        inspector["min_longitude"],
        inspector["min_latitude"],
        inspector["max_longitude"],
        inspector["max_latitude"],
    ):
        raise BusinessRuleViolation(
            "OUTSIDE_SERVICE_AREA", "Inspection location is outside the inspector service area", 422
        )
