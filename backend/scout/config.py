"""
Configuration loader for SCOUT.

Loads settings from ``~/.scout/config.toml`` (if it exists) and supports
``SCOUT_*`` environment variable overrides.  All fields have sensible defaults
so the application starts without any configuration file present.

TOML layout understood by this module::

    [scout]
    db_path = "~/.scout/scout.db"
    host    = "127.0.0.1"
    port    = 8765

    [sources.hibp]
    api_key = ""

    [sources.virustotal]
    api_key = ""

    [sources.abuseipdb]
    api_key = ""

    [sources.github]
    token = ""

Usage
-----
    from scout.config import get_config

    cfg = get_config()
    print(cfg.db_path)
    print(cfg.sources.hibp.api_key)

    # CLI helper
    from pathlib import Path
    from scout.config import write_default_config
    write_default_config(Path.home() / ".scout" / "config.toml")
"""

from __future__ import annotations

import functools
import sys
from pathlib import Path
from typing import Any, ClassVar, Tuple, Type

from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

# ---------------------------------------------------------------------------
# Source-level config models
# ---------------------------------------------------------------------------


class HibpConfig(BaseModel):
    api_key: str = ""


class VirusTotalConfig(BaseModel):
    api_key: str = ""


class AbuseIPDBConfig(BaseModel):
    api_key: str = ""


class GitHubConfig(BaseModel):
    token: str = ""


class SourcesConfig(BaseModel):
    hibp: HibpConfig = HibpConfig()
    virustotal: VirusTotalConfig = VirusTotalConfig()
    abuseipdb: AbuseIPDBConfig = AbuseIPDBConfig()
    github: GitHubConfig = GitHubConfig()


# ---------------------------------------------------------------------------
# Custom TOML settings source
# ---------------------------------------------------------------------------


class _ScoutTomlSource(PydanticBaseSettingsSource):
    """Read ``~/.scout/config.toml`` and map its sections to :class:`ScoutConfig`.

    The TOML file uses a ``[scout]`` table for top-level fields and a
    ``[sources.*]`` hierarchy for per-source credentials.  This source
    flattens those into the flat dict that :class:`BaseSettings` expects::

        {"db_path": ..., "host": ..., "port": ..., "sources": {...}}

    If the file does not exist the source returns an empty dict silently.
    The path is resolved at *call time* from the module-level ``_CONFIG_FILE``
    so tests can monkeypatch it.
    """

    def _load(self) -> dict[str, Any]:
        import scout.config as _self_module  # resolved at call time for testability

        toml_path: Path = _self_module._CONFIG_FILE
        if not toml_path.exists():
            return {}

        if sys.version_info >= (3, 11):
            import tomllib
        else:
            try:
                import tomllib  # type: ignore[no-redef]
            except ImportError:
                import tomli as tomllib  # type: ignore[no-redef]

        raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))

        result: dict[str, Any] = {}

        # Top-level fields live under [scout]
        scout_section = raw.get("scout", {})
        result.update(scout_section)

        # Source credentials live under [sources.*]
        sources_section = raw.get("sources", {})
        if sources_section:
            result["sources"] = sources_section

        return result

    def __call__(self) -> dict[str, Any]:
        return self._load()

    def get_field_value(
        self,
        field: Any,
        field_name: str,
    ) -> tuple[Any, str, bool]:
        """Return the value for *field_name* from the parsed TOML data.

        The return tuple is ``(value, field_name, is_complex)`` as required
        by :class:`PydanticBaseSettingsSource`.
        """
        data = self._load()
        value = data.get(field_name)
        return value, field_name, False


# ---------------------------------------------------------------------------
# Top-level settings
# ---------------------------------------------------------------------------

_CONFIG_FILE = Path.home() / ".scout" / "config.toml"


class ScoutConfig(BaseSettings):
    """SCOUT application settings.

    Resolution order (highest wins):
    1. Environment variables (``SCOUT_*``)
    2. ``~/.scout/config.toml``
    3. Field defaults
    """

    db_path: Path = Path.home() / ".scout" / "scout.db"
    host: str = "127.0.0.1"
    port: int = 8765
    sources: SourcesConfig = SourcesConfig()

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="SCOUT_",
    )

    @field_validator("db_path", mode="before")
    @classmethod
    def _expand_db_path(cls, v: Any) -> Path:
        """Expand ``~`` in *db_path* to the current user's home directory."""
        return Path(v).expanduser()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Load from env vars first, then TOML file, then defaults."""
        return (
            init_settings,
            env_settings,
            _ScoutTomlSource(settings_cls),
        )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def get_config() -> ScoutConfig:
    """Return the cached singleton :class:`ScoutConfig` instance.

    The first call reads and parses the TOML file (if present) and any
    ``SCOUT_*`` environment variables.  Subsequent calls return the cached
    object without re-reading.
    """
    return ScoutConfig()


# ---------------------------------------------------------------------------
# Default config writer
# ---------------------------------------------------------------------------

_DEFAULT_TOML = """\
[scout]
db_path = "~/.scout/scout.db"
host    = "127.0.0.1"
port    = 8765

[sources.hibp]
api_key = ""

[sources.virustotal]
api_key = ""

[sources.abuseipdb]
api_key = ""

[sources.github]
token = ""
"""


def write_default_config(path: Path) -> None:
    """Write the default TOML configuration template to *path*.

    Parent directories are created as needed.  After writing, the file
    permissions are set to ``0o600`` (owner read/write only) so that API keys
    stored later are not world-readable.  On Windows, ``Path.chmod()`` raises
    ``NotImplementedError`` which is silently ignored.

    Args:
        path: Destination path for the config file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_DEFAULT_TOML, encoding="utf-8")
    try:
        path.chmod(0o600)
    except NotImplementedError:
        pass
