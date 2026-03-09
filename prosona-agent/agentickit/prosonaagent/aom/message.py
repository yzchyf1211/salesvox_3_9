"""
A2A Biz Data Message builders.

Each function corresponds to one protocol identifier defined in
docs/protocol_a2a_biz_data.md, constructing and sending the message via send_to.
send_display_message always includes sf_metadata (search_text_1, filter_keyword_1).
"""

from typing import Any, Dict, Optional

from agentickit.prosonaagent.aom.types import AOMCard
from agentickit.prosonaagent.utils.agent_proxy import send_to, UserAgentProxy
from agentickit.prosonaagent.utils.a2a_message import A2ABizDataMessage
from agentickit.prosonaagent.utils.sf_metadata import build_sf_metadata


# §1  biz-common-activity-lifecycle
async def send_activity_lifecycle_message(
    state: Dict[str, Any],
    lifecycle_type: str,
    activity: Dict[str, Any],
) -> None:
    """Send Activity lifecycle message (start / pause / resume / interrupt / recover / end)."""
    await send_to(
        UserAgentProxy(state),
        A2ABizDataMessage(
            name="biz-common-activity-lifecycle",
            identifier="biz-common-activity-lifecycle",
            params={
                "type": lifecycle_type,
                "activity_id": activity.get("id"),
                "activity_name": activity.get("name"),
                "activity_type": activity.get("type"),
            },
        ),
    )


# §2  biz-common-sco-lifecycle
async def send_sco_lifecycle_message(
    state: Dict[str, Any],
    lifecycle_type: str,
    sco: Dict[str, Any],
    activity: Dict[str, Any],
    order: int,
) -> None:
    """Send SCO lifecycle message (start / pause / resume / interrupt / recover / end)."""
    await send_to(
        UserAgentProxy(state),
        A2ABizDataMessage(
            name="biz-common-sco-lifecycle",
            identifier="biz-common-sco-lifecycle",
            params={
                "type": lifecycle_type,
                "data": {
                    "type": lifecycle_type,
                    "sco_id": sco.get("id"),
                    "sco_name": sco.get("name"),
                    "sco_type": sco.get("type"),
                    "activity_id": activity.get("id"),
                    "order": order,
                },
            },
        ),
    )


# §3  biz-common-layout
async def send_layout_message(
    state: Dict[str, Any],
    layout_type: str = "canvas",
) -> None:
    """Send layout message (switches UI layout). layout_type: canvas | speaker."""
    await send_to(
        UserAgentProxy(state),
        A2ABizDataMessage(
            name="biz-common-layout",
            identifier="biz-common-layout",
            params={"type": layout_type},
        ),
    )


# §4  biz-common-display
async def send_display_message(
    state: Dict[str, Any],
    card: AOMCard,
    ref: Optional[Dict[str, Any]] = None,
) -> None:
    """Send content display message (renders card in UI)."""
    data: Dict[str, Any] = {
        "id": card["id"],
        "name": card["name"],
        "type": card["type"],
        "data": card["data"],
    }
    ext = card.get("ext")
    if ext is not None:
        data["ext"] = ext

    params: Dict[str, Any] = {"type": "card", "data": data}
    if ref is not None:
        params["ref"] = ref

    part_metadata = build_sf_metadata(
        search_text_1=card["name"],
        filter_keyword_1=card["type"],
    )

    await send_to(
        UserAgentProxy(state),
        A2ABizDataMessage(
            name=card["name"],
            identifier="biz-common-display",
            params=params,
        ),
        part_metadata=part_metadata,
    )
