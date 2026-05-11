import os
import subprocess
import sys
import textwrap

import pytest

from app import scheduler as scheduler_module


@pytest.fixture
def _reset_scheduler_lock():
    """Reset the module-level lock fd before and after the test."""
    scheduler_module._scheduler_lock_fd = None  # noqa: SLF001
    yield
    fd = scheduler_module._scheduler_lock_fd  # noqa: SLF001
    if fd is not None:
        os.close(fd)
    scheduler_module._scheduler_lock_fd = None  # noqa: SLF001


@pytest.mark.usefixtures("_reset_scheduler_lock")
def test_acquire_scheduler_lock_excludes_other_processes(tmp_path):
    """Only one process at a time can hold the scheduler lock — the gate that
    keeps multiple gunicorn workers from each starting their own cron jobs."""
    assert scheduler_module._acquire_scheduler_lock(str(tmp_path)) is True  # noqa: SLF001
    assert (tmp_path / "scheduler.lock").exists()

    # A separate process tries to flock the same file. fcntl is used directly
    # so the subprocess does not need to import the full Flask app stack.
    script = textwrap.dedent(
        """
        import fcntl
        import os
        import sys

        fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit(0)
        sys.exit(1)
        """
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script, str(tmp_path / "scheduler.lock")],
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, (
        f"expected BlockingIOError in subprocess; stderr={result.stderr!r}"
    )


@pytest.mark.usefixtures("_reset_scheduler_lock")
def test_acquire_scheduler_lock_is_idempotent_within_process(tmp_path):
    """A re-entry inside the same process short-circuits without re-locking."""
    assert scheduler_module._acquire_scheduler_lock(str(tmp_path)) is True  # noqa: SLF001
    held_fd = scheduler_module._scheduler_lock_fd  # noqa: SLF001
    assert scheduler_module._acquire_scheduler_lock(str(tmp_path)) is True  # noqa: SLF001
    assert scheduler_module._scheduler_lock_fd == held_fd  # noqa: SLF001
