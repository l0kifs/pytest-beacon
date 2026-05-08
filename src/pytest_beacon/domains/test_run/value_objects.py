"""
Value objects for test run domain.
"""
from enum import Enum

from pydantic import BaseModel, Field


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    OTHER = "other"


class LogEntry(BaseModel):
    """A single captured log record."""

    level: str
    message: str
    logger: str = ""
    timestamp: str | None = None


class TestLogs(BaseModel):
    """Captured log entries grouped by test execution phase."""

    setup: list[LogEntry] = Field(default_factory=list)
    call: list[LogEntry] = Field(default_factory=list)
    teardown: list[LogEntry] = Field(default_factory=list)
