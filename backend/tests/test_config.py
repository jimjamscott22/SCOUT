"""Tests for scout.config — settings loading, defaults, and helpers."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

import scout.config as config_module
from scout.config import ScoutConfig, SourcesConfig, get_config, write_default_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_get_config() -> ScoutConfig:
    """Clear the lru_cache and return a fresh ScoutConfig instance."""
    get_config.cache_clear()
    return get_config()


# ---------------------------------------------------------------------------
# Default config (no file, no env vars)
# ---------------------------------------------------------------------------


def test_default_db_path_is_under_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """db_path default must be inside the user's home directory."""
    # Point the TOML file at a non-existent path so no file is read.
    monkeypatch.setattr(config_module, "_CONFIG_FILE", tmp_path / "nonexistent.toml")
    get_config.cache_clear()
    cfg = ScoutConfig()
    assert cfg.db_path == Path.home() / ".scout" / "scout.db"


def test_default_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default host must be 127.0.0.1."""
    monkeypatch.setattr(config_module, "_CONFIG_FILE", tmp_path / "nonexistent.toml")
    cfg = ScoutConfig()
    assert cfg.host == "127.0.0.1"


def test_default_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Default port must be 8765."""
    monkeypatch.setattr(config_module, "_CONFIG_FILE", tmp_path / "nonexistent.toml")
    cfg = ScoutConfig()
    assert cfg.port == 8765


def test_default_sources_are_empty_strings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """All source API key / token defaults must be empty strings."""
    monkeypatch.setattr(config_module, "_CONFIG_FILE", tmp_path / "nonexistent.toml")
    cfg = ScoutConfig()
    assert cfg.sources.hibp.api_key == ""
    assert cfg.sources.virustotal.api_key == ""
    assert cfg.sources.abuseipdb.api_key == ""
    assert cfg.sources.github.token == ""


# ---------------------------------------------------------------------------
# db_path ~ expansion
# ---------------------------------------------------------------------------


def test_db_path_expands_tilde(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """db_path must expand '~' to the real home directory."""
    monkeypatch.setattr(config_module, "_CONFIG_FILE", tmp_path / "nonexistent.toml")
    cfg = ScoutConfig()
    # The resolved path must not start with '~'
    assert not str(cfg.db_path).startswith("~")
    assert cfg.db_path.is_absolute()


def test_db_path_expands_tilde_from_string(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Providing '~/custom/path.db' as a string must expand to an absolute path."""
    monkeypatch.setattr(config_module, "_CONFIG_FILE", tmp_path / "nonexistent.toml")
    cfg = ScoutConfig(db_path="~/custom/path.db")  # type: ignore[arg-type]
    assert not str(cfg.db_path).startswith("~")
    assert cfg.db_path.is_absolute()
    assert cfg.db_path == Path.home() / "custom" / "path.db"


# ---------------------------------------------------------------------------
# TOML file loading
# ---------------------------------------------------------------------------


def test_config_loads_from_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Values present in a TOML file must override the defaults."""
    toml_file = tmp_path / "config.toml"
    toml_file.write_text(
        "[scout]\nport = 9999\nhost = \"0.0.0.0\"\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "_CONFIG_FILE", toml_file)
    cfg = ScoutConfig()
    assert cfg.port == 9999
    assert cfg.host == "0.0.0.0"


def test_missing_toml_file_uses_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing TOML file must not raise FileNotFoundError."""
    monkeypatch.setattr(config_module, "_CONFIG_FILE", tmp_path / "does_not_exist.toml")
    # Should not raise
    cfg = ScoutConfig()
    assert cfg.port == 8765


# ---------------------------------------------------------------------------
# write_default_config
# ---------------------------------------------------------------------------


def test_write_default_config_creates_file(tmp_path: Path) -> None:
    """write_default_config must create the file at the given path."""
    target = tmp_path / "cfg" / "config.toml"
    assert not target.exists()
    write_default_config(target)
    assert target.exists()


def test_write_default_config_contains_expected_keys(tmp_path: Path) -> None:
    """The written TOML must contain all expected section headers and keys."""
    target = tmp_path / "config.toml"
    write_default_config(target)
    content = target.read_text(encoding="utf-8")

    assert "[scout]" in content
    assert "db_path" in content
    assert "host" in content
    assert "port" in content
    assert "[sources.hibp]" in content
    assert "[sources.virustotal]" in content
    assert "[sources.abuseipdb]" in content
    assert "[sources.github]" in content


def test_write_default_config_is_valid_toml(tmp_path: Path) -> None:
    """The written file must be parseable as valid TOML."""
    import tomllib

    target = tmp_path / "config.toml"
    write_default_config(target)
    data = tomllib.loads(target.read_text(encoding="utf-8"))

    assert data["scout"]["port"] == 8765
    assert data["scout"]["host"] == "127.0.0.1"
    assert data["sources"]["hibp"]["api_key"] == ""
    assert data["sources"]["github"]["token"] == ""


def test_write_default_config_creates_parent_dirs(tmp_path: Path) -> None:
    """write_default_config must create intermediate parent directories."""
    target = tmp_path / "deep" / "nested" / "config.toml"
    write_default_config(target)
    assert target.exists()


# ---------------------------------------------------------------------------
# Singleton / get_config
# ---------------------------------------------------------------------------


def test_get_config_returns_same_instance() -> None:
    """get_config() must return the identical cached object on repeated calls."""
    get_config.cache_clear()
    first = get_config()
    second = get_config()
    assert first is second


def test_get_config_cache_clear_returns_new_instance() -> None:
    """After cache_clear(), get_config() must return a fresh instance."""
    get_config.cache_clear()
    first = get_config()
    get_config.cache_clear()
    second = get_config()
    # They may be equal in value, but must be different objects
    assert first is not second
