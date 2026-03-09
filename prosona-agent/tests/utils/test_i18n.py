"""Tests for i18n utility."""

from agentickit.prosonaagent.utils.i18n import get_language_name


class TestGetLanguageName:
    def test_chinese_simplified(self):
        assert get_language_name("zh_CN") == "Chinese Simplified"

    def test_english(self):
        assert get_language_name("en") == "English"

    def test_japanese(self):
        assert get_language_name("ja") == "Japanese"

    def test_unknown_returns_unknown(self):
        assert get_language_name("xx_YY") == "Unknown"
