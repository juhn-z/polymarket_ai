"""Shared pytest fixtures for the backend test suite."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest


@pytest.fixture(scope="session")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    return asyncio.DefaultEventLoopPolicy()
