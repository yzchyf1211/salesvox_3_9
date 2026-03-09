"""Tests for JSON utility."""

from agentickit.prosonaagent.utils.json import safe_get_value


class TestSafeGetValue:
    def test_from_dict(self):
        assert safe_get_value({"name": "test"}, "name") == "test"

    def test_from_json_string(self):
        assert safe_get_value('{"name": "test"}', "name") == "test"

    def test_missing_key_returns_default(self):
        assert safe_get_value({"name": "test"}, "age", "unknown") == "unknown"

    def test_empty_string(self):
        assert safe_get_value("", "name", "default") == "default"

    def test_invalid_json(self):
        assert safe_get_value("not json", "name", "fallback") == "fallback"

    def test_none_input(self):
        assert safe_get_value(None, "name", "default") == "default"

    def test_integer_input(self):
        assert safe_get_value(42, "name", "default") == "default"
