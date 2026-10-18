"""
pytest configuration for WealthWatch backend tests.
Sets asyncio_mode for pytest-anyio compatibility.
"""
import pytest


def pytest_configure(config):
    """Register anyio marker to silence PytestUnknownMarkWarning."""
    config.addinivalue_line("markers", "anyio: mark test as async (anyio)")
