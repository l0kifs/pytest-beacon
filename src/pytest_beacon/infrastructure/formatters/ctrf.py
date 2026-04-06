"""
CTRF 1.0.0 formatter.

Converts a TestRun aggregate into a CTRF-compliant report dict ready for
JSON/YAML serialisation.
"""
import sys
from typing import Any

import pytest

from pytest_beacon.domains.test_run.entities import TestRun
from pytest_beacon.domains.test_run.value_objects import TestStatus


def build_ctrf_report(
    run: TestRun,
    *,
    plugin_name: str = "pytest-beacon",
    plugin_version: str = "0.1.0",
    excluded_statuses: set[str] | None = None,
    xdist_workers: int | None = None,
    extra_meta: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return a CTRF 1.0.0 report dict from *run*."""
    excluded_statuses = excluded_statuses or set()

    tests_section = []
    for result in run.tests:
        if result.status.value in excluded_statuses:
            continue
        tests_section.append(_format_test(result))

    environment: dict[str, Any] = {
        "pythonVersion": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "pytestVersion": pytest.__version__,
    }
    if xdist_workers is not None:
        environment["xdistWorkers"] = xdist_workers
    if extra_meta:
        environment.update(extra_meta)

    summary = run.summary  # already includes start/stop

    return {
        "results": {
            "tool": {
                "name": "pytest",
                "version": pytest.__version__,
            },
            "summary": summary,
            "tests": tests_section,
            "environment": environment,
            "extra": {
                "pluginName": plugin_name,
                "pluginVersion": plugin_version,
                "ctrf": "1.0.0",
                "generatedAt": summary["stop"],
            },
        }
    }


def _format_test(result) -> dict[str, Any]:
    item: dict[str, Any] = {
        "name": result.nodeid,
        "status": result.status.value,
        "duration": result.duration_ms,
    }

    if result.file_path is not None:
        item["filePath"] = result.file_path
    if result.line is not None:
        item["line"] = result.line
    if result.message is not None:
        item["message"] = result.message
    if result.trace is not None:
        item["trace"] = result.trace
    if result.failure_location is not None:
        item["failureLocation"] = result.failure_location
    if result.marks:
        item["marks"] = result.marks
    if result.params:
        item["params"] = result.params
    if result.allure_id is not None:
        item["allureId"] = result.allure_id
    if result.stdout is not None:
        item["stdout"] = result.stdout
    if result.stderr is not None:
        item["stderr"] = result.stderr

    return item
