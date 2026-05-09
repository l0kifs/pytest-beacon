"""
Value objects for test run domain.
"""
from enum import Enum

from typing import Any

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
    data: dict[str, Any] = Field(default_factory=dict)


class TestLogs(BaseModel):
    """Captured log entries grouped by test execution phase."""

    setup: list[LogEntry] = Field(default_factory=list)
    call: list[LogEntry] = Field(default_factory=list)
    teardown: list[LogEntry] = Field(default_factory=list)


class ConsoleStream(BaseModel):
    """Captured console lines for one stream."""

    lines: list[str] = Field(default_factory=list)
    truncated: bool = False
    omitted_lines: int = 0


class ConsolePhaseOutput(BaseModel):
    """Captured stdout/stderr for one pytest execution phase."""

    stdout: ConsoleStream | None = None
    stderr: ConsoleStream | None = None


class TestConsoleOutput(BaseModel):
    """Captured console output grouped by test execution phase."""

    setup: ConsolePhaseOutput | None = None
    call: ConsolePhaseOutput | None = None
    teardown: ConsolePhaseOutput | None = None
