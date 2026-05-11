import os
import time
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from app.services import backup_service
from app.services.backup_service import (
    DUMP_PREFIX,
    DUMP_SUFFIX,
    WEEKLY_MARKER,
    _is_backup_due,
    _pg_env_from_uri,
    run_backup_if_due,
)


@pytest.fixture
def backup_dir(app, tmp_path, monkeypatch):
    """Point STORAGE_DIR at a tmp dir so backups land there during the test."""
    monkeypatch.setitem(app.config, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setitem(app.config, "BACKUP_ENABLED", True)
    return tmp_path / "db_backups"


def _touch_dump(backup_dir: Path, name: str, age_seconds: float = 0) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    f = backup_dir / name
    f.write_bytes(b"fake-pg_dump-data")
    if age_seconds:
        past = time.time() - age_seconds
        os.utime(f, (past, past))
    return f


def test_is_backup_due_when_no_dumps_exist(tmp_path) -> None:
    assert _is_backup_due(tmp_path, min_interval_hours=24) is True


def test_is_backup_due_when_latest_is_old(tmp_path) -> None:
    _touch_dump(
        tmp_path, f"{DUMP_PREFIX}20260101T000000Z{DUMP_SUFFIX}", age_seconds=25 * 3600
    )
    assert _is_backup_due(tmp_path, min_interval_hours=24) is True


def test_is_backup_due_skipped_when_latest_is_recent(tmp_path) -> None:
    _touch_dump(
        tmp_path, f"{DUMP_PREFIX}20260101T000000Z{DUMP_SUFFIX}", age_seconds=3600
    )
    assert _is_backup_due(tmp_path, min_interval_hours=24) is False


def test_is_backup_due_ignores_weekly_files(tmp_path) -> None:
    """A weekly snapshot alone must not satisfy the daily-interval check."""
    _touch_dump(
        tmp_path,
        f"{DUMP_PREFIX}2026-W01{WEEKLY_MARKER}{DUMP_SUFFIX}",
        age_seconds=3600,
    )
    assert _is_backup_due(tmp_path, min_interval_hours=24) is True


def test_pg_env_from_uri_extracts_credentials() -> None:
    uri = "postgresql://alice:s3cr%21t@dbhost:5433/mydb"
    env = _pg_env_from_uri(uri)
    assert env["PGHOST"] == "dbhost"
    assert env["PGPORT"] == "5433"
    assert env["PGUSER"] == "alice"
    assert env["PGPASSWORD"] == "s3cr!t"
    assert env["PGDATABASE"] == "mydb"


def test_pg_env_from_uri_defaults_port() -> None:
    env = _pg_env_from_uri("postgresql://u:p@host/db")
    assert env["PGPORT"] == "5432"


def test_pg_env_from_uri_rejects_non_postgres_scheme() -> None:
    with pytest.raises(ValueError, match="Unsupported DB scheme"):
        _pg_env_from_uri("mysql://u:p@host/db")


def _fake_pg_dump(target: Path, compression: int) -> None:
    """Stand-in for the real pg_dump: writes a small file at the target path."""
    target.write_bytes(b"FAKE_DUMP_CONTENT")


def test_run_backup_if_due_creates_file_when_no_prior(app, backup_dir) -> None:
    with app.app_context(), patch.object(backup_service, "_run_pg_dump", _fake_pg_dump):
        run_backup_if_due()

    dumps = list(backup_dir.glob(f"{DUMP_PREFIX}*{DUMP_SUFFIX}"))
    daily = [f for f in dumps if WEEKLY_MARKER not in f.name]
    weekly = [f for f in dumps if WEEKLY_MARKER in f.name]
    assert len(daily) == 1
    # The same run also seeds a weekly snapshot for the current ISO week
    assert len(weekly) == 1


def test_run_backup_if_due_skips_when_recent_exists(app, backup_dir) -> None:
    _touch_dump(
        backup_dir, f"{DUMP_PREFIX}20260101T000000Z{DUMP_SUFFIX}", age_seconds=600
    )

    with app.app_context(), patch.object(backup_service, "_run_pg_dump", _fake_pg_dump):
        run_backup_if_due()

    daily = [
        f
        for f in backup_dir.glob(f"{DUMP_PREFIX}*{DUMP_SUFFIX}")
        if WEEKLY_MARKER not in f.name
    ]
    assert len(daily) == 1, "should not have created a second dump"


def test_run_backup_if_due_respects_disabled_flag(app, backup_dir, monkeypatch) -> None:
    monkeypatch.setitem(app.config, "BACKUP_ENABLED", False)

    with app.app_context(), patch.object(backup_service, "_run_pg_dump", _fake_pg_dump):
        run_backup_if_due()

    assert not backup_dir.exists() or not list(backup_dir.iterdir())


def test_run_backup_if_due_rotates_old_daily(app, backup_dir, monkeypatch) -> None:
    monkeypatch.setitem(app.config, "BACKUP_KEEP_DAYS", 7)
    # Old daily dump well past the cutoff, plus a recent-enough one — the recent one
    # blocks a new dump, but rotation still prunes the stale file on the same pass...
    # so trigger by aging the latest beyond the interval.
    _touch_dump(
        backup_dir,
        f"{DUMP_PREFIX}20260101T000000Z{DUMP_SUFFIX}",
        age_seconds=30 * 86400,
    )
    _touch_dump(
        backup_dir, f"{DUMP_PREFIX}20260105T000000Z{DUMP_SUFFIX}", age_seconds=25 * 3600
    )

    with app.app_context(), patch.object(backup_service, "_run_pg_dump", _fake_pg_dump):
        run_backup_if_due()

    remaining = sorted(f.name for f in backup_dir.glob(f"{DUMP_PREFIX}*{DUMP_SUFFIX}"))
    # 30-day-old dump pruned; the 25h one kept; new dump added; weekly snapshot added.
    assert "cinetagit_20260101T000000Z.dump" not in remaining
    assert "cinetagit_20260105T000000Z.dump" in remaining
    daily_new = [
        n
        for n in remaining
        if WEEKLY_MARKER not in n and n != "cinetagit_20260105T000000Z.dump"
    ]
    assert len(daily_new) == 1


def test_run_backup_if_due_keeps_weekly_beyond_daily_window(
    app, backup_dir, monkeypatch
) -> None:
    monkeypatch.setitem(app.config, "BACKUP_KEEP_DAYS", 7)
    monkeypatch.setitem(app.config, "BACKUP_KEEP_WEEKS", 8)
    # 30-day-old weekly snapshot must survive (under the 8-week window).
    weekly = _touch_dump(
        backup_dir,
        f"{DUMP_PREFIX}2026-W01{WEEKLY_MARKER}{DUMP_SUFFIX}",
        age_seconds=30 * 86400,
    )

    with app.app_context(), patch.object(backup_service, "_run_pg_dump", _fake_pg_dump):
        run_backup_if_due()

    assert weekly.exists(), "weekly snapshots within retention must not be pruned"
