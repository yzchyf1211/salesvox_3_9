"""Tests for XML utility."""

from agentickit.prosonaagent.utils.xml import prettify_xml


class TestPrettifyXml:
    def test_single_tag_pair(self):
        result = prettify_xml("<root>\n    hello\n</root>")
        assert "<root>" in result
        assert "</root>" in result
        assert "hello" in result

    def test_nested_tags(self):
        xml = "<outer>\n<inner>\n    data\n</inner>\n</outer>"
        result = prettify_xml(xml)
        assert "<outer>" in result
        assert "<inner>" in result
        assert "</inner>" in result
        assert "</outer>" in result

    def test_empty_input(self):
        assert prettify_xml("") == ""
        assert prettify_xml(None) is None

    def test_indentation(self):
        xml = "<a>\n<b>\ntext\n</b>\n</a>"
        result = prettify_xml(xml, indent_size=4)
        lines = result.split("\n")
        # Inner tag should be indented
        assert lines[0] == "<a>"
        assert lines[1].startswith("    ")  # 4 spaces indent
