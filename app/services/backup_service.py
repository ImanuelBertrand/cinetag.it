import logging
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from flask import current_app

_logger = logging.getLogger(__name__)

DUMP_PREFIX = "cinetagit_"
DUMP_SUFFIX = ".dump"
WEEKLY_MARKER = "_weekly"


def _backup_dir() -> Path:
    storage_dir = current_app.config["STORAGE_DIR"]
    path = Path(storage_dir) / "db_backups"
    path.mkdir(parents=True, exist_ok=True)
    # DB dumps contain the full dataset; keep the directory owner-only so other
    # users on the host (or a compromised sibling process) can't read them.
    try:
        path.chmod(0o700)
    except OSError:
        _logger.exception("backup: could not restrict permissions on %s", path)
    return path


def _all_dumps(backup_dir: Path) -> list[Path]:
    return list(backup_dir.glob(f"{DUMP_PREFIX}*{DUMP_SUFFIX}"))


def _daily_dumps(backup_dir: Path) -> list[Path]:
    return [f for f in _all_dumps(backup_dir) if WEEKLY_MARKER not in f.name]


def _latest_daily_mtime(backup_dir: Path) -> float | None:
    candidates = _daily_dumps(backup_dir)
    if not candidates:
        return None
    return max(f.stat().st_mtime for f in candidates)


def _is_backup_due(backup_dir: Path, min_interval_hours: float) -> bool:
    latest = _latest_daily_mtime(backup_dir)
    if latest is None:
        return True
    return (time.time() - latest) >= min_interval_hours * 3600


def _pg_env_from_uri(uri: str) -> dict[str, str]:
    """Split a postgres URI into PG* env vars so the password never reaches argv."""
    parsed = urlparse(uri)
    if parsed.scheme not in ("postgresql", "postgres"):
        raise ValueError(f"Unsupported DB scheme for backup: {parsed.scheme!r}")
    env = os.environ.copy()
    if parsed.hostname:
        env["PGHOST"] = parsed.hostname
    env["PGPORT"] = str(parsed.port or 5432)
    if parsed.username:
        env["PGUSER"] = unquote(parsed.username)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    dbname = parsed.path.lstrip("/")
    if dbname:
        env["PGDATABASE"] = dbname
    return env


def _run_pg_dump(target: Path, compression: int) -> None:
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    env = _pg_env_from_uri(uri)
    tmp = target.with_suffix(target.suffix + ".tmp")
    cmd = [
        "pg_dump",
        "--format=custom",
        f"--compress={compression}",
        "--no-owner",
        "--no-privileges",
        "--file",
        str(tmp),
    ]
    try:
        subprocess.run(  # noqa: S603  # fixed argv, no shell, no user input
            cmd, check=True, env=env, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as exc:
        tmp.unlink(missing_ok=True)
        # stderr may contain the connection string echo but never the password
        _logger.exception(
            "backup: pg_dump failed (exit %s): %s", exc.returncode, exc.stderr
        )
        raise
    tmp.rename(target)


def _ensure_weekly(backup_dir: Path, source: Path) -> None:
    iso_year, iso_week, _ = datetime.now(UTC).isocalendar()
    name = f"{DUMP_PREFIX}{iso_year}-W{iso_week:02d}{WEEKLY_MARKER}{DUMP_SUFFIX}"
    weekly_path = backup_dir / name
    if weekly_path.exists():
        return
    shutil.copy2(source, weekly_path)
    _logger.info("backup: tagged weekly snapshot %s", name)


def _rotate(backup_dir: Path, keep_days: int, keep_weeks: int) -> None:
    now = time.time()
    daily_cutoff = now - keep_days * 86400
    weekly_cutoff = now - keep_weeks * 7 * 86400
    for f in _all_dumps(backup_dir):
        is_weekly = WEEKLY_MARKER in f.name
        cutoff = weekly_cutoff if is_weekly else daily_cutoff
        if f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                _logger.info("backup: pruned %s", f.name)
            except OSError:
                _logger.exception("backup: failed to prune %s", f.name)


def run_backup_if_due() -> None:
    """Create a new DB dump if the newest existing one is older than the threshold.

    Stateless: the schedule lives in the backup files themselves, so a container
    restart does not trigger an immediate dump when a recent one already exists.
    """
    cfg = current_app.config
    if not cfg.get("BACKUP_ENABLED", True):
        return

    min_interval_hours = float(cfg.get("BACKUP_MIN_INTERVAL_HOURS", 23.5))
    keep_days = int(cfg.get("BACKUP_KEEP_DAYS", 14))
    keep_weeks = int(cfg.get("BACKUP_KEEP_WEEKS", 8))
    compression = int(cfg.get("BACKUP_COMPRESSION", 6))

    backup_dir = _backup_dir()

    if not _is_backup_due(backup_dir, min_interval_hours):
        return

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"{DUMP_PREFIX}{ts}{DUMP_SUFFIX}"

    _logger.info("backup: starting pg_dump → %s", target.name)
    start = time.time()
    _run_pg_dump(target, compression=compression)
    size_mb = target.stat().st_size / (1024 * 1024)
    _logger.info(
        "backup: wrote %s (%.1f MB in %.1fs)",
        target.name,
        size_mb,
        time.time() - start,
    )

    _ensure_weekly(backup_dir, target)
    _rotate(backup_dir, keep_days=keep_days, keep_weeks=keep_weeks)
