"""Tests for A2A biz data message builders."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentickit.prosonaagent.aom.message import (
    send_activity_lifecycle_message,
    send_sco_lifecycle_message,
    send_layout_message,
    send_display_message,
)
from agentickit.prosonaagent.aom.card import build_content_card


STATE = {"context_id": "ctx-001"}
ACTIVITY = {"id": "act-1", "name": "Activity 1", "type": "lecture"}
SCO = {"id": "sco-1", "name": "SCO 1", "type": "content"}


@pytest.fixture(autouse=True)
def mock_send_to():
    with patch("agentickit.prosonaagent.aom.message.send_to", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture(autouse=True)
def mock_user_agent_proxy():
    with patch("agentickit.prosonaagent.aom.message.UserAgentProxy", return_value=MagicMock()):
        yield


def _msg(mock_send_to):
    """Extract A2ABizDataMessage from send_to call."""
    return mock_send_to.call_args[0][1]


def _params(mock_send_to):
    return _msg(mock_send_to).content["params"]


def _identifier(mock_send_to):
    return _msg(mock_send_to).content["identifier"]


class TestSendActivityLifecycleMessage:
    @pytest.mark.asyncio
    async def test_identifier(self, mock_send_to):
        await send_activity_lifecycle_message(STATE, "start", ACTIVITY)
        assert _identifier(mock_send_to) == "biz-common-activity-lifecycle"

    @pytest.mark.asyncio
    async def test_params(self, mock_send_to):
        await send_activity_lifecycle_message(STATE, "end", ACTIVITY)
        params = _params(mock_send_to)
        assert params["type"] == "end"
        assert params["activity_id"] == "act-1"
        assert params["activity_name"] == "Activity 1"
        assert params["activity_type"] == "lecture"


class TestSendScoLifecycleMessage:
    @pytest.mark.asyncio
    async def test_identifier(self, mock_send_to):
        await send_sco_lifecycle_message(STATE, "start", SCO, ACTIVITY, order=1)
        assert _identifier(mock_send_to) == "biz-common-sco-lifecycle"

    @pytest.mark.asyncio
    async def test_params(self, mock_send_to):
        await send_sco_lifecycle_message(STATE, "start", SCO, ACTIVITY, order=2)
        params = _params(mock_send_to)
        assert params["type"] == "start"
        assert params["data"]["sco_id"] == "sco-1"
        assert params["data"]["activity_id"] == "act-1"
        assert params["data"]["order"] == 2


class TestSendLayoutMessage:
    @pytest.mark.asyncio
    async def test_default_layout_type(self, mock_send_to):
        await send_layout_message(STATE)
        assert _identifier(mock_send_to) == "biz-common-layout"
        assert _params(mock_send_to)["type"] == "canvas"

    @pytest.mark.asyncio
    async def test_speaker_layout_type(self, mock_send_to):
        await send_layout_message(STATE, layout_type="speaker")
        assert _params(mock_send_to)["type"] == "speaker"


class TestSendDisplayMessage:
    @pytest.mark.asyncio
    async def test_identifier_and_basic_fields(self, mock_send_to):
        card = build_content_card(id="c1", name="Card", content={"k": "v"})
        await send_display_message(STATE, card)
        assert _identifier(mock_send_to) == "biz-common-display"
        data = _params(mock_send_to)["data"]
        assert data["id"] == "c1"
        assert data["name"] == "Card"
        assert data["type"] == "content"
        assert data["data"] == {"k": "v"}

    @pytest.mark.asyncio
    async def test_ref_included(self, mock_send_to):
        card = build_content_card(id="c1", name="Card", content={})
        ref = {"id": "task-1", "name": "content", "group": "sco", "params": {}, "mode": "start"}
        await send_display_message(STATE, card, ref=ref)
        assert _params(mock_send_to)["ref"] == ref

    @pytest.mark.asyncio
    async def test_no_ref_by_default(self, mock_send_to):
        card = build_content_card(id="c1", name="Card", content={})
        await send_display_message(STATE, card)
        assert "ref" not in _params(mock_send_to)

    @pytest.mark.asyncio
    async def test_sf_metadata_always_set(self, mock_send_to):
        card = build_content_card(id="c1", name="My Card", content={})
        await send_display_message(STATE, card)
        part_metadata = mock_send_to.call_args[1].get("part_metadata")
        assert part_metadata is not None
        assert part_metadata.get("search_text_1") == "My Card"
        assert part_metadata.get("filter_keyword_1") == "content"

    @pytest.mark.asyncio
    async def test_ext_included_when_set(self, mock_send_to):
        card = build_content_card(id="c1", name="Card", content={})
        card["ext"] = {"custom_key": "val"}
        await send_display_message(STATE, card)
        assert _params(mock_send_to)["data"]["ext"] == {"custom_key": "val"}

    @pytest.mark.asyncio
    async def test_ext_omitted_when_not_set(self, mock_send_to):
        card = build_content_card(id="c1", name="Card", content={})
        await send_display_message(STATE, card)
        assert "ext" not in _params(mock_send_to)["data"]

