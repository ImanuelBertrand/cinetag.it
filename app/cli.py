from typing import TYPE_CHECKING

import click

from app.models.allowed_refresh_token import AllowedRefreshToken
from app.services.maintenance_service import purge_abandoned_guests

if TYPE_CHECKING:
    from flask import Flask


def register_cli(app: Flask):
    @app.cli.command("purge-guests")
    @click.option("--days", default=14, type=int, help="Retention window in days")
    @click.option(
        "--force",
        is_flag=True,
        default=False,
        help="Actually delete (omit for dry-run)",
    )
    def purge_guests_cmd(days: int, force: bool):
        """Delete anonymous users without allowed refresh tokens older than N days."""
        result = purge_abandoned_guests(retention_days=days, dry_run=not force)
        click.echo(result)

    @app.cli.command("cleanup-expired-refresh-tokens")
    def cleanup_expired_refresh_tokens_cmd():
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
    def purge_empty_guests_cmd(days: int, force: bool):
        """Delete guest users that still have a refresh token
        but no data and are older than N days."""
        # import locally to avoid modifying top-level imports further
        from app.services.maintenance_service import (
            purge_inactive_empty_guests_with_tokens,
        )

        result = purge_inactive_empty_guests_with_tokens(
            retention_days=days, dry_run=not force
        )
        click.echo(result)
