"""Root conftest: shared fixtures and configuration for all tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def test_fixtures_dir() -> Path:
    """Return the path to the tests directory for loading test data."""
    return Path(__file__).parent
