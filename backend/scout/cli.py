"""
SCOUT command-line interface.

Commands
--------
scout serve        Start the FastAPI server (default: 127.0.0.1:8765)
scout config show  Print the current resolved configuration
scout config init  Write a default config file to ~/.scout/config.toml
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

app = typer.Typer(name="scout", help="SCOUT — local-first OSINT toolkit", no_args_is_help=True)
config_app = typer.Typer(help="Manage SCOUT configuration", no_args_is_help=True)
app.add_typer(config_app, name="config")


# ---------------------------------------------------------------------------
# scout serve
# ---------------------------------------------------------------------------


@app.command()
def serve(
    host: str = typer.Option(None, "--host", help="Bind host (default from config)"),
    port: int = typer.Option(None, "--port", help="Bind port (default from config)"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev mode)"),
) -> None:
    """Start the SCOUT API server."""
    import uvicorn

    from scout.config import get_config
    from scout.db import get_engine, init_db

    cfg = get_config()
    bind_host = host or cfg.host
    bind_port = port or cfg.port

    if bind_host != "127.0.0.1":
        typer.echo(
            f"WARNING: binding to {bind_host} exposes SCOUT on the network. "
            "No authentication is provided in v1.",
            err=True,
        )

    # Ensure DB is initialised before the server starts
    engine = get_engine(cfg.db_path)
    init_db(engine)

    typer.echo(f"Starting SCOUT on http://{bind_host}:{bind_port}")
    uvicorn.run(
        "scout.main:app",
        host=bind_host,
        port=bind_port,
        reload=reload,
    )


# ---------------------------------------------------------------------------
# scout config show
# ---------------------------------------------------------------------------


@config_app.command("show")
def config_show() -> None:
    """Print the current resolved configuration."""
    from scout.config import get_config

    cfg = get_config()
    typer.echo(f"db_path : {cfg.db_path}")
    typer.echo(f"host    : {cfg.host}")
    typer.echo(f"port    : {cfg.port}")
    typer.echo("")
    typer.echo("[sources]")
    typer.echo(f"  hibp.api_key       : {'<set>' if cfg.sources.hibp.api_key else '<not set>'}")
    typer.echo(f"  virustotal.api_key : {'<set>' if cfg.sources.virustotal.api_key else '<not set>'}")
    typer.echo(f"  abuseipdb.api_key  : {'<set>' if cfg.sources.abuseipdb.api_key else '<not set>'}")
    typer.echo(f"  github.token       : {'<set>' if cfg.sources.github.token else '<not set>'}")


# ---------------------------------------------------------------------------
# scout config init
# ---------------------------------------------------------------------------


@config_app.command("init")
def config_init(
    force: bool = typer.Option(False, "--force", help="Overwrite existing config file"),
) -> None:
    """Write a default config file to ~/.scout/config.toml."""
    from scout.config import write_default_config

    path = Path.home() / ".scout" / "config.toml"
    if path.exists() and not force:
        typer.echo(f"Config already exists at {path}. Use --force to overwrite.", err=True)
        raise typer.Exit(1)
    write_default_config(path)
    typer.echo(f"Config written to {path}")
    typer.echo("Edit it to add your API keys.")
