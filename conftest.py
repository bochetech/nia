# Common test fixtures for all Python microservices
import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy for asyncio."""
    return asyncio.DefaultEventLoopPolicy()
