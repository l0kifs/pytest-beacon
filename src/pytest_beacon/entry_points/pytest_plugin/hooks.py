"""
pytest-beacon plugin: hook implementations and plugin registration.

Entry point registered in pyproject.toml as:
    [project.entry-points.pytest11]
    beacon = "pytest_beacon.entry_points.pytest_plugin.hooks"
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from pytest_beacon.config.settings import get_settings
from pytest_beacon.domains.test_run.entities import TestResult, TestRun
from pytest_beacon.domains.test_run.value_objects import TestStatus
from pytest_beacon.entry_points.pytest_plugin import options as _options
from pytest_beacon.entry_points.pytest_plugin import xdist as _xdist
from pytest_beacon.infrastructure.exporters.file_exporter import FileExporter
from pytest_beacon.infrastructure.exporters.http_exporter import HttpExporter
from pytest_beacon.infrastructure.formatters.ctrf import build_ctrf_report
from pytest_beacon.infrastructure.observability.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------


class BeaconPlugin:
    """Collects test results and exports a CTRF report at session end."""

    def __init__(self, config: pytest.Config) -> None:
        self._config = config
        self._settings = get_settings()
        self._run = TestRun()
        self._processed_tests: set[str] = set()
        self._processed_collection_errors: set[str] = set()

        # CLI options override settings
        self._fmt: str = config.getoption(
            "--beacon-format", default=self._settings.report_format
        )
        self._verbose: bool = config.getoption(
            "--beacon-verbose", default=self._settings.verbose
        )
        exclude_raw: str = config.getoption(
            "--beacon-exclude-status", default=self._settings.exclude_statuses
        )
        self._excluded: set[str] = {
            s.strip() for s in exclude_raw.split(",") if s.strip()
        }
        self._meta: dict[str, str] = _parse_meta(
            config.getoption("--beacon-meta", default=[])
        )

        log.debug(
            "beacon: plugin initialised",
            fmt=self._fmt,
            verbose=self._verbose,
            excluded=list(self._excluded),
            meta=self._meta,
        )

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    @pytest.hookimpl
    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        """Capture collection errors (import errors, syntax errors, etc.)."""
        if report.outcome not in ("failed", "error"):
            return
        try:
            nodeid = getattr(report, "nodeid", None)
            if not nodeid:
                return
            # Deduplicate by file path — one error entry per file
            file_path = nodeid.split("::")[0]
            if file_path in self._processed_collection_errors:
                return
            self._processed_collection_errors.add(file_path)

            result = TestResult(
                nodeid=nodeid,
                name=nodeid.split("::")[-1] if "::" in nodeid else nodeid,
                status=TestStatus.ERROR,
                duration_ms=0.0,
                file_path=file_path,
                message=_extract_error_message(
                    report, getattr(report, "excinfo", None)
                ),
                trace=_truncate_traceback(str(report.longrepr))
                if getattr(report, "longrepr", None)
                else None,
                failure_location=_failure_location(getattr(report, "excinfo", None)),
            )
            self._run.update_summary_only(TestStatus.ERROR)
            if TestStatus.ERROR.value not in self._excluded:
                self._run._tests.append(result)
        except Exception:
            log.exception(
                "beacon: error in pytest_collectreport",
                nodeid=getattr(report, "nodeid", "?"),
            )

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(
        self, item: pytest.Item, call: pytest.CallInfo
    ) -> Any:
        outcome = yield
        report: pytest.TestReport = outcome.get_result()

        try:
            should_process = report.when == "call" or (
                report.when == "setup"
                and report.outcome in ("skipped", "failed", "error")
            )
            is_new = report.when == "call" or item.nodeid not in self._processed_tests

            if not (should_process and is_new):
                return

            self._processed_tests.add(item.nodeid)

            status = _map_outcome(report)
            excinfo = getattr(report, "excinfo", None)

            # Duration
            duration_ms = 0.0
            if report.when == "call":
                dur = getattr(report, "duration", None) or getattr(
                    call, "duration", None
                )
                if dur is not None:
                    duration_ms = round(dur * 1000, 3)

            result = TestResult(
                nodeid=item.nodeid,
                name=item.name,
                status=status,
                duration_ms=duration_ms,
                start_time=datetime.now(timezone.utc),
                file_path=item.location[0] if hasattr(item, "location") else None,
                line=item.location[1] if hasattr(item, "location") else None,
                marks=_extract_marks(item),
                params=_extract_params(item),
                allure_id=_extract_allure_id(item),
            )

            if status in (TestStatus.FAILED, TestStatus.ERROR):
                result.message = _extract_error_message(report, excinfo)
                result.trace = (
                    _truncate_traceback(str(report.longrepr))
                    if getattr(report, "longrepr", None)
                    else None
                )
                result.failure_location = _failure_location(excinfo)
                if excinfo and hasattr(excinfo, "typename"):
                    # Store exception type in message prefix for context
                    if result.message and excinfo.typename not in result.message:
                        result.message = f"{excinfo.typename}: {result.message}"
            elif status == TestStatus.SKIPPED:
                result.message = _extract_skip_reason(report)
            elif status == TestStatus.PASSED and self._verbose:
                result.stdout = (getattr(report, "capstdout", None) or "")[
                    :1000
                ] or None
                result.stderr = (getattr(report, "capstderr", None) or "")[
                    :1000
                ] or None

            self._run.update_summary_only(status)
            if status.value not in self._excluded:
                self._run._tests.append(result)

        except Exception:
            log.exception(
                "beacon: error in pytest_runtest_makereport",
                nodeid=getattr(item, "nodeid", "?"),
            )

    def pytest_testnodedown(self, node: Any, error: Any) -> None:
        """Merge results from a finished xdist worker."""
        try:
            raw_tests = _xdist.collect_from_worker(node)
            if raw_tests:
                self._run.merge_worker_results(
                    raw_tests, self._excluded, self._processed_collection_errors
                )
        except Exception:
            log.exception(
                "beacon: error in pytest_testnodedown",
                worker=getattr(node, "workerid", "?"),
            )

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        """Finalise the run and export the report."""
        try:
            if _xdist.is_worker(session):
                _xdist.send_to_master(
                    self._config,
                    [r.model_dump(mode="json") for r in self._run.tests],
                )
                return

            self._run.finalize()
            report = build_ctrf_report(
                self._run,
                excluded_statuses=self._excluded,
                xdist_workers=_xdist.get_worker_count(self._config),
                extra_meta=self._meta or None,
            )

            file_path = self._config.getoption(
                "--beacon-file", default=self._settings.report_file
            )
            url = self._config.getoption(
                "--beacon-url", default=self._settings.report_url
            )

            exporters = []
            if url:
                exporters.append(
                    HttpExporter(
                        url,
                        self._settings.http_timeout,
                        self._settings.http_max_retries,
                    )
                )
            if not url or file_path:
                # Always write a local file unless only a URL is configured and no explicit file
                exporters.append(FileExporter(file_path, self._fmt))

            for exporter in exporters:
                exporter.export(report)

        except Exception:
            log.exception("beacon: error in pytest_sessionfinish")


# ---------------------------------------------------------------------------
# Module-level hooks (called before plugin instance exists)
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    _options.add_options(parser)


def pytest_configure(config: pytest.Config) -> None:
    """Register the plugin instance when --beacon is active."""
    try:
        enabled = config.getoption("--beacon", default=False)
    except ValueError:
        enabled = False

    if not enabled:
        return

    plugin_name = "beacon_instance"
    if not config.pluginmanager.hasplugin(plugin_name):
        config.pluginmanager.register(BeaconPlugin(config), plugin_name)


# ---------------------------------------------------------------------------
# Extraction helpers (pure functions, no pytest-specific state)
# ---------------------------------------------------------------------------


def _map_outcome(report: pytest.TestReport) -> TestStatus:
    if report.when == "setup" and report.outcome == "failed":
        return TestStatus.ERROR
    mapping = {
        "passed": TestStatus.PASSED,
        "failed": TestStatus.FAILED,
        "skipped": TestStatus.SKIPPED,
        "error": TestStatus.ERROR,
    }
    return mapping.get(report.outcome, TestStatus.OTHER)


def _extract_error_message(report: Any, excinfo: Any) -> str:
    if excinfo and hasattr(excinfo, "value") and excinfo.value:
        if excinfo.typename == "AssertionError" and getattr(
            excinfo.value, "args", None
        ):
            return str(excinfo.value.args[0])[:500]
        return str(excinfo.value)[:500]

    longrepr = getattr(report, "longrepr", None)
    if longrepr:
        lines = str(longrepr).split("\n")
        for line in lines:
            if line.strip().startswith(("E ", "E\t")):
                return line.strip()[2:].strip()[:500]
        for line in lines:
            if line.strip() and not line.strip().startswith((">", "def ", "class ")):
                return line.strip()[:500]
        return lines[0][:500] if lines else "Unknown error"

    return "Unknown error"


def _extract_skip_reason(report: Any) -> str:
    longrepr = getattr(report, "longrepr", None)
    if longrepr:
        text = str(longrepr)
        if "Skipped:" in text:
            return text.split("Skipped:")[-1].strip()[:200]
        return text[:200]
    if getattr(report, "wasxfail", None):
        return "Expected failure"
    return "Test was skipped"


def _truncate_traceback(text: str) -> str:
    lines = text.split("\n")
    if len(lines) > 20:
        return "\n".join([*lines[:10], "...", *lines[-10:]])
    return text


def _failure_location(excinfo: Any) -> dict[str, Any] | None:
    if excinfo and hasattr(excinfo, "traceback") and excinfo.traceback:
        entry = excinfo.traceback[-1]
        return {"file": str(entry.path), "line": entry.lineno}
    return None


def _extract_marks(item: pytest.Item) -> list[str]:
    try:
        return [mark.name for mark in item.iter_markers()]
    except Exception:
        return []


def _extract_params(item: pytest.Item) -> dict[str, Any]:
    try:
        if not hasattr(item, "callspec"):
            return {}
        return {k: _sanitize_param(v) for k, v in item.callspec.params.items()}
    except Exception:
        return {}


def _sanitize_param(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return [_sanitize_param(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _sanitize_param(v) for k, v in value.items()}
    return str(value)


def _extract_allure_id(item: pytest.Item) -> str | None:
    try:
        for mark in item.iter_markers():
            if mark.name in ("allure_id", "allure.id", "id"):
                if mark.args:
                    return str(mark.args[0])
    except Exception:
        pass
    return None


def _parse_meta(raw: list[str]) -> dict[str, str]:
    """Parse a list of 'KEY=VALUE' strings into a dict. Malformed entries are skipped."""
    result: dict[str, str] = {}
    for entry in raw or []:
        if "=" in entry:
            key, _, value = entry.partition("=")
            key = key.strip()
            if key:
                result[key] = value
    return result
