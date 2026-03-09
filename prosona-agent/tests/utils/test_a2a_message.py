"""Tests for A2A message classes."""

from agentickit.prosonaagent.utils.a2a_message import (
    A2AMessage,
    A2ADataMessage,
    A2ATextMessage,
    A2ABizDataMessage,
)


class TestA2ADataMessage:
    def test_content_stored(self):
        msg = A2ADataMessage(content={"key": "value"})
        assert msg.get_content() == {"key": "value"}


class TestA2ATextMessage:
    def test_content_stored(self):
        msg = A2ATextMessage(content="hello world")
        assert msg.get_content() == "hello world"


class TestA2ABizDataMessage:
    def test_content_structure(self):
        msg = A2ABizDataMessage(
            id="msg-001",
            sco_id="sco-001",
            name="Test",
            identifier="biz-common-sco-lifecycle",
            params={"type": "start"},
        )
        content = msg.get_content()
        assert content["type"] == "biz"
        assert content["id"] == "msg-001"
        assert content["scoid"] == "sco-001"
        assert content["name"] == "Test"
        assert content["identifier"] == "biz-common-sco-lifecycle"
        assert content["params"] == {"type": "start"}

    def test_default_values(self):
        msg = A2ABizDataMessage()
        content = msg.get_content()
        assert content["type"] == "biz"
        assert content["id"] == ""
        assert content["scoid"] == ""
        assert content["name"] == ""
        assert content["identifier"] == ""
        assert content["params"] == {}

    def test_is_subclass_of_data_message(self):
        msg = A2ABizDataMessage()
        assert isinstance(msg, A2ADataMessage)
        assert isinstance(msg, A2AMessage)
