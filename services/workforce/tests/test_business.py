import pytest

from services.workforce.src.business import BusinessRuleViolation, ensure_eligible, point_is_covered


INSPECTOR = {
    "skills": ["ELECTRICAL", "SAFETY"],
    "min_longitude": 77.0,
    "min_latitude": 12.0,
    "max_longitude": 78.0,
    "max_latitude": 13.0,
}


@pytest.mark.parametrize("longitude,latitude", [(77.5, 12.5), (77.0, 12.0), (78.0, 13.0)])
def test_br1_inside_and_boundary_points_are_covered(longitude, latitude):
    assert point_is_covered(longitude, latitude, 77.0, 12.0, 78.0, 13.0)


def test_br1_outside_point_is_rejected():
    with pytest.raises(BusinessRuleViolation) as error:
        ensure_eligible(INSPECTOR, "ELECTRICAL", 80.0, 12.5)
    assert error.value.code == "OUTSIDE_SERVICE_AREA"


def test_br2_missing_skill_is_rejected():
    with pytest.raises(BusinessRuleViolation) as error:
        ensure_eligible(INSPECTOR, "GAS", 77.5, 12.5)
    assert error.value.code == "SKILL_MISMATCH"


def test_br2_matching_skill_is_accepted():
    ensure_eligible(INSPECTOR, "ELECTRICAL", 77.5, 12.5)
