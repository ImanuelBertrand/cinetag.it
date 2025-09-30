import logging
import time
from collections import defaultdict
from functools import wraps

_logger = logging.getLogger(__name__)


def profile_function(func):
    """
    Decorator to profile a function's execution time.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        _logger.info(
            f"Function {func.__name__} executed in {execution_time:.4f} seconds"
        )
        return result

    return wrapper


class Profiler:
    """
    A profiler for measuring execution time of code blocks.
    Can be used either as a context manager or with explicit start/stop calls.
    """

    def __init__(self, name, log_level="info"):
        self.name = name
        self.log_level = log_level
        self.start_time = None
        self.sections = defaultdict(float)
        self.current_section = None
        self.section_start_time = None
        self.is_running = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        """Start the profiler."""
        self.start_time = time.time()
        self.is_running = True
        return self

    def stop(self):
        """Stop the profiler and log the results."""
        if not self.is_running:
            _logger.warning(f"Profiler {self.name} was stopped without being started")
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
                f"Cannot start section {name} - profiler {self.name} is not running"
            )
            return self

        if self.current_section:
            self.end_section()

        self.current_section = name
        self.section_start_time = time.time()
        return self

    def end_section(self):
        """End timing the current section."""
        if not self.current_section:
            return self

        if not self.is_running:
            _logger.warning(
                f"Cannot end section {self.current_section} - "
                f"profiler {self.name} is not running"
            )
            return self

        duration = time.time() - self.section_start_time
        self.sections[self.current_section] += duration
        self.current_section = None
        return self
