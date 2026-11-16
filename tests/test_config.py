"""Tests for application configuration."""

import pytest
from pydantic import ValidationError

from shortvideocli.config import Settings


def test_settings_defaults() -> None:
    """Settings should provide sensible development defaults."""
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert settings.database_url == "sqlite:///shortvideocli.db"


def test_settings_read_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings should load values using the configured environment prefix."""
    monkeypatch.setenv("SHORTVIDEOCLI_APP_ENV", "testing")
    monkeypatch.setenv("SHORTVIDEOCLI_LOG_LEVEL", "DEBUG")

    settings = Settings(_env_file=None)

    assert settings.app_env == "testing"
    assert settings.log_level == "DEBUG"


def test_settings_reject_invalid_log_level() -> None:
    """Settings should reject unsupported logging levels."""
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            log_level="TRACE",
        )
