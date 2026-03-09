"""Tests for AOM card builders."""

from agentickit.prosonaagent.aom.card import (
    build_content_card,
    build_record_card,
    build_report_card,
)


class TestBuildContentCard:
    def test_fields_and_type(self):
        card = build_content_card(
            id="card-001",
            name="My Card",
            content={"key": "value"},
            description="A content card",
        )
        assert card["id"] == "card-001"
        assert card["name"] == "My Card"
        assert card["type"] == "content"
        assert card["data"] == {"key": "value"}
        assert card["description"] == "A content card"

    def test_description_optional(self):
        card = build_content_card(id="c1", name="N", content={})
        assert card.get("description") is None

    def test_ext_not_set_by_default(self):
        card = build_content_card(id="c1", name="N", content={})
        assert card.get("ext") is None


class TestBuildRecordCard:
    def test_fields_and_type(self):
        card = build_record_card(
            id="card-002",
            name="Record Card",
            sco_id="sco-001",
            sco_order=2,
            description="A record card",
        )
        assert card["id"] == "card-002"
        assert card["name"] == "Record Card"
        assert card["type"] == "record"
        assert card["data"]["sco_id"] == "sco-001"
        assert card["data"]["order"] == 2
        assert card["description"] == "A record card"


class TestBuildReportCard:
    def test_fields_and_type(self):
        card = build_report_card(
            id="card-003",
            name="Report Card",
            artifact_id="artifact-001",
            description="A report card",
        )
        assert card["id"] == "card-003"
        assert card["name"] == "Report Card"
        assert card["type"] == "report"
        assert card["data"]["artifact_id"] == "artifact-001"
        assert card["description"] == "A report card"
