import logging
import time
from collections import defaultdict
from functools import wraps
from typing import Any, Self

_logger = logging.getLogger(__name__)


def profile_function(func):
    """
    Decorator to profile a function's execution time.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        _logger.info(
            "Function %s executed in %.4f seconds", func.__name__, execution_time
        )
        return result

    return wrapper


class Profiler:
    """
    A profiler for measuring execution time of code blocks.
    Can be used either as a context manager or with explicit start/stop calls.
    """

    def __init__(self, name: str, log_level: str = "info") -> None:
        self.name = name
        self.log_level = log_level
        self.start_time: float | None = None
        self.sections: dict[str, float] = defaultdict(float)
        self.current_section: str | None = None
        self.section_start_time: float | None = None
        self.is_running = False

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def start(self):
        """Start the profiler."""
        self.start_time = time.time()
        self.is_running = True
        return self

    def stop(self):
        """Stop the profiler and log the results."""
        if not self.is_running or self.start_time is None:
            _logger.warning("Profiler %s was stopped without being started", self.name)
            return self

        if self.current_section:
            self.end_section()

        total_time = time.time() - self.start_time

        # Create a summary of the profiling results
        summary = [f"Profiling results for {self.name} (total: {total_time:.4f}s):"]
        for section, duration in self.sections.items():
            percentage = (duration / total_time) * 100
            summary.append(f"  - {section}: {duration:.4f}s ({percentage:.1f}%)")

        # Log the summary
        if self.log_level == "debug":
            _logger.debug("\n".join(summary))
        else:
            _logger.info("\n".join(summary))

        self.is_running = False
        return self

    def start_section(self, name):
        """Start timing a new section."""
        if not self.is_running:
            _logger.warning(
                "Cannot start section %s - profiler %s is not running", name, self.name
            )
            return self

        if self.current_section:
            self.end_section()

        self.current_section = name
        self.section_start_time = time.time()
        return self

    def end_section(self):
        """End timing the current section."""
        if not self.current_section or self.section_start_time is None:
            return self

        if not self.is_running:
            _logger.warning(
                "Cannot end section %s - profiler %s is not running",
                self.current_section,
                self.name,
            )
            return self

        duration = time.time() - self.section_start_time
        self.sections[self.current_section] += duration
        self.current_section = None
        return self
