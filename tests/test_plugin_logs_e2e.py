"""End-to-end integration tests for the pytest-beacon log capture feature.

Covers:
- Basic opt-in behaviour (--beacon-logs flag)
- Per-phase log entries (setup / call / teardown)
- General logs from the collection phase
- Log level filtering (--beacon-logs-level)
- Max-entries cap (--beacon-logs-max)
- Structured log entry format (level, message, logger fields)
- Interaction with status-exclusion settings
- Edge cases: no logs emitted, empty phases, logs disabled by default,
  multiple tests with independent log sets, parametrized tests
- HTTP export: test_logs field present/absent, level filtering, max cap, no flag
- xdist compatibility
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json_report(pytester):
    reports = list(pytester.path.glob("beacon_reports/*.json"))
    assert reports, "No JSON report generated in beacon_reports/"
    return json.loads(reports[0].read_text())


def _results(report):
    return report["results"]


def _tests(report):
    return _results(report)["tests"]


def _extra(report):
    return _results(report)["extra"]


# ---------------------------------------------------------------------------
# Feature disabled by default
# ---------------------------------------------------------------------------


class TestLogsDisabledByDefault:
    def test_no_logs_key_without_flag(self, pytester):
        """Without --beacon-logs the 'logs' key must not appear on any test."""
        pytester.makepyfile("""
            import logging
            def test_with_log():
                logging.warning("should not appear")
        """)
        pytester.runpytest("--beacon", "--beacon-file-exclude-status=")
        data = _load_json_report(pytester)
        for t in _tests(data):
            assert "logs" not in t

    def test_no_general_logs_key_without_flag(self, pytester):
        """Without --beacon-logs the 'generalLogs' key must not appear in extra."""
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-file-exclude-status=")
        data = _load_json_report(pytester)
        assert "generalLogs" not in _extra(data)


# ---------------------------------------------------------------------------
# Basic opt-in
# ---------------------------------------------------------------------------


class TestLogsOptIn:
    def test_logs_key_present_when_flag_set(self, pytester):
        """With --beacon-logs each test entry must carry a 'logs' key."""
        pytester.makepyfile("""
            import logging
            def test_something():
                logging.warning("a warning")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING")
        data = _load_json_report(pytester)
        tests = _tests(data)
        assert len(tests) == 1
        assert "logs" in tests[0]

    def test_logs_object_has_phase_keys(self, pytester):
        """The 'logs' object must only contain non-empty phase keys."""
        pytester.makepyfile("""
            import logging
            def test_emits():
                logging.warning("call-phase warning")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "-p", "no:warnings")
        data = _load_json_report(pytester)
        logs = _tests(data)[0]["logs"]
        # All keys that are present must be valid phase names
        assert set(logs.keys()) <= {"setup", "call", "teardown"}

    def test_call_phase_log_entry_fields(self, pytester):
        """Each log entry must contain at least 'level' and 'message'."""
        pytester.makepyfile("""
            import logging
            def test_log_fields():
                logging.getLogger("myapp.module").warning("check fields")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        logs = _tests(data)[0].get("logs", {})
        call_logs = logs.get("call", [])
        assert call_logs, "Expected at least one call-phase log entry"
        entry = call_logs[0]
        assert "level" in entry
        assert "message" in entry
        assert entry["level"] == "WARNING"
        assert "check fields" in entry["message"]

    def test_logger_name_captured(self, pytester):
        """The 'logger' field must reflect the logger name used."""
        pytester.makepyfile("""
            import logging
            def test_named_logger():
                logging.getLogger("specific.logger").warning("named")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        call_logs = _tests(data)[0].get("logs", {}).get("call", [])
        assert call_logs
        assert "specific.logger" in call_logs[0].get("logger", "")


# ---------------------------------------------------------------------------
# Per-phase capture
# ---------------------------------------------------------------------------


class TestPerPhaseLogCapture:
    def test_setup_phase_logs_captured(self, pytester):
        """Logs emitted inside a fixture (setup phase) go to 'setup' key."""
        pytester.makepyfile("""
            import logging
            import pytest

            @pytest.fixture
            def setup_logger():
                logging.getLogger("fixture").warning("setup warning")

            def test_uses_fixture(setup_logger):
                pass
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        logs = _tests(data)[0].get("logs", {})
        assert "setup" in logs
        messages = [e["message"] for e in logs["setup"]]
        assert any("setup warning" in m for m in messages)

    def test_call_phase_logs_captured(self, pytester):
        """Logs emitted in the test body go to 'call' key."""
        pytester.makepyfile("""
            import logging
            def test_call_log():
                logging.getLogger("call").warning("call warning")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        logs = _tests(data)[0].get("logs", {})
        assert "call" in logs
        messages = [e["message"] for e in logs["call"]]
        assert any("call warning" in m for m in messages)

    def test_teardown_phase_logs_captured(self, pytester):
        """Logs emitted during fixture teardown go to 'teardown' key."""
        pytester.makepyfile("""
            import logging
            import pytest

            @pytest.fixture
            def teardown_logger():
                yield
                logging.getLogger("td").warning("teardown warning")

            def test_uses_teardown(teardown_logger):
                pass
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        logs = _tests(data)[0].get("logs", {})
        assert "teardown" in logs
        messages = [e["message"] for e in logs["teardown"]]
        assert any("teardown warning" in m for m in messages)

    def test_empty_phase_not_included_in_logs(self, pytester):
        """A phase that produces no log entries must not appear in the 'logs' dict."""
        pytester.makepyfile("""
            import logging
            def test_only_call_log():
                logging.getLogger("only").warning("only call")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        logs = _tests(data)[0].get("logs", {})
        # 'setup' and 'teardown' had no log lines → must be absent
        assert "setup" not in logs
        assert "teardown" not in logs

    def test_logs_present_on_failed_test(self, pytester):
        """Log entries must still be captured when the test fails."""
        pytester.makepyfile("""
            import logging
            def test_failing():
                logging.getLogger("fail").warning("before assert")
                assert False, "intentional"
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        failed = [t for t in _tests(data) if t["status"] == "failed"]
        assert failed
        call_logs = failed[0].get("logs", {}).get("call", [])
        assert call_logs
        assert any("before assert" in e["message"] for e in call_logs)

    def test_logs_present_on_setup_error(self, pytester):
        """Log entries from a broken fixture (setup) are captured under 'setup'."""
        pytester.makepyfile("""
            import logging
            import pytest

            @pytest.fixture
            def broken():
                logging.getLogger("fix").warning("fixture log before error")
                raise RuntimeError("boom")

            def test_broken(broken):
                pass
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        errors = [t for t in _tests(data) if t["status"] == "error"]
        assert errors
        setup_logs = errors[0].get("logs", {}).get("setup", [])
        assert setup_logs
        assert any("fixture log before error" in e["message"] for e in setup_logs)

    def test_multiple_tests_have_independent_logs(self, pytester):
        """Each test must only hold its own log entries, not logs from other tests."""
        pytester.makepyfile("""
            import logging
            def test_alpha():
                logging.getLogger("t").warning("alpha log")
            def test_beta():
                logging.getLogger("t").warning("beta log")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        tests = _tests(data)
        alpha = next(t for t in tests if "alpha" in t["name"])
        beta = next(t for t in tests if "beta" in t["name"])

        alpha_messages = [e["message"] for e in alpha.get("logs", {}).get("call", [])]
        beta_messages = [e["message"] for e in beta.get("logs", {}).get("call", [])]

        assert any("alpha log" in m for m in alpha_messages)
        assert all("beta log" not in m for m in alpha_messages)
        assert any("beta log" in m for m in beta_messages)
        assert all("alpha log" not in m for m in beta_messages)

    def test_parametrized_tests_have_independent_logs(self, pytester):
        """Each parametrized variant must hold only its own log entries."""
        pytester.makepyfile("""
            import logging
            import pytest

            @pytest.mark.parametrize("val", ["first", "second"])
            def test_param(val):
                logging.getLogger("p").warning(f"log for {val}")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        tests = _tests(data)
        assert len(tests) == 2
        for t in tests:
            call_logs = t.get("logs", {}).get("call", [])
            assert len(call_logs) == 1  # exactly one entry per variant
            nodeid = t["name"]
            expected = "first" if "first" in nodeid else "second"
            assert f"log for {expected}" in call_logs[0]["message"]


# ---------------------------------------------------------------------------
# Log level filtering
# ---------------------------------------------------------------------------


class TestLogLevelFiltering:
    def test_default_level_warning_filters_info(self, pytester):
        """With default WARNING level, INFO logs must not appear in the report."""
        pytester.makepyfile("""
            import logging
            def test_mixed_levels():
                logging.getLogger("t").info("info message")
                logging.getLogger("t").warning("warning message")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--log-cli-level=DEBUG")
        data = _load_json_report(pytester)
        call_logs = _tests(data)[0].get("logs", {}).get("call", [])
        levels = [e["level"] for e in call_logs]
        assert "INFO" not in levels
        assert "WARNING" in levels

    def test_debug_level_captures_debug_messages(self, pytester):
        """With --beacon-logs-level=DEBUG, DEBUG-level logs must be captured."""
        pytester.makepyfile("""
            import logging
            def test_debug():
                logging.getLogger("t").debug("debug message")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=DEBUG", "--log-cli-level=DEBUG")
        data = _load_json_report(pytester)
        call_logs = _tests(data)[0].get("logs", {}).get("call", [])
        levels = [e["level"] for e in call_logs]
        assert "DEBUG" in levels

    def test_error_level_filters_warning(self, pytester):
        """With --beacon-logs-level=ERROR, WARNING logs must not appear."""
        pytester.makepyfile("""
            import logging
            def test_warn_and_error():
                logging.getLogger("t").warning("warn msg")
                logging.getLogger("t").error("error msg")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=ERROR", "--log-cli-level=DEBUG")
        data = _load_json_report(pytester)
        call_logs = _tests(data)[0].get("logs", {}).get("call", [])
        levels = [e["level"] for e in call_logs]
        assert "WARNING" not in levels
        assert "ERROR" in levels

    def test_critical_level_only_captures_critical(self, pytester):
        """With --beacon-logs-level=CRITICAL only CRITICAL records should appear."""
        pytester.makepyfile("""
            import logging
            def test_all_levels():
                log = logging.getLogger("t")
                log.debug("d")
                log.info("i")
                log.warning("w")
                log.error("e")
                log.critical("c")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=CRITICAL", "--log-cli-level=DEBUG")
        data = _load_json_report(pytester)
        call_logs = _tests(data)[0].get("logs", {}).get("call", [])
        levels = {e["level"] for e in call_logs}
        assert levels <= {"CRITICAL"}

    def test_no_logs_below_minimum_level_leaves_no_entry(self, pytester):
        """If all emitted logs are below the minimum level, 'call' must be absent."""
        pytester.makepyfile("""
            import logging
            def test_only_debug():
                logging.getLogger("t").debug("too low")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=DEBUG")
        data = _load_json_report(pytester)
        logs = _tests(data)[0].get("logs", {})
        assert "call" not in logs


# ---------------------------------------------------------------------------
# Max entries cap (--beacon-logs-max)
# ---------------------------------------------------------------------------


class TestLogsMaxEntries:
    def test_max_caps_call_phase(self, pytester):
        """--beacon-logs-max must cap entries in the call phase."""
        pytester.makepyfile("""
            import logging
            def test_many_logs():
                log = logging.getLogger("t")
                for i in range(20):
                    log.warning(f"entry {i}")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--beacon-logs-max=5",
                           "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        call_logs = _tests(data)[0].get("logs", {}).get("call", [])
        assert len(call_logs) <= 5

    def test_max_caps_each_phase_independently(self, pytester):
        """The cap applies separately to setup, call, and teardown."""
        pytester.makepyfile("""
            import logging
            import pytest

            @pytest.fixture
            def multi_phase_fixture():
                for i in range(10):
                    logging.getLogger("s").warning(f"setup {i}")
                yield
                for i in range(10):
                    logging.getLogger("t").warning(f"teardown {i}")

            def test_all_phases(multi_phase_fixture):
                for i in range(10):
                    logging.getLogger("c").warning(f"call {i}")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--beacon-logs-max=3",
                           "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        logs = _tests(data)[0].get("logs", {})
        for phase in ("setup", "call", "teardown"):
            entries = logs.get(phase, [])
            assert len(entries) <= 3, f"{phase} exceeded max: {len(entries)}"

    def test_max_one_keeps_first_entry(self, pytester):
        """With --beacon-logs-max=1 only the first log entry is retained."""
        pytester.makepyfile("""
            import logging
            def test_ordered():
                logging.getLogger("t").warning("first")
                logging.getLogger("t").warning("second")
                logging.getLogger("t").warning("third")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--beacon-logs-max=1",
                           "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        call_logs = _tests(data)[0].get("logs", {}).get("call", [])
        assert len(call_logs) == 1
        assert "first" in call_logs[0]["message"]

    def test_no_max_keeps_all_entries(self, pytester):
        """Without --beacon-logs-max all log entries are included."""
        n = 15
        pytester.makepyfile(f"""
            import logging
            def test_many():
                log = logging.getLogger("t")
                for i in range({n}):
                    log.warning(f"entry {{i}}")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        call_logs = _tests(data)[0].get("logs", {}).get("call", [])
        assert len(call_logs) == n

    def test_max_zero_produces_no_entries(self, pytester):
        """With --beacon-logs-max=0 no log entries should be stored."""
        pytester.makepyfile("""
            import logging
            def test_zero_cap():
                logging.getLogger("t").warning("should be dropped")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--beacon-logs-max=0",
                           "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        logs = _tests(data)[0].get("logs", {})
        for phase in ("setup", "call", "teardown"):
            assert logs.get(phase, []) == []


# ---------------------------------------------------------------------------
# General logs (collection phase)
# ---------------------------------------------------------------------------


class TestGeneralLogs:
    def test_general_logs_absent_when_none_emitted(self, pytester):
        """'generalLogs' must not appear in extra when no collection-phase logs exist."""
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING")
        data = _load_json_report(pytester)
        assert "generalLogs" not in _extra(data)

    def test_general_logs_captured_from_module_import(self, pytester):
        """Logs emitted at module import time must appear in 'generalLogs'."""
        pytester.makepyfile("""
            import logging
            logging.getLogger("collect_logger").warning("module import log")

            def test_pass():
                pass
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING")
        data = _load_json_report(pytester)
        general = _extra(data).get("generalLogs", [])
        assert general, "generalLogs must not be empty"
        assert any("module import log" in e["message"] for e in general)

    def test_general_logs_level_filtering(self, pytester):
        """INFO logs must be filtered out of generalLogs when level is WARNING."""
        pytester.makepyfile("""
            import logging
            logging.getLogger("t").info("info should be filtered")
            logging.getLogger("t").warning("warning should appear")

            def test_pass():
                pass
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING")
        data = _load_json_report(pytester)
        general = _extra(data).get("generalLogs", [])
        levels = [e["level"] for e in general]
        assert "INFO" not in levels
        assert "WARNING" in levels

    def test_general_logs_max_capped(self, pytester):
        """--beacon-logs-max caps the number of general log entries."""
        pytester.makepyfile("""
            import logging
            log = logging.getLogger("t")
            for i in range(10):
                log.warning(f"collect log {i}")

            def test_pass():
                pass
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--beacon-logs-max=3")
        data = _load_json_report(pytester)
        general = _extra(data).get("generalLogs", [])
        assert general, "generalLogs must not be empty"
        assert len(general) <= 3


# ---------------------------------------------------------------------------
# Interaction with status exclusion
# ---------------------------------------------------------------------------


class TestLogsWithStatusExclusion:
    def test_logs_absent_for_excluded_test(self, pytester):
        """When a test is excluded from the report by status, its logs are also absent."""
        pytester.makepyfile("""
            import logging
            def test_pass_with_log():
                logging.getLogger("t").warning("should be excluded")
        """)
        # passed is excluded by default
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-logs-level=WARNING",
                           "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        # No tests in report (passed excluded by default)
        assert _tests(data) == []

    def test_logs_present_for_included_test(self, pytester):
        """When a test is included in the report, its logs must be present."""
        pytester.makepyfile("""
            import logging
            def test_fail_with_log():
                logging.getLogger("t").warning("included warning")
                assert False
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-logs-level=WARNING",
                           "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        failed = [t for t in _tests(data) if t["status"] == "failed"]
        assert failed
        assert "logs" in failed[0]

    def test_logs_with_include_all_statuses(self, pytester):
        """With empty exclude-status, logs appear on both passed and failed tests."""
        pytester.makepyfile("""
            import logging
            def test_pass():
                logging.getLogger("p").warning("pass log")
            def test_fail():
                logging.getLogger("f").warning("fail log")
                assert False
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        for t in _tests(data):
            assert "logs" in t


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestLogsEdgeCases:
    def test_no_log_emitted_logs_object_may_be_empty(self, pytester):
        """A test that emits no logs should still not crash the plugin."""
        pytester.makepyfile("def test_silent(): pass")
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING")
        data = _load_json_report(pytester)
        # Plugin must not raise; test entry may have 'logs' with empty dict or omit it
        assert _tests(data)  # report was generated

    def test_logs_and_verbose_coexist(self, pytester):
        """--beacon-logs and --beacon-verbose can both be active simultaneously."""
        pytester.makepyfile("""
            import logging
            def test_both():
                print("stdout text")
                logging.getLogger("t").warning("log text")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-verbose",
                           "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        t = _tests(data)[0]
        assert "logs" in t
        assert "stdout" in t
        assert "log text" in str(t["logs"])
        assert "stdout text" in t["stdout"]

    def test_invalid_log_level_falls_back_to_warning(self, pytester):
        """An unrecognised level string should not crash the plugin."""
        pytester.makepyfile("""
            import logging
            def test_pass():
                logging.getLogger("t").warning("warn msg")
        """)
        # NOTAREALEVEL is not a valid logging level → should fall back to WARNING
        result = pytester.runpytest("--beacon", "--beacon-logs",
                                    "--beacon-file-exclude-status=",
                                    "--beacon-logs-level=NOTAREALEVEL",
                                    "--log-cli-level=WARNING")
        # Plugin must not crash pytest
        reports = list(pytester.path.glob("beacon_reports/*.json"))
        assert reports, "Report must be generated even with invalid level"

    def test_logs_in_report_is_valid_json(self, pytester):
        """The report containing logs must remain valid JSON."""
        pytester.makepyfile("""
            import logging
            def test_unicode():
                logging.getLogger("t").warning("unicode: \u00e9\u00e0\u00fc \U0001f600")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        reports = list(pytester.path.glob("beacon_reports/*.json"))
        assert reports
        # Must not raise JSONDecodeError
        data = json.loads(reports[0].read_text())
        assert _tests(data)

    def test_large_number_of_tests_all_get_logs(self, pytester):
        """Many tests should each independently get their own logs section."""
        n = 10
        lines = ["import logging"]
        for i in range(n):
            lines.append(f"def test_{i}():")
            lines.append(f'    logging.getLogger("t{i}").warning("log {i}")')
        pytester.makepyfile("\n".join(lines))
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING")
        data = _load_json_report(pytester)
        tests = _tests(data)
        assert len(tests) == n
        for t in tests:
            assert "logs" in t
            assert t["logs"]  # non-empty


# ---------------------------------------------------------------------------
# xdist compatibility
# ---------------------------------------------------------------------------


class TestLogsWithXdist:
    def test_xdist_logs_survive_serialization(self, pytester):
        """Logs must be present on test entries when running with xdist workers."""
        pytester.makepyfile("""
            import logging
            def test_with_log():
                logging.getLogger("xd").warning("xdist log message")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING",
                           "-n", "2")
        data = _load_json_report(pytester)
        tests = _tests(data)
        assert len(tests) == 1
        assert "logs" in tests[0]
        call_logs = tests[0]["logs"].get("call", [])
        assert call_logs
        assert any("xdist log message" in e["message"] for e in call_logs)

    def test_xdist_per_test_logs_are_independent(self, pytester):
        """Each test must carry only its own logs when distributed across workers."""
        pytester.makepyfile("""
            import logging
            import pytest

            @pytest.mark.parametrize("val", ["alpha", "beta", "gamma", "delta"])
            def test_param(val):
                logging.getLogger("xd").warning(f"msg for {val}")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING",
                           "-n", "2")
        data = _load_json_report(pytester)
        tests = _tests(data)
        assert len(tests) == 4
        for t in tests:
            call_logs = t.get("logs", {}).get("call", [])
            assert len(call_logs) == 1, (
                f"Expected exactly 1 log entry for {t['name']}, got {len(call_logs)}"
            )
            nodeid = t["name"]
            for val in ("alpha", "beta", "gamma", "delta"):
                if val in nodeid:
                    assert f"msg for {val}" in call_logs[0]["message"]
                else:
                    assert f"msg for {val}" not in call_logs[0]["message"]

    def test_xdist_log_level_filtering_preserved(self, pytester):
        """Log level filtering must still work after worker→master serialization."""
        pytester.makepyfile("""
            import logging
            import pytest

            @pytest.mark.parametrize("n", range(4))
            def test_mixed_levels(n):
                logging.getLogger("t").info("info msg")
                logging.getLogger("t").warning("warning msg")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=DEBUG",
                           "-n", "2")
        data = _load_json_report(pytester)
        for t in _tests(data):
            call_logs = t.get("logs", {}).get("call", [])
            levels = [e["level"] for e in call_logs]
            assert "INFO" not in levels, f"INFO leaked into {t['name']}"
            assert "WARNING" in levels

    def test_xdist_max_entries_cap_preserved(self, pytester):
        """--beacon-logs-max must be respected after worker→master serialization."""
        pytester.makepyfile("""
            import logging
            import pytest

            @pytest.mark.parametrize("n", range(4))
            def test_many_logs(n):
                log = logging.getLogger("t")
                for i in range(20):
                    log.warning(f"entry {i} in test {n}")
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--beacon-logs-max=5",
                           "--log-cli-level=WARNING", "-n", "2")
        data = _load_json_report(pytester)
        for t in _tests(data):
            call_logs = t.get("logs", {}).get("call", [])
            assert len(call_logs) <= 5, (
                f"Max exceeded for {t['name']}: {len(call_logs)} entries"
            )

    def test_xdist_logs_on_failed_tests(self, pytester):
        """Logs from failing tests must survive xdist serialization."""
        pytester.makepyfile("""
            import logging
            import pytest

            @pytest.mark.parametrize("n", range(4))
            def test_some_fail(n):
                logging.getLogger("t").warning(f"log before assert {n}")
                assert n % 2 == 0, f"odd failure {n}"
        """)
        pytester.runpytest("--beacon", "--beacon-logs", "--beacon-file-exclude-status=",
                           "--beacon-logs-level=WARNING", "--log-cli-level=WARNING",
                           "-n", "2")
        data = _load_json_report(pytester)
        failed = [t for t in _tests(data) if t["status"] == "failed"]
        assert failed
        for t in failed:
            assert "logs" in t
            call_logs = t["logs"].get("call", [])
            assert call_logs
            assert any("log before assert" in e["message"] for e in call_logs)

    def test_xdist_logs_absent_when_flag_not_set(self, pytester):
        """Without --beacon-logs, xdist workers must not include logs in serialized output."""
        pytester.makepyfile("""
            import logging
            import pytest

            @pytest.mark.parametrize("n", range(4))
            def test_silent(n):
                logging.getLogger("t").warning(f"should not appear {n}")
        """)
        pytester.runpytest("--beacon", "--beacon-file-exclude-status=",
                           "--log-cli-level=WARNING", "-n", "2")
        data = _load_json_report(pytester)
        for t in _tests(data):
            assert "logs" not in t


# ---------------------------------------------------------------------------
# HTTP export: test_logs field
# ---------------------------------------------------------------------------


class _CapturingHandler(BaseHTTPRequestHandler):
    received_bodies: list = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _CapturingHandler.received_bodies.append(json.loads(body))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass  # silence server output


def _run_with_http_server(pytester, *pytest_args):
    """Spin up a local HTTP server, run pytest with the given args plus --beacon-url,
    return the captured request body dict."""
    _CapturingHandler.received_bodies = []
    server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()
    pytester.runpytest(*pytest_args, f"--beacon-url=http://127.0.0.1:{port}")
    thread.join(timeout=5)
    server.server_close()
    assert _CapturingHandler.received_bodies, "No HTTP request received"
    return _CapturingHandler.received_bodies[0]


class TestLogsHttpExport:
    def test_test_logs_present_in_http_payload_when_flag_set(self, pytester):
        """With --beacon-logs the HTTP payload metric must include test_logs."""
        pytester.makepyfile("""
            import logging
            def test_with_log():
                logging.getLogger("t").warning("http log message")
        """)
        body = _run_with_http_server(
            pytester,
            "--beacon", "--beacon-logs", "--beacon-http-exclude-status=",
            "--beacon-logs-level=WARNING", "--log-cli-level=WARNING",
        )
        metrics = body["metrics"]
        assert len(metrics) == 1
        assert "test_logs" in metrics[0]
        call_logs = metrics[0]["test_logs"].get("call", [])
        assert call_logs
        assert any("http log message" in e["message"] for e in call_logs)

    def test_test_logs_absent_in_http_payload_without_flag(self, pytester):
        """Without --beacon-logs the HTTP payload must not contain test_logs."""
        pytester.makepyfile("""
            import logging
            def test_with_log():
                logging.getLogger("t").warning("should not appear")
        """)
        body = _run_with_http_server(
            pytester,
            "--beacon", "--beacon-http-exclude-status=", "--log-cli-level=WARNING",
        )
        for metric in body["metrics"]:
            assert "test_logs" not in metric

    def test_http_payload_log_entry_fields(self, pytester):
        """Log entries in the HTTP payload must have level, message, and logger fields."""
        pytester.makepyfile("""
            import logging
            def test_fields():
                logging.getLogger("app.service").warning("service warning")
        """)
        body = _run_with_http_server(
            pytester,
            "--beacon", "--beacon-logs", "--beacon-http-exclude-status=",
            "--beacon-logs-level=WARNING", "--log-cli-level=WARNING",
        )
        entry = body["metrics"][0]["test_logs"]["call"][0]
        assert entry["level"] == "WARNING"
        assert "service warning" in entry["message"]
        assert "app.service" in entry.get("logger", "")

    def test_http_log_level_filtering_applied(self, pytester):
        """Level filtering must be applied before HTTP export — INFO must not appear."""
        pytester.makepyfile("""
            import logging
            def test_levels():
                logging.getLogger("t").info("info msg")
                logging.getLogger("t").warning("warning msg")
        """)
        body = _run_with_http_server(
            pytester,
            "--beacon", "--beacon-logs", "--beacon-http-exclude-status=",
            "--beacon-logs-level=WARNING", "--log-cli-level=DEBUG",
        )
        call_logs = body["metrics"][0]["test_logs"].get("call", [])
        levels = [e["level"] for e in call_logs]
        assert "INFO" not in levels
        assert "WARNING" in levels

    def test_http_log_max_cap_applied(self, pytester):
        """--beacon-logs-max cap must be respected in the HTTP payload."""
        pytester.makepyfile("""
            import logging
            def test_many():
                log = logging.getLogger("t")
                for i in range(20):
                    log.warning(f"entry {i}")
        """)
        body = _run_with_http_server(
            pytester,
            "--beacon", "--beacon-logs", "--beacon-http-exclude-status=",
            "--beacon-logs-level=WARNING", "--beacon-logs-max=4",
            "--log-cli-level=WARNING",
        )
        call_logs = body["metrics"][0]["test_logs"].get("call", [])
        assert len(call_logs) <= 4

    def test_http_per_phase_logs_in_payload(self, pytester):
        """Setup and teardown phase logs must appear under the correct keys in the HTTP payload."""
        pytester.makepyfile("""
            import logging
            import pytest

            @pytest.fixture
            def phases():
                logging.getLogger("s").warning("setup log")
                yield
                logging.getLogger("td").warning("teardown log")

            def test_all_phases(phases):
                logging.getLogger("c").warning("call log")
        """)
        body = _run_with_http_server(
            pytester,
            "--beacon", "--beacon-logs", "--beacon-http-exclude-status=",
            "--beacon-logs-level=WARNING", "--log-cli-level=WARNING",
        )
        logs = body["metrics"][0]["test_logs"]
        assert any("setup log" in e["message"] for e in logs.get("setup", []))
        assert any("call log" in e["message"] for e in logs.get("call", []))
        assert any("teardown log" in e["message"] for e in logs.get("teardown", []))

    def test_http_logs_only_for_included_statuses(self, pytester):
        """test_logs must not appear for tests excluded from HTTP export."""
        pytester.makepyfile("""
            import logging
            def test_pass():
                logging.getLogger("t").warning("pass log")
            def test_fail():
                logging.getLogger("t").warning("fail log")
                assert False
        """)
        # Exclude passed from HTTP, include failed
        body = _run_with_http_server(
            pytester,
            "--beacon", "--beacon-logs",
            "--beacon-http-exclude-status=passed",
            "--beacon-logs-level=WARNING", "--log-cli-level=WARNING",
        )
        metrics = body["metrics"]
        # Only failed test is in the HTTP payload
        assert all(m["test_result"] != "passed" for m in metrics)
        for metric in metrics:
            assert "test_logs" in metric

    def test_http_and_file_both_contain_logs(self, pytester):
        """When both --beacon-url and --beacon-file are set, logs appear in both outputs."""
        pytester.makepyfile("""
            import logging
            def test_both():
                logging.getLogger("t").warning("shared log")
        """)
        target = pytester.path / "also_file.json"
        _CapturingHandler.received_bodies = []
        server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request)
        thread.daemon = True
        thread.start()

        pytester.runpytest(
            "--beacon", "--beacon-logs",
            "--beacon-file-exclude-status=", "--beacon-http-exclude-status=",
            "--beacon-logs-level=WARNING", "--log-cli-level=WARNING",
            f"--beacon-url=http://127.0.0.1:{port}",
            f"--beacon-file={target}",
        )
        thread.join(timeout=5)
        server.server_close()

        # File report
        file_data = json.loads(target.read_text())
        file_call_logs = file_data["results"]["tests"][0]["logs"].get("call", [])
        assert any("shared log" in e["message"] for e in file_call_logs)

        # HTTP payload
        assert _CapturingHandler.received_bodies
        http_call_logs = _CapturingHandler.received_bodies[0]["metrics"][0]["test_logs"].get("call", [])
        assert any("shared log" in e["message"] for e in http_call_logs)

    def test_http_independent_exclude_statuses_with_logs(self, pytester):
        """Different exclude rules for file and HTTP must be applied independently to logs."""
        pytester.makepyfile("""
            import logging
            def test_pass():
                logging.getLogger("t").warning("pass log")
            def test_fail():
                logging.getLogger("t").warning("fail log")
                assert False
        """)
        target = pytester.path / "indep.json"
        _CapturingHandler.received_bodies = []
        server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request)
        thread.daemon = True
        thread.start()

        pytester.runpytest(
            "--beacon", "--beacon-logs",
            "--beacon-file-exclude-status=",      # include all in file
            "--beacon-http-exclude-status=passed", # exclude passed from HTTP
            "--beacon-logs-level=WARNING", "--log-cli-level=WARNING",
            f"--beacon-url=http://127.0.0.1:{port}",
            f"--beacon-file={target}",
        )
        thread.join(timeout=5)
        server.server_close()

        # File has both tests with logs
        file_data = json.loads(target.read_text())
        file_statuses = {t["status"] for t in file_data["results"]["tests"]}
        assert "passed" in file_statuses
        assert "failed" in file_statuses
        for t in file_data["results"]["tests"]:
            assert "logs" in t

        # HTTP has only failed test
        assert _CapturingHandler.received_bodies
        http_metrics = _CapturingHandler.received_bodies[0]["metrics"]
        assert all(m["test_result"] != "passed" for m in http_metrics)
        assert all("test_logs" in m for m in http_metrics)
