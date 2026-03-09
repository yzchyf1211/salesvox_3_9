"""Tests for AOM context builders."""

from agentickit.prosonaagent.aom.context import (
    get_project_context,
    get_activity_list_context,
    get_activity_context,
    get_current_sco_context,
)


MOCK_PROJECT = {
    "actvId": "proj-001",
    "actvName": "Test Project",
    "description": "A test project",
    "startTime": "2024-01-01",
    "endTime": "2024-12-31",
}

MOCK_ACTIVITY = {
    "id": "act-001",
    "name": "Test Activity",
    "description": "An activity",
    "type": "roleplay",
}

MOCK_SCO = {
    "id": "sco-001",
    "name": "Test SCO",
    "type": "drill-guide",
    "description": "A guide SCO",
}


class TestGetProjectContext:
    def test_returns_xml_with_project_fields(self):
        result = get_project_context(MOCK_PROJECT)
        assert "<project_information>" in result
        assert "proj-001" in result
        assert "Test Project" in result
        assert "</project_information>" in result


class TestGetActivityListContext:
    def test_returns_xml_with_activities(self):
        result = get_activity_list_context([MOCK_ACTIVITY])
        assert "<activity_list>" in result
        assert "<activity_item>" in result
        assert "act-001" in result
        assert "Test Activity" in result
        assert "</activity_list>" in result

    def test_multiple_activities(self):
        activity2 = {**MOCK_ACTIVITY, "id": "act-002", "name": "Second Activity"}
        result = get_activity_list_context([MOCK_ACTIVITY, activity2])
        assert "act-001" in result
        assert "act-002" in result


class TestGetActivityContext:
    def test_returns_xml_with_activity_and_scos(self):
        result = get_activity_context(MOCK_ACTIVITY, [MOCK_SCO])
        assert "<activity_item>" in result
        assert "act-001" in result
        assert "<sco_list>" in result
        assert "<sco_item>" in result
        assert "sco-001" in result
        assert "</activity_item>" in result


class TestGetCurrentScoContext:
    def test_returns_xml_with_sco_fields(self):
        result = get_current_sco_context(MOCK_SCO)
        assert "<current_sco>" in result
        assert "sco-001" in result
        assert "Test SCO" in result
        assert "drill-guide" in result
        assert "</current_sco>" in result
