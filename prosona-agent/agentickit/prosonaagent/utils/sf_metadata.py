from typing import Dict, Any, TypedDict, Optional


class SearchAndFilterMetadata(TypedDict, total=False):
    search_text_1: Optional[str]
    search_text_2: Optional[str]
    search_text_3: Optional[str]
    search_text_4: Optional[str]
    search_text_5: Optional[str]
    filter_keyword_1: Optional[str]
    filter_keyword_2: Optional[str]
    filter_keyword_3: Optional[str]
    filter_keyword_4: Optional[str]
    filter_keyword_5: Optional[str]


def build_sf_metadata(
    search_text_1: Optional[str] = None,
    filter_keyword_1: Optional[str] = None,
) -> "SearchAndFilterMetadata":
    """Build SearchAndFilterMetadata, omitting None-valued fields."""
    meta: Dict[str, Any] = {}
    if search_text_1 is not None:
        meta["search_text_1"] = search_text_1
    if filter_keyword_1 is not None:
        meta["filter_keyword_1"] = filter_keyword_1
    return meta
