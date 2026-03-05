from __future__ import annotations

from typing import TYPE_CHECKING

import click

from app.models.allowed_refresh_token import AllowedRefreshToken
from app.services.maintenance_service import purge_abandoned_guests

if TYPE_CHECKING:
    from flask import Flask
from app.extensions import assets_env
from app.services.maintenance_service import (
    purge_inactive_empty_guests_with_tokens,
)


def register_cli(app: Flask) -> None:
    @app.cli.command("build-assets")
    def build_assets_cmd() -> None:
        """Precompile static assets."""
        click.echo("Building assets...")
        # assets_env is registered in init_extensions, so it should be ready
        for name in assets_env:
            click.echo(f"Building bundle: {name}")
            bundle = assets_env[name]
            bundle.build()

        click.echo("Assets built successfully.")

    @app.cli.command("purge-guests")
    @click.option("--days", default=14, type=int, help="Retention window in days")
    @click.option(
        "--force",
        is_flag=True,
        default=False,
        help="Actually delete (omit for dry-run)",
    )
    def purge_guests_cmd(days: int, force: bool) -> None:
        """Delete anonymous users without allowed refresh tokens older than N days."""
        result = purge_abandoned_guests(retention_days=days, dry_run=not force)
        click.echo(result)

    @app.cli.command("cleanup-expired-refresh-tokens")
    def cleanup_expired_refresh_tokens_cmd() -> None:
        """Remove expired refresh token allowlist entries."""
        count = AllowedRefreshToken.cleanup_expired_tokens()
        click.echo({"expired_tokens_deleted": count})

    @app.cli.command("purge-empty-guests")
    @click.option("--days", default=14, type=int, help="Retention window in days")
    @click.option(
        "--force",
        is_flag=True,
        default=False,
        help="Actually delete (omit for dry-run)",
    )
    def purge_empty_guests_cmd(days: int, force: bool) -> None:
        """Delete guest users that still have a refresh token
        but no data and are older than N days."""
        result = purge_inactive_empty_guests_with_tokens(
            retention_days=days, dry_run=not force
        )
        click.echo(result)
