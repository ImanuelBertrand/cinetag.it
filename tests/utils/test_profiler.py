import time

from app.utils.profiler import Profiler, profile_function


def test_profile_function_decorator() -> None:
    """Test that profile_function decorator runs the function and returns result."""

    @profile_function
    def add(a, b):
        return a + b

    result = add(2, 3)
    assert result == 5


def test_profiler_start_stop() -> None:
    """Test Profiler start and stop basic flow."""
    profiler = Profiler("test_profiler")
    profiler.start()
    assert profiler.is_running is True

    time.sleep(0.01)
    profiler.stop()
    assert profiler.is_running is False


def test_profiler_context_manager() -> None:
    """Test Profiler used as a context manager."""
    with Profiler("context_test") as profiler:
        assert profiler.is_running is True
        time.sleep(0.01)

    assert profiler.is_running is False


def test_profiler_sections() -> None:
    """Test Profiler sections timing."""
    profiler = Profiler("section_test")
    profiler.start()

    profiler.start_section("section1")
    time.sleep(0.01)
    profiler.start_section("section2")
    time.sleep(0.01)
    profiler.stop()

    assert "section1" in profiler.sections
    assert "section2" in profiler.sections
    assert profiler.sections["section1"] > 0
    assert profiler.sections["section2"] > 0


def test_profiler_stop_without_start() -> None:
    """Test Profiler stop without start logs warning but doesn't crash."""
    profiler = Profiler("no_start")
    # Should not raise an exception
    profiler.stop()
    assert profiler.is_running is False


def test_profiler_start_section_not_running() -> None:
    """Test Profiler.start_section when not running logs warning."""
    profiler = Profiler("not_running")
    # Should not raise
    profiler.start_section("test_section")
    assert profiler.current_section is None


def test_profiler_debug_log_level() -> None:
    """Test Profiler with debug log level."""
    profiler = Profiler("debug_profiler", log_level="debug")
    profiler.start()
    profiler.start_section("s1")
    time.sleep(0.01)
    profiler.stop()
    assert profiler.is_running is False
