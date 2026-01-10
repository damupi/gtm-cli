"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def mock_config_dir(tmp_path: pytest.TempPathFactory) -> str:
    """Create a temporary config directory for testing."""
    config_dir = tmp_path / ".gtm-orchestrator"
    config_dir.mkdir()
    (config_dir / "profiles").mkdir()
    (config_dir / "tokens").mkdir()
    return str(config_dir)
