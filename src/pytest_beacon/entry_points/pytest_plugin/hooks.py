"""
pytest-beacon plugin: hook implementations and plugin registration.

Entry point registered in pyproject.toml as:
    [project.entry-points.pytest11]
    beacon = "pytest_beacon.entry_points.pytest_plugin.hooks"
"""

from __future__ import annotations

import logging
import re
from importlib import import_module
from datetime import datetime, timezone
from typing import Any

import pytest

from pytest_beacon.config.settings import get_settings
from pytest_beacon.domains.test_run.entities import TestResult, TestRun
from pytest_beacon.domains.test_run.value_objects import (
    ConsolePhaseOutput,
    ConsoleStream,
    LogEntry,
    TestConsoleOutput,
    TestLogs,
    TestStatus,
)
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
        self._result_statuses: dict[str, TestStatus] = {}
        self._result_indexes: dict[str, int] = {}

        # CLI options override settings
        self._fmt: str = config.getoption(
            "--beacon-format", default=self._settings.report_format
        )
        self._verbose: bool = config.getoption(
            "--beacon-verbose", default=self._settings.verbose
        )
        exclude_raw: str = config.getoption(
            "--beacon-file-exclude-status", default=self._settings.file_exclude_statuses
        )
        self._file_excluded: set[str] = {
            s.strip() for s in exclude_raw.split(",") if s.strip()
        }
        http_exclude_raw: str | None = config.getoption(
            "--beacon-http-exclude-status", default=None
        )
        if http_exclude_raw is None:
            http_exclude_raw = self._settings.http_exclude_statuses
        self._http_excluded: set[str] = {
            s.strip() for s in http_exclude_raw.split(",") if s.strip()
        }
        # Only skip storing a test result if excluded from BOTH outputs
        self._storage_excluded: set[str] = self._file_excluded & self._http_excluded
        self._meta: dict[str, str] = _parse_meta(
            config.getoption("--beacon-meta", default=[])
        )

        # Log capture settings
        self._logs_enabled: bool = config.getoption(
            "--beacon-logs", default=self._settings.logs_enabled
        )
        logs_level_str: str = config.getoption(
            "--beacon-logs-level", default=self._settings.logs_level
        )
        self._logs_min_level: int = getattr(
            logging, logs_level_str.upper(), logging.WARNING
        )
        logs_max_raw = config.getoption(
            "--beacon-logs-max", default=self._settings.logs_max_per_category
        )
        self._logs_max_per_category: int | None = (
            int(logs_max_raw) if logs_max_raw is not None else None
        )
        # Accumulates per-phase log entries keyed by nodeid then phase name
        self._pending_logs: dict[str, dict[str, list[LogEntry]]] = {}
        self._pending_console: dict[str, dict[str, ConsolePhaseOutput]] = {}
        self._active_nodeid: str | None = None
        self._active_phase: str | None = None
        self._stdlib_log_handler: _DirectLogHandler | None = None
        self._loguru_sink_id: int | None = None
        self._loguru_logger: Any | None = None

        self._console_enabled: bool = config.getoption(
            "--beacon-console-output", default=self._settings.console_output_enabled
        )
        self._console_lines: int = max(
            0,
            int(
                config.getoption(
                    "--beacon-console-lines",
                    default=self._settings.console_output_lines,
                )
            ),
        )

        # Handler installed on the root logger during the collection phase
        self._collection_log_handler: _CollectionLogHandler | None = None
        if self._logs_enabled:
            self._collection_log_handler = _CollectionLogHandler(self._logs_min_level)
            logging.root.addHandler(self._collection_log_handler)
            self._stdlib_log_handler = _DirectLogHandler(
                self._logs_min_level,
                self._capture_direct_log_record,
            )
            logging.root.addHandler(self._stdlib_log_handler)

        log.debug(
            "beacon: plugin initialised",
            fmt=self._fmt,
            verbose=self._verbose,
            file_excluded=list(self._file_excluded),
            http_excluded=list(self._http_excluded),
            meta=self._meta,
        )

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------

    @pytest.hookimpl
    def pytest_collection_finish(self, session: pytest.Session) -> None:  # noqa: ARG002
        """Finalise general log capture after the collection phase completes."""
        if not self._logs_enabled or self._collection_log_handler is None:
            return
        logging.root.removeHandler(self._collection_log_handler)
        records = self._collection_log_handler.records
        self._collection_log_handler = None
        entries: list[LogEntry] = [
            _log_entry_from_stdlib_record(r)
            for r in records
        ]
        if self._logs_max_per_category is not None:
            entries = (
                entries[-self._logs_max_per_category :]
                if self._logs_max_per_category > 0
                else []
            )
        if entries:
            self._run.add_general_logs(entries)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_setup(self, item: pytest.Item) -> Any:
        self._enter_test_phase(item, "setup")
        try:
            yield
        finally:
            self._leave_test_phase()

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item: pytest.Item) -> Any:
        self._enter_test_phase(item, "call")
        try:
            yield
        finally:
            self._leave_test_phase()

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_teardown(self, item: pytest.Item) -> Any:
        self._enter_test_phase(item, "teardown")
        try:
            yield
        finally:
            self._leave_test_phase()

    @pytest.hookimpl
    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        """Capture collection errors."""
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
            if TestStatus.ERROR.value not in self._storage_excluded:
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
        try:
            outcome = yield
            report: pytest.TestReport = outcome.get_result()
        except Exception as exc:
            self._record_fallback_from_call(item, call, exc)
            return

        try:
            # Always capture logs for this phase if log capture is enabled
            if self._logs_enabled and report.when in ("setup", "call", "teardown"):
                parsed_logs = _parse_log_sections_from_sections(
                    getattr(report, "sections", []),
                    report.when,
                    self._logs_min_level,
                    self._logs_max_per_category,
                )
                direct_logs = self._pending_logs.get(item.nodeid, {}).get(
                    report.when, []
                )
                phase_logs = _merge_log_entries(
                    direct_logs, parsed_logs, self._logs_max_per_category
                )
                self._pending_logs.setdefault(item.nodeid, {})[report.when] = phase_logs

            if self._console_enabled and report.when in ("setup", "call", "teardown"):
                self._pending_console.setdefault(item.nodeid, {})[
                    report.when
                ] = _extract_console_output(report, self._console_lines)

            should_process = (
                report.when == "call"
                or (
                    report.when == "setup"
                    and report.outcome in ("skipped", "failed", "error")
                )
                or (
                    report.when == "teardown"
                    and report.outcome in ("failed", "error")
                )
            )
            previous_status = self._result_statuses.get(item.nodeid)
            is_new = report.when == "call" or item.nodeid not in self._processed_tests
            is_teardown_override = (
                report.when == "teardown"
                and report.outcome in ("failed", "error")
                and previous_status == TestStatus.PASSED
            )

            # For a successful teardown, patch teardown logs onto the already-stored result
            if (
                (self._logs_enabled or self._console_enabled)
                and report.when == "teardown"
                and not should_process
            ):
                index = self._result_indexes.get(item.nodeid)
                if index is not None and index < len(self._run._tests):
                    stored = self._run._tests[index]
                    update: dict[str, Any] = {}
                    if stored.logs is not None:
                        teardown_logs = (
                            self._pending_logs.get(item.nodeid, {}).get("teardown", [])
                        )
                        update["logs"] = stored.logs.model_copy(
                            update={"teardown": teardown_logs}
                        )
                    if stored.console_output is not None:
                        teardown_console = self._pending_console.get(
                            item.nodeid, {}
                        ).get("teardown")
                        update["console_output"] = stored.console_output.model_copy(
                            update={"teardown": teardown_console}
                        )
                    if update:
                        self._run._tests[index] = stored.model_copy(update=update)

            if not (should_process and (is_new or is_teardown_override)):
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

            if self._logs_enabled:
                pending = self._pending_logs.get(item.nodeid, {})
                result.logs = TestLogs(
                    setup=pending.get("setup", []),
                    call=pending.get("call", []),
                    teardown=pending.get("teardown", []),
                )
            if self._console_enabled:
                pending_console = self._pending_console.get(item.nodeid, {})
                result.console_output = TestConsoleOutput(
                    setup=pending_console.get("setup"),
                    call=pending_console.get("call"),
                    teardown=pending_console.get("teardown"),
                )

            self._store_result(item.nodeid, result)

        except Exception:
            log.exception(
                "beacon: error in pytest_runtest_makereport",
                nodeid=getattr(item, "nodeid", "?"),
            )

    def pytest_testnodedown(self, node: Any, error: Any) -> None:
        """Merge results from a finished xdist worker."""
        try:
            payload = _xdist.collect_from_worker(node)
            raw_tests = payload.get("tests", [])
            summary = payload.get("summary", {})
            if raw_tests or summary:
                self._run.merge_worker_results(
                    raw_tests,
                    self._storage_excluded,
                    self._processed_collection_errors,
                    worker_summary=summary,
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
                    self._run.summary,
                )
                return

            self._run.finalize()
            file_path = self._config.getoption(
                "--beacon-file", default=self._settings.report_file
            )
            url = self._config.getoption(
                "--beacon-url", default=self._settings.report_url
            )
            xdist_workers = _xdist.get_worker_count(self._config)

            if url:
                pytest_summary = _extract_pytest_summary(self._config)
                http_report = build_ctrf_report(
                    self._run,
                    plugin_version=self._settings.app_version,
                    excluded_statuses=self._http_excluded,
                    xdist_workers=xdist_workers,
                    extra_meta=self._meta or None,
                    pytest_summary=pytest_summary,
                )
                HttpExporter(
                    url,
                    self._settings.http_timeout,
                    self._settings.http_max_retries,
                ).export(http_report)

            if not url or file_path:
                # Always write a local file unless only a URL is configured and no explicit file path
                pytest_summary = _extract_pytest_summary(self._config)
                file_report = build_ctrf_report(
                    self._run,
                    plugin_version=self._settings.app_version,
                    excluded_statuses=self._file_excluded,
                    xdist_workers=xdist_workers,
                    extra_meta=self._meta or None,
                    pytest_summary=pytest_summary,
                )
                FileExporter(file_path, self._fmt).export(file_report)

        except Exception:
            log.exception("beacon: error in pytest_sessionfinish")

    def pytest_unconfigure(self, config: pytest.Config) -> None:  # noqa: ARG002
        """Remove logging hooks installed by the plugin."""
        if self._stdlib_log_handler is not None:
            try:
                logging.root.removeHandler(self._stdlib_log_handler)
            except Exception:
                pass
            self._stdlib_log_handler = None
        self._remove_loguru_sink()

    def _enter_test_phase(self, item: pytest.Item, phase: str) -> None:
        self._active_nodeid = item.nodeid
        self._active_phase = phase
        if self._logs_enabled:
            self._install_loguru_sink()

    def _leave_test_phase(self) -> None:
        if self._logs_enabled:
            self._remove_loguru_sink()
        self._active_nodeid = None
        self._active_phase = None

    def _capture_direct_log_record(self, record: logging.LogRecord) -> None:
        if (
            not self._logs_enabled
            or self._active_nodeid is None
            or self._active_phase is None
        ):
            return
        if record.name.startswith("pytest_beacon"):
            return
        self._pending_logs.setdefault(self._active_nodeid, {}).setdefault(
            self._active_phase, []
        ).append(_log_entry_from_stdlib_record(record))

    def _capture_loguru_message(self, message: Any) -> None:
        if (
            not self._logs_enabled
            or self._active_nodeid is None
            or self._active_phase is None
        ):
            return
        record = getattr(message, "record", None)
        if not isinstance(record, dict):
            return
        level = record.get("level")
        level_name = getattr(level, "name", str(level))
        level_no = getattr(level, "no", _LOGURU_LEVELS.get(level_name, 0))
        if level_no < self._logs_min_level:
            return
        self._pending_logs.setdefault(self._active_nodeid, {}).setdefault(
            self._active_phase, []
        ).append(_log_entry_from_loguru_record(record))

    def _install_loguru_sink(self) -> None:
        if self._loguru_sink_id is not None:
            return
        try:
            loguru_logger = import_module("loguru").logger
        except Exception:
            return
        try:
            self._loguru_logger = loguru_logger
            self._loguru_sink_id = loguru_logger.add(
                self._capture_loguru_message,
                level=0,
                enqueue=False,
                catch=True,
            )
        except Exception:
            self._loguru_sink_id = None
            self._loguru_logger = None

    def _remove_loguru_sink(self) -> None:
        if self._loguru_logger is None or self._loguru_sink_id is None:
            return
        try:
            self._loguru_logger.remove(self._loguru_sink_id)
        except Exception:
            pass
        self._loguru_sink_id = None
        self._loguru_logger = None

    def _record_fallback_from_call(
        self,
        item: pytest.Item,
        call: pytest.CallInfo,
        exc: Exception,
    ) -> None:
        """Best-effort reporting when makereport hookwrapper teardown raises."""
        try:
            should_process = (
                call.when == "call"
                or (call.when == "setup" and bool(getattr(call, "excinfo", None)))
                or (call.when == "teardown" and bool(getattr(call, "excinfo", None)))
            )
            previous_status = self._result_statuses.get(item.nodeid)
            is_new = call.when == "call" or item.nodeid not in self._processed_tests
            is_teardown_override = (
                call.when == "teardown"
                and bool(getattr(call, "excinfo", None))
                and previous_status == TestStatus.PASSED
            )
            if not (should_process and (is_new or is_teardown_override)):
                return

            self._processed_tests.add(item.nodeid)
            status = _map_call_to_status(call)
            duration_ms = round((getattr(call, "duration", 0.0) or 0.0) * 1000, 3)

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

            excinfo = getattr(call, "excinfo", None)
            if excinfo and status in (TestStatus.FAILED, TestStatus.ERROR):
                result.message = str(excinfo.value)[:500] if excinfo.value else str(exc)
                result.trace = _truncate_traceback(str(excinfo.traceback))
                result.failure_location = _failure_location(excinfo)
            elif status == TestStatus.SKIPPED:
                result.message = "Test was skipped"

            self._store_result(item.nodeid, result)

            log.exception(
                "beacon: recovered from makereport hookwrapper exception",
                nodeid=getattr(item, "nodeid", "?"),
                when=getattr(call, "when", "?"),
            )
        except Exception:
            log.exception(
                "beacon: failed to record fallback result",
                nodeid=getattr(item, "nodeid", "?"),
            )

    def _store_result(self, nodeid: str, result: TestResult) -> None:
        """Store a test result, replacing an earlier passed outcome when needed."""
        previous_status = self._result_statuses.get(nodeid)
        if previous_status is None:
            self._run.update_summary_only(result.status)
            if result.status.value not in self._storage_excluded:
                self._result_indexes[nodeid] = len(self._run._tests)
                self._run._tests.append(result)
            self._result_statuses[nodeid] = result.status
            return

        if previous_status == result.status:
            return

        self._decrement_summary(previous_status)
        self._run.update_summary_only(result.status)
        self._result_statuses[nodeid] = result.status

        index = self._result_indexes.get(nodeid)
        if index is not None:
            if result.status.value in self._storage_excluded:
                del self._run._tests[index]
                del self._result_indexes[nodeid]
                for stored_nodeid, stored_index in list(self._result_indexes.items()):
                    if stored_index > index:
                        self._result_indexes[stored_nodeid] = stored_index - 1
            else:
                self._run._tests[index] = result
        elif result.status.value not in self._storage_excluded:
            self._result_indexes[nodeid] = len(self._run._tests)
            self._run._tests.append(result)

    def _decrement_summary(self, status: TestStatus) -> None:
        self._run._summary["tests"] -= 1
        key = status.value if status.value in ("passed", "failed", "skipped", "error", "other") else "other"
        self._run._summary[key] -= 1


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


def _map_call_to_status(call: pytest.CallInfo) -> TestStatus:
    if call.when == "setup":
        return TestStatus.ERROR if getattr(call, "excinfo", None) else TestStatus.OTHER
    if call.when == "call":
        return TestStatus.FAILED if getattr(call, "excinfo", None) else TestStatus.PASSED
    if call.when == "teardown":
        return TestStatus.FAILED if getattr(call, "excinfo", None) else TestStatus.OTHER
    return TestStatus.OTHER


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
        seen: set[str] = set()
        result: list[str] = []
        for mark in item.iter_markers():
            if mark.name not in seen:
                seen.add(mark.name)
                result.append(mark.name)
        return result
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


def _extract_pytest_summary(config: pytest.Config) -> dict[str, int] | None:
    """Extract pytest terminal-summary style counters from terminalreporter stats."""
    terminalreporter = config.pluginmanager.get_plugin("terminalreporter")
    if terminalreporter is None:
        return None

    stats = getattr(terminalreporter, "stats", None)
    if not stats:
        return None

    aliases = {
        "errors": "error",
        "warnings": "warnings",
        "warning": "warnings",
        "rerun": "rerun",
        "reruns": "rerun",
    }
    ordered_keys = (
        "failed",
        "passed",
        "skipped",
        "deselected",
        "xfailed",
        "xpassed",
        "warnings",
        "error",
        "rerun",
    )

    summary: dict[str, int] = {key: 0 for key in ordered_keys}
    for raw_key, values in stats.items():
        key = aliases.get(raw_key, raw_key)
        if key in summary:
            summary[key] = len(values)

    return summary


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


# ---------------------------------------------------------------------------
# Collection-phase log capture
# ---------------------------------------------------------------------------


class _CollectionLogHandler(logging.Handler):
    """Captures log records emitted during the pytest collection phase."""

    def __init__(self, min_level: int) -> None:
        super().__init__(level=min_level)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class _DirectLogHandler(logging.Handler):
    """Forwards stdlib log records emitted during an active test phase."""

    def __init__(self, min_level: int, callback: Any) -> None:
        super().__init__(level=min_level)
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        self._callback(record)


# ---------------------------------------------------------------------------
# Log capture helpers
# ---------------------------------------------------------------------------

# Matches the default pytest log format:
# %(levelname)-8s %(name)s:%(filename)s:%(lineno)d %(message)s
# Example: "WARNING  mylogger:test_file.py:42 Something went wrong"
_LOG_LINE_RE = re.compile(
    r"^(?P<level>[A-Z]+)\s+"
    r"(?P<logger>[^:]+):"
    r"[^:]+:"      # filename (ignored)
    r"\d+\s+"      # lineno + whitespace (ignored)
    r"(?P<message>.*)$"
)

_PHASE_LOG_SECTION_TITLES = {
    "setup": "captured log setup",
    "call": "captured log call",
    "teardown": "captured log teardown",
}

_PHASE_STREAM_SECTION_TITLES = {
    "setup": ("captured stdout setup", "captured stderr setup"),
    "call": ("captured stdout call", "captured stderr call"),
    "teardown": ("captured stdout teardown", "captured stderr teardown"),
}

_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

# Matches loguru's common console shape used by qa_tests:
# 2026-05-08 15:00:00.123 | WARNING  | package.module:function:42 - message
_LOGURU_LINE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}\s+"
    r"\d{2}:\d{2}:\d{2}(?:\.\d+)?\s+\|\s+"
    r"(?P<level>[A-Z]+)\s+\|\s+"
    r"(?P<logger>.*?)\s+-\s+"
    r"(?P<message>.*)$"
)

_LOGURU_LEVELS = {
    "TRACE": 5,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "SUCCESS": 25,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_STDLIB_LOG_RECORD_BUILTINS = set(logging.makeLogRecord({}).__dict__)


def _parse_log_sections_from_sections(
    sections: list[tuple[str, str]],
    phase: str,
    min_level: int,
    max_entries: int | None,
) -> list[LogEntry]:
    """Extract log entries from pytest report sections for the given *phase*.

    Pytest stores stdlib logging in "Captured log ..." sections, while projects
    using loguru often emit formatted log lines to stdout/stderr. Capture both
    shapes and leave unrelated print output alone.
    """
    entries: list[LogEntry] = []
    expected_log = _PHASE_LOG_SECTION_TITLES.get(phase, "")
    expected_streams = _PHASE_STREAM_SECTION_TITLES.get(phase, ())

    for title, content in sections:
        if not content:
            continue
        title_lower = title.lower()
        if expected_log and title_lower == expected_log:
            entries.extend(_parse_log_text(content, min_level, None))
        elif title_lower in expected_streams:
            entries.extend(_parse_stream_log_text(content, min_level, None))

    if max_entries is not None:
        entries = entries[-max_entries:] if max_entries > 0 else []
    return entries


def _parse_log_text(
    text: str, min_level: int, max_entries: int | None
) -> list[LogEntry]:
    """Parse a captured log text block into a list of :class:`LogEntry` objects.

    Lines that do not match the default pytest log format are silently skipped.
    """
    entries: list[LogEntry] = []
    for line in text.splitlines():
        stripped = line.rstrip()
        if not stripped:
            continue
        m = _LOG_LINE_RE.match(stripped)
        if not m:
            continue
        level = m.group("level")
        numeric_level = getattr(logging, level, None)
        if numeric_level is None or numeric_level < min_level:
            continue
        entries.append(
            LogEntry(
                level=level,
                message=m.group("message"),
                logger=m.group("logger").strip(),
            )
        )
    if max_entries is not None:
        entries = entries[-max_entries:] if max_entries > 0 else []
    return entries


def _parse_stream_log_text(
    text: str, min_level: int, max_entries: int | None
) -> list[LogEntry]:
    """Parse log-like lines from captured stdout/stderr text."""
    entries: list[LogEntry] = []
    for line in text.splitlines():
        stripped = _ANSI_RE.sub("", line).rstrip()
        if not stripped:
            continue
        m = _LOGURU_LINE_RE.match(stripped)
        if not m:
            continue
        level = m.group("level")
        numeric_level = _LOGURU_LEVELS.get(level)
        if numeric_level is None or numeric_level < min_level:
            continue
        entries.append(
            LogEntry(
                level=level,
                message=m.group("message").strip(),
                logger=m.group("logger").strip(),
            )
        )
    if max_entries is not None:
        entries = entries[-max_entries:] if max_entries > 0 else []
    return entries


def _merge_log_entries(
    direct_logs: list[LogEntry],
    parsed_logs: list[LogEntry],
    max_entries: int | None,
) -> list[LogEntry]:
    """Merge direct and parsed log entries, keeping direct records authoritative."""
    result = list(direct_logs)
    seen = {_log_identity(entry) for entry in result}
    direct_messages = {(entry.level, entry.message) for entry in result}
    for entry in parsed_logs:
        if (entry.level, entry.message) in direct_messages:
            continue
        identity = _log_identity(entry)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(entry)
    if max_entries is not None:
        result = result[-max_entries:] if max_entries > 0 else []
    return result


def _log_identity(entry: LogEntry) -> tuple[str, str, str]:
    return (entry.level, entry.logger, entry.message)


def _log_entry_from_stdlib_record(record: logging.LogRecord) -> LogEntry:
    data = {
        "name": record.name,
        "pathname": record.pathname,
        "filename": record.filename,
        "module": record.module,
        "lineno": record.lineno,
        "funcName": record.funcName,
        "process": record.process,
        "processName": record.processName,
        "thread": record.thread,
        "threadName": record.threadName,
        "created": record.created,
        "msecs": record.msecs,
        "relativeCreated": record.relativeCreated,
        "levelno": record.levelno,
        "excInfo": _safe_string(record.exc_info) if record.exc_info else None,
        "stackInfo": record.stack_info,
        "extra": {
            key: _json_safe(value)
            for key, value in record.__dict__.items()
            if key not in _STDLIB_LOG_RECORD_BUILTINS
        },
    }
    return LogEntry(
        level=record.levelname,
        message=record.getMessage(),
        logger=record.name,
        timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
        data={key: value for key, value in data.items() if value not in (None, {})},
    )


def _log_entry_from_loguru_record(record: dict[str, Any]) -> LogEntry:
    level = record.get("level")
    time_value = record.get("time")
    file_value = record.get("file")
    process_value = record.get("process")
    thread_value = record.get("thread")
    exception_value = record.get("exception")
    data = {
        "name": record.get("name"),
        "function": record.get("function"),
        "module": record.get("module"),
        "line": record.get("line"),
        "file": _object_attrs(file_value, ("name", "path")),
        "process": _object_attrs(process_value, ("id", "name")),
        "thread": _object_attrs(thread_value, ("id", "name")),
        "level": _object_attrs(level, ("name", "no", "icon")),
        "elapsed": _safe_string(record.get("elapsed")),
        "exception": _safe_string(exception_value) if exception_value else None,
        "extra": _json_safe(record.get("extra", {})),
    }
    timestamp = time_value.isoformat() if hasattr(time_value, "isoformat") else None
    return LogEntry(
        level=getattr(level, "name", str(level)),
        message=str(record.get("message", "")),
        logger=str(record.get("name") or ""),
        timestamp=timestamp,
        data={key: value for key, value in data.items() if value not in (None, {})},
    )


def _object_attrs(value: Any, attrs: tuple[str, ...]) -> dict[str, Any] | None:
    if value is None:
        return None
    result = {
        attr: _json_safe(getattr(value, attr))
        for attr in attrs
        if hasattr(value, attr)
    }
    return result or None


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return _safe_string(value)


def _safe_string(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return repr(value)


def _extract_console_output(report: pytest.TestReport, line_limit: int) -> ConsolePhaseOutput:
    phase = getattr(report, "when", "")
    stdout = _extract_stream_output(getattr(report, "sections", []), phase, "stdout", line_limit)
    stderr = _extract_stream_output(getattr(report, "sections", []), phase, "stderr", line_limit)
    return ConsolePhaseOutput(stdout=stdout, stderr=stderr)


def _extract_stream_output(
    sections: list[tuple[str, str]],
    phase: str,
    stream_name: str,
    line_limit: int,
) -> ConsoleStream | None:
    expected = f"captured {stream_name} {phase}"
    content_parts = [
        content
        for title, content in sections
        if title.lower() == expected and content
    ]
    if not content_parts:
        return None
    lines = "\n".join(content_parts).splitlines()
    omitted = max(0, len(lines) - line_limit)
    if line_limit <= 0:
        retained: list[str] = []
    else:
        retained = lines[-line_limit:]
    return ConsoleStream(
        lines=retained,
        truncated=omitted > 0,
        omitted_lines=omitted,
    )
