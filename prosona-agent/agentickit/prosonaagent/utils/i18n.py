LOCALE_NAMES = {
    "zh_CN": "Chinese Simplified",
    "zh_TW": "Chinese Traditional",
    "ja": "Japanese",
    "en": "English",
}


def get_locale_name(locale: str) -> str:
    return LOCALE_NAMES.get(locale, "Unknown")
