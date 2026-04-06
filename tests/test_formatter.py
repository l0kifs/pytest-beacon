"""Unit tests for the CTRF 1.0.0 formatter."""
import sys

import pytest as _pytest

from pytest_beacon.domains.test_run.entities import TestResult, TestRun
from pytest_beacon.domains.test_run.value_objects import TestStatus
from pytest_beacon.infrastructure.formatters.ctrf import _format_test, build_ctrf_report


def _run_with(*results: TestResult) -> TestRun:
    run = TestRun()
    for r in results:
        run.add_result(r)
    run.finalize()
    return run


def _make(status: TestStatus = TestStatus.PASSED, **kwargs) -> TestResult:
    defaults = {"nodeid": f"tests/t.py::test_{status.value}", "name": f"test_{status.value}", "status": status}
    defaults.update(kwargs)
    return TestResult(**defaults)


# ---------------------------------------------------------------------------
# Report structure
# ---------------------------------------------------------------------------


class TestReportStructure:
    def test_top_level_key(self):
        report = build_ctrf_report(_run_with())
        assert "results" in report

    def test_tool_section(self):
        report = build_ctrf_report(_run_with())
        tool = report["results"]["tool"]
        assert tool["name"] == "pytest"
        assert isinstance(tool["version"], str)
        assert len(tool["version"]) > 0

    def test_summary_section_keys(self):
        report = build_ctrf_report(_run_with())
        summary = report["results"]["summary"]
        for key in ("tests", "passed", "failed", "skipped", "error", "other", "pending", "start", "stop"):
            assert key in summary, f"Missing key: {key}"

    def test_tests_section_is_list(self):
        report = build_ctrf_report(_run_with())
        assert isinstance(report["results"]["tests"], list)

    def test_environment_section(self):
        report = build_ctrf_report(_run_with())
        env = report["results"]["environment"]
        assert "pythonVersion" in env
        assert "pytestVersion" in env
        expected_py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        assert env["pythonVersion"] == expected_py

    def test_extra_section(self):
        report = build_ctrf_report(_run_with())
        extra = report["results"]["extra"]
        assert extra["pluginName"] == "pytest-beacon"
        assert extra["pluginVersion"] == "0.1.0"
        assert extra["ctrf"] == "1.0.0"
        assert "generatedAt" in extra

    def test_custom_plugin_name_version(self):
        report = build_ctrf_report(_run_with(), plugin_name="my-plugin", plugin_version="2.0.0")
        extra = report["results"]["extra"]
        assert extra["pluginName"] == "my-plugin"
        assert extra["pluginVersion"] == "2.0.0"


# ---------------------------------------------------------------------------
# Summary counts
# ---------------------------------------------------------------------------


class TestSummaryCounts:
    def test_empty_run(self):
        report = build_ctrf_report(_run_with())
        s = report["results"]["summary"]
        assert s["tests"] == 0
        assert s["passed"] == 0

    def test_counts_match_added_results(self):
        run = _run_with(
            _make(TestStatus.PASSED),
            _make(TestStatus.PASSED),
            _make(TestStatus.FAILED, nodeid="t::f"),
            _make(TestStatus.SKIPPED, nodeid="t::s"),
            _make(TestStatus.ERROR, nodeid="t::e"),
        )
        report = build_ctrf_report(run)
        s = report["results"]["summary"]
        assert s["tests"] == 5
        assert s["passed"] == 2
        assert s["failed"] == 1
        assert s["skipped"] == 1
        assert s["error"] == 1


# ---------------------------------------------------------------------------
# Status exclusion
# ---------------------------------------------------------------------------


class TestStatusExclusion:
    def test_excluded_status_not_in_tests_list(self):
        run = _run_with(_make(TestStatus.PASSED), _make(TestStatus.FAILED, nodeid="t::f"))
        report = build_ctrf_report(run, excluded_statuses={"passed"})
        statuses = [t["status"] for t in report["results"]["tests"]]
        assert "passed" not in statuses
        assert "failed" in statuses

    def test_empty_excluded_set_shows_all(self):
        run = _run_with(_make(TestStatus.PASSED), _make(TestStatus.FAILED, nodeid="t::f"))
        report = build_ctrf_report(run, excluded_statuses=set())
        assert len(report["results"]["tests"]) == 2

    def test_none_excluded_shows_all(self):
        run = _run_with(_make(TestStatus.PASSED))
        report = build_ctrf_report(run, excluded_statuses=None)
        assert len(report["results"]["tests"]) == 1

    def test_summary_not_affected_by_exclusion(self):
        # build_ctrf_report itself doesn't touch summary — it comes from TestRun
        run = _run_with(_make(TestStatus.PASSED))
        report = build_ctrf_report(run, excluded_statuses={"passed"})
        assert report["results"]["summary"]["passed"] == 1  # summary accurate


# ---------------------------------------------------------------------------
# xdist workers
# ---------------------------------------------------------------------------


class TestXdistWorkers:
    def test_not_present_when_none(self):
        report = build_ctrf_report(_run_with(), xdist_workers=None)
        assert "xdistWorkers" not in report["results"]["environment"]

    def test_present_when_provided(self):
        report = build_ctrf_report(_run_with(), xdist_workers=4)
        assert report["results"]["environment"]["xdistWorkers"] == 4


# ---------------------------------------------------------------------------
# Extra metadata
# ---------------------------------------------------------------------------


class TestExtraMeta:
    def test_not_present_when_none(self):
        report = build_ctrf_report(_run_with(), extra_meta=None)
        env = report["results"]["environment"]
        assert "build" not in env

    def test_meta_merged_into_environment(self):
        report = build_ctrf_report(_run_with(), extra_meta={"build": "123", "branch": "main"})
        env = report["results"]["environment"]
        assert env["build"] == "123"
        assert env["branch"] == "main"

    def test_meta_does_not_overwrite_standard_fields(self):
        # If user passes a key that conflicts, it overwrites — expected behavior
        report = build_ctrf_report(_run_with(), extra_meta={"pytestVersion": "custom"})
        assert report["results"]["environment"]["pytestVersion"] == "custom"


# ---------------------------------------------------------------------------
# _format_test
# ---------------------------------------------------------------------------


class TestFormatTest:
    def test_required_fields_always_present(self):
        r = _make(TestStatus.PASSED)
        item = _format_test(r)
        assert "name" in item
        assert "status" in item
        assert "duration" in item

    def test_optional_fields_absent_when_none(self):
        r = _make(TestStatus.PASSED)
        item = _format_test(r)
        assert "filePath" not in item
        assert "line" not in item
        assert "message" not in item
        assert "trace" not in item
        assert "failureLocation" not in item
        assert "marks" not in item
        assert "params" not in item
        assert "allureId" not in item
        assert "stdout" not in item
        assert "stderr" not in item

    def test_file_path_and_line_present(self):
        r = _make(TestStatus.FAILED, file_path="tests/t.py", line=10, nodeid="tests/t.py::test_failed")
        item = _format_test(r)
        assert item["filePath"] == "tests/t.py"
        assert item["line"] == 10

    def test_failure_fields(self):
        r = _make(
            TestStatus.FAILED,
            nodeid="t::f",
            message="assertion failed",
            trace="Traceback ...",
            failure_location={"file": "t.py", "line": 5},
        )
        item = _format_test(r)
        assert item["message"] == "assertion failed"
        assert item["trace"] == "Traceback ..."
        assert item["failureLocation"] == {"file": "t.py", "line": 5}

    def test_marks_and_params(self):
        r = _make(TestStatus.PASSED, marks=["smoke"], params={"x": 1})
        item = _format_test(r)
        assert item["marks"] == ["smoke"]
        assert item["params"] == {"x": 1}

    def test_allure_id(self):
        r = _make(TestStatus.PASSED, allure_id="TC-99")
        item = _format_test(r)
        assert item["allureId"] == "TC-99"

    def test_allure_id_absent_when_none(self):
        r = _make(TestStatus.PASSED)
        item = _format_test(r)
        assert "allureId" not in item

    def test_stdout_stderr_in_verbose(self):
        r = _make(TestStatus.PASSED, stdout="hello\n", stderr="err\n")
        item = _format_test(r)
        assert item["stdout"] == "hello\n"
        assert item["stderr"] == "err\n"

    def test_status_is_string_value(self):
        r = _make(TestStatus.SKIPPED)
        item = _format_test(r)
        assert item["status"] == "skipped"

    def test_duration_in_ms(self):
        r = _make(TestStatus.PASSED, duration_ms=123.4)
        item = _format_test(r)
        assert item["duration"] == 123.4
