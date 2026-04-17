"""Security CLI commands: set-password, check-auth, logs, rotate-api-key."""

from __future__ import annotations

import hashlib
import os
import secrets

import typer
from rich.console import Console
from rich.table import Table

from weeklyamp.core.config import load_config
from weeklyamp.db.repository import Repository
from weeklyamp.web.security import hash_password

console = Console()
security_app = typer.Typer(name="security", help="Security and authentication management.")


@security_app.command("set-password")
def set_password() -> None:
    """Generate a bcrypt hash for a password."""
    password = typer.prompt("Password", hide_input=True, confirmation_prompt=True)
    hashed = hash_password(password)
    console.print(f"\n[bold]Bcrypt hash:[/bold]\n  {hashed}")
    console.print("\n[dim]Set this as WEEKLYAMP_ADMIN_HASH in your environment,[/dim]")
    console.print("[dim]or use WEEKLYAMP_ADMIN_PASSWORD for automatic runtime hashing.[/dim]")


@security_app.command("check-auth")
def check_auth() -> None:
    """Verify auth env vars are configured."""
    console.print("\n[bold]Auth Configuration Check[/bold]\n")

    secret_key = os.environ.get("WEEKLYAMP_SECRET_KEY", "")
    admin_hash = os.environ.get("WEEKLYAMP_ADMIN_HASH", "")
    admin_password = os.environ.get("WEEKLYAMP_ADMIN_PASSWORD", "")

    if secret_key:
        console.print("  WEEKLYAMP_SECRET_KEY    [green]set[/green]")
    else:
        console.print("  WEEKLYAMP_SECRET_KEY    [red]not set[/red] (random key used per restart)")

    if admin_hash:
        console.print("  WEEKLYAMP_ADMIN_HASH    [green]set[/green]")
    elif admin_password:
        console.print("  WEEKLYAMP_ADMIN_HASH    [yellow]not set[/yellow] (using ADMIN_PASSWORD fallback)")
    else:
        console.print("  WEEKLYAMP_ADMIN_HASH    [red]not set[/red]")

    if admin_password:
        console.print("  WEEKLYAMP_ADMIN_PASSWORD [green]set[/green]")
    else:
        console.print("  WEEKLYAMP_ADMIN_PASSWORD [dim]not set[/dim]")

    if not admin_hash and not admin_password:
        console.print("\n  [red]Auth is disabled![/red] Set WEEKLYAMP_ADMIN_HASH or WEEKLYAMP_ADMIN_PASSWORD.")
    else:
        console.print("\n  [green]Auth is enabled.[/green]")


@security_app.command("rotate-api-key")
def rotate_api_key(
    name: str = typer.Argument(..., help="Human-readable key name (e.g. 'mobile-app')"),
    permissions: str = typer.Option("read", help="Comma-separated: read,write"),
    rate_limit: int = typer.Option(1000, help="Per-minute rate limit"),
) -> None:
    """Generate a new API key and insert it as active.

    Prints the raw key ONCE to stdout — it is never recoverable after
    this run because only the SHA-256 hash is stored. Deactivates any
    existing active key with the same `name` so the rotation is atomic
    from the caller's point of view.
    """
    cfg = load_config()
    repo = Repository(cfg.db_path, cfg.database_url, cfg.db_backend)

    # Generate a cryptographically random 32-byte key, URL-safe b64.
    # Prefix with `tfs_` so operators can recognise it in logs.
    raw = "tfs_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    key_prefix = raw[:12]

    conn = repo._conn()
    try:
        # Deactivate prior keys with this name so the rotation replaces
        # the old one atomically.
        if repo._is_pg:
            conn.execute(
                "UPDATE api_keys SET is_active = 0 WHERE name = ?", (name,),
            )
            conn.execute(
                "INSERT INTO api_keys (name, key_hash, key_prefix, permissions, rate_limit, is_active) "
                "VALUES (?, ?, ?, ?, ?, 1)",
                (name, key_hash, key_prefix, permissions, rate_limit),
            )
        else:
            conn.execute(
                "UPDATE api_keys SET is_active = 0 WHERE name = ?", (name,),
            )
            conn.execute(
                "INSERT INTO api_keys (name, key_hash, key_prefix, permissions, rate_limit, is_active) "
                "VALUES (?, ?, ?, ?, ?, 1)",
                (name, key_hash, key_prefix, permissions, rate_limit),
            )
        conn.commit()
    finally:
        conn.close()

    console.print(f"\n[bold green]New API key for '{name}':[/bold green]")
    console.print(f"  [bold]{raw}[/bold]")
    console.print(
        "\n[yellow]Store this now — it will not be shown again.[/yellow]"
    )
    console.print(
        "[dim]Send as: Authorization: Bearer <key>[/dim]\n"
    )


@security_app.command("logs")
def show_logs(
    limit: int = typer.Option(20, help="Number of events to show"),
) -> None:
    """Display recent security events."""
    cfg = load_config()
    repo = Repository(cfg.db_path)

    try:
        events = repo.get_security_log(limit=limit)
    except Exception:
        console.print("[red]Could not read security_log table.[/red] Run migrations first.")
        raise typer.Exit(1)

    if not events:
        console.print("[dim]No security events recorded yet.[/dim]")
        return

    table = Table(title="Security Events")
    table.add_column("Time", style="dim")
    table.add_column("Event", style="cyan")
    table.add_column("IP", style="white")
    table.add_column("Detail", style="white")

    for ev in events:
        table.add_row(
            str(ev.get("created_at", "")),
            ev.get("event_type", ""),
            ev.get("ip_address", ""),
            ev.get("detail", ""),
        )

    console.print(table)
