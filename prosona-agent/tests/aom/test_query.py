"""Tests for AOM query functions."""

from agentickit.prosonaagent.aom.query import (
    get_activity_by_activity_id,
    get_next_activity_by_activity_id,
    get_sco_by_sco_id,
    get_next_sco_by_sco_id,
)


ACTIVITY_A = {"id": "a1", "name": "Activity A", "type": "lecture"}
ACTIVITY_B = {"id": "a2", "name": "Activity B", "type": "drill"}
ACTIVITY_C = {"id": "a3", "name": "Activity C", "type": "report"}

SCO_X = {"id": "s1", "name": "SCO X", "type": "drill-guide"}
SCO_Y = {"id": "s2", "name": "SCO Y", "type": "drill-deduction"}
SCO_Z = {"id": "s3", "name": "SCO Z", "type": "drill-review"}


def _make_state(activities=None, scos=None):
    return {
        "activity_list": activities or [],
        "sco_list": scos or [],
    }


class TestGetActivityByActivityId:
    def test_found(self):
        state = _make_state(activities=[ACTIVITY_A, ACTIVITY_B])
        result = get_activity_by_activity_id(state, "a1")
        assert result == ACTIVITY_A

    def test_not_found(self):
        state = _make_state(activities=[ACTIVITY_A])
        result = get_activity_by_activity_id(state, "missing")
        assert result is None

    def test_empty_list(self):
        state = _make_state(activities=[])
        result = get_activity_by_activity_id(state, "a1")
        assert result is None


class TestGetNextActivityByActivityId:
    def test_middle_returns_next(self):
        state = _make_state(activities=[ACTIVITY_A, ACTIVITY_B, ACTIVITY_C])
        result = get_next_activity_by_activity_id(state, "a1")
        assert result == ACTIVITY_B

    def test_last_returns_none(self):
        state = _make_state(activities=[ACTIVITY_A, ACTIVITY_B])
        result = get_next_activity_by_activity_id(state, "a2")
        assert result is None

    def test_not_found_returns_none(self):
        state = _make_state(activities=[ACTIVITY_A])
        result = get_next_activity_by_activity_id(state, "missing")
        assert result is None


class TestGetScoByScoid:
    def test_found(self):
        state = _make_state(scos=[SCO_X, SCO_Y])
        result = get_sco_by_sco_id(state, "s1")
        assert result == SCO_X

    def test_not_found(self):
        state = _make_state(scos=[SCO_X])
        result = get_sco_by_sco_id(state, "missing")
        assert result is None


class TestGetNextScoByScoid:
    def test_middle_returns_next(self):
        state = _make_state(scos=[SCO_X, SCO_Y, SCO_Z])
        result = get_next_sco_by_sco_id(state, "s1")
        assert result == SCO_Y

    def test_last_returns_none(self):
        state = _make_state(scos=[SCO_X, SCO_Y])
        result = get_next_sco_by_sco_id(state, "s2")
        assert result is None

    def test_not_found_returns_none(self):
        state = _make_state(scos=[SCO_X])
        result = get_next_sco_by_sco_id(state, "missing")
        assert result is None
