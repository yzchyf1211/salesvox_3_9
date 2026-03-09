"""Shared fixtures for core tests."""

import pytest


@pytest.fixture
def event_loop_policy():
    """Use default event loop policy."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
