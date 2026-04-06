"""
Domain entities for test execution results.
"""
import time
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from pytest_beacon.domains.test_run.value_objects import TestStatus


class TestResult(BaseModel):
    """Represents the outcome of a single test."""

    nodeid: str
    name: str
    status: TestStatus = TestStatus.OTHER
    duration_ms: float = 0.0
    start_time: datetime | None = None
    file_path: str | None = None
    line: int | None = None
    message: str | None = None
    trace: str | None = None
    failure_location: dict[str, Any] | None = None
    marks: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    allure_id: str | None = None
    stdout: str | None = None
    stderr: str | None = None


_SUMMARY_KEYS = ("passed", "failed", "skipped", "error", "other")


class TestRun:
    """Aggregate root representing a complete test session."""

    def __init__(self) -> None:
        self.start_ms: int = int(time.time() * 1000)
        self.stop_ms: int = 0
        self._tests: list[TestResult] = []
        self._summary: dict[str, int] = {
            "tests": 0,
            "passed": 0,
            "failed": 0,
            "pending": 0,
            "skipped": 0,
            "error": 0,
            "other": 0,
        }

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_result(self, result: TestResult) -> None:
        """Record a test result and update summary counters."""
        self._update_summary(result.status)
        self._tests.append(result)

    def update_summary_only(self, status: TestStatus) -> None:
        """Update summary counters without adding to tests list (for excluded statuses)."""
        self._update_summary(status)

    def merge_worker_results(
        self,
        raw_tests: list[dict[str, Any]],
        excluded_statuses: set[str],
        seen_collection_errors: set[str],
    ) -> None:
        """Merge serialised test dicts from an xdist worker into this run."""
        for raw in raw_tests:
            status_str = raw.get("status", "other")
            # Always update summary
            try:
                status = TestStatus(status_str)
            except ValueError:
                status = TestStatus.OTHER
            self._update_summary(status)

            # Deduplicate collection errors by file path
            if status == TestStatus.ERROR:
                file_path = raw.get("file_path")
                if file_path:
                    if file_path in seen_collection_errors:
                        continue
                    seen_collection_errors.add(file_path)

            if status_str in excluded_statuses:
                continue

            # Normalise status to a valid TestStatus value before construction
            self._tests.append(TestResult(**{**raw, "status": status.value}))

    def finalize(self) -> None:
        self.stop_ms = int(time.time() * 1000)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @property
    def tests(self) -> list[TestResult]:
        return self._tests

    @property
    def summary(self) -> dict[str, int]:
        return {**self._summary, "start": self.start_ms, "stop": self.stop_ms}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_summary(self, status: TestStatus) -> None:
        self._summary["tests"] += 1
        key = status.value if status.value in _SUMMARY_KEYS else "other"
        self._summary[key] += 1
