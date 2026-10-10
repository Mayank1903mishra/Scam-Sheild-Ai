"""Configuration loading and CORS allow-list parsing."""
import json
from pathlib import Path

import pytest

from app.config import Settings, get_allowed_origins

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


@pytest.fixture
def clear_origin_env(monkeypatch):
    for name in ("ALLOWED_ORIGINS", "APP_ENV"):
        monkeypatch.delenv(name, raising=False)


class TestEnvExample:
    def test_shipped_env_example_loads_without_crashing(self, clear_origin_env):
        """Copying .env.example to .env must not stop the app from starting.

        A bare ALLOWED_ORIGINS value used to raise SettingsError because
        pydantic refuses to coerce a plain string into List[str].
        """
        loaded = Settings(_env_file=str(ENV_EXAMPLE))
        assert loaded.app_env == "development"
        assert "http://localhost:5173" in loaded.allowed_origins

    def test_env_example_origins_are_accepted(self, clear_origin_env, monkeypatch):
        loaded = Settings(_env_file=str(ENV_EXAMPLE))
        monkeypatch.setattr("app.config.settings.allowed_origins", loaded.allowed_origins)
        origins = get_allowed_origins()
        assert "http://localhost:3000" in origins
        assert "http://localhost:5173" in origins


class TestAllowedOrigins:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("http://localhost:5173", ["http://localhost:5173"]),
            (
                "http://localhost:5173,http://localhost:3000",
                ["http://localhost:5173", "http://localhost:3000"],
            ),
            (
                json.dumps(["http://localhost:5173", "http://localhost:3000"]),
                ["http://localhost:5173", "http://localhost:3000"],
            ),
            ("", []),
            ("  http://a.test ,  http://b.test  ", ["http://a.test", "http://b.test"]),
        ],
    )
    def test_parsing_forms(self, monkeypatch, raw, expected):
        monkeypatch.setattr("app.config.settings.allowed_origins", raw)
        assert get_allowed_origins() == expected

    def test_default_covers_both_dev_ports(self, monkeypatch):
        default = Settings.model_fields["allowed_origins"].default
        monkeypatch.setattr("app.config.settings.allowed_origins", default)
        origins = get_allowed_origins()
        assert "http://localhost:5173" in origins
        assert "http://localhost:3000" in origins
        assert "http://127.0.0.1:3000" in origins
