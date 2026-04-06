"""Unit tests for domain entities: TestResult, TestRun, TestStatus."""
from datetime import datetime, timezone

import pytest

from pytest_beacon.domains.test_run.entities import TestResult, TestRun
from pytest_beacon.domains.test_run.value_objects import TestStatus


# ---------------------------------------------------------------------------
# TestStatus
# ---------------------------------------------------------------------------


class TestTestStatus:
    def test_string_values(self):
        assert TestStatus.PASSED.value == "passed"
        assert TestStatus.FAILED.value == "failed"
        assert TestStatus.SKIPPED.value == "skipped"
        assert TestStatus.ERROR.value == "error"
        assert TestStatus.OTHER.value == "other"

    def test_is_str_subclass(self):
        assert TestStatus.PASSED == "passed"
        assert TestStatus.FAILED == "failed"

    def test_from_string(self):
        assert TestStatus("passed") is TestStatus.PASSED
        assert TestStatus("error") is TestStatus.ERROR

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            TestStatus("unknown_xyz")


# ---------------------------------------------------------------------------
# TestResult
# ---------------------------------------------------------------------------


class TestTestResult:
    def test_minimal_required_fields(self):
        r = TestResult(nodeid="tests/test_x.py::test_foo", name="test_foo")
        assert r.nodeid == "tests/test_x.py::test_foo"
        assert r.name == "test_foo"
        assert r.status == TestStatus.OTHER
        assert r.duration_ms == 0.0
        assert r.marks == []
        assert r.params == {}
        assert r.start_time is None
        assert r.message is None
        assert r.trace is None
        assert r.failure_location is None
        assert r.allure_id is None
        assert r.stdout is None
        assert r.stderr is None

    def test_all_fields(self):
        dt = datetime.now(timezone.utc)
        r = TestResult(
            nodeid="tests/test_x.py::test_foo[a-b]",
            name="test_foo[a-b]",
            status=TestStatus.FAILED,
            duration_ms=250.5,
            start_time=dt,
            file_path="tests/test_x.py",
            line=42,
            message="assertion failed",
            trace="Traceback ...\nE assert False",
            failure_location={"file": "tests/test_x.py", "line": 42},
            marks=["smoke", "regression"],
            params={"x": 1, "y": "hello"},
            allure_id="TC-42",
            stdout="some output",
            stderr="some error",
        )
        assert r.status == TestStatus.FAILED
        assert r.duration_ms == 250.5
        assert r.start_time == dt
        assert r.file_path == "tests/test_x.py"
        assert r.line == 42
        assert r.marks == ["smoke", "regression"]
        assert r.params == {"x": 1, "y": "hello"}
        assert r.allure_id == "TC-42"
        assert r.stdout == "some output"
        assert r.stderr == "some error"

    def test_status_coercion_from_string(self):
        r = TestResult(nodeid="t::t", name="t", status="passed")
        assert r.status == TestStatus.PASSED

    def test_model_dump_round_trip(self):
        r = TestResult(
            nodeid="tests/t.py::test_a",
            name="test_a",
            status=TestStatus.FAILED,
            duration_ms=100.0,
            marks=["smoke"],
        )
        data = r.model_dump(mode="json")
        r2 = TestResult(**data)
        assert r2.nodeid == r.nodeid
        assert r2.status == r.status
        assert r2.marks == r.marks


# ---------------------------------------------------------------------------
# TestRun
# ---------------------------------------------------------------------------


class TestTestRunInitialState:
    def test_empty_tests_list(self):
        run = TestRun()
        assert run.tests == []

    def test_stop_ms_zero(self):
        run = TestRun()
        assert run.stop_ms == 0

    def test_start_ms_positive(self):
        run = TestRun()
        assert run.start_ms > 0

    def test_summary_all_zeros(self):
        run = TestRun()
        s = run.summary
        assert s["tests"] == 0
        assert s["passed"] == 0
        assert s["failed"] == 0
        assert s["skipped"] == 0
        assert s["error"] == 0
        assert s["other"] == 0
        assert s["pending"] == 0

    def test_summary_includes_timestamps(self):
        run = TestRun()
        s = run.summary
        assert "start" in s
        assert "stop" in s
        assert s["start"] > 0


class TestTestRunAddResult:
    def test_adds_to_tests(self):
        run = TestRun()
        r = TestResult(nodeid="t::test_a", name="test_a", status=TestStatus.PASSED)
        run.add_result(r)
        assert len(run.tests) == 1
        assert run.tests[0] is r

    def test_updates_summary(self):
        run = TestRun()
        run.add_result(TestResult(nodeid="t::p", name="p", status=TestStatus.PASSED))
        run.add_result(TestResult(nodeid="t::f", name="f", status=TestStatus.FAILED))
        run.add_result(TestResult(nodeid="t::s", name="s", status=TestStatus.SKIPPED))
        run.add_result(TestResult(nodeid="t::e", name="e", status=TestStatus.ERROR))
        run.add_result(TestResult(nodeid="t::o", name="o", status=TestStatus.OTHER))
        s = run.summary
        assert s["tests"] == 5
        assert s["passed"] == 1
        assert s["failed"] == 1
        assert s["skipped"] == 1
        assert s["error"] == 1
        assert s["other"] == 1


class TestTestRunUpdateSummaryOnly:
    def test_updates_summary_not_tests(self):
        run = TestRun()
        run.update_summary_only(TestStatus.FAILED)
        assert run.summary["tests"] == 1
        assert run.summary["failed"] == 1
        assert run.tests == []

    def test_multiple_calls(self):
        run = TestRun()
        run.update_summary_only(TestStatus.PASSED)
        run.update_summary_only(TestStatus.PASSED)
        run.update_summary_only(TestStatus.FAILED)
        assert run.summary["passed"] == 2
        assert run.summary["failed"] == 1
        assert run.summary["tests"] == 3


class TestTestRunFinalize:
    def test_sets_stop_ms(self):
        run = TestRun()
        assert run.stop_ms == 0
        run.finalize()
        assert run.stop_ms > 0

    def test_stop_after_start(self):
        run = TestRun()
        run.finalize()
        assert run.stop_ms >= run.start_ms

    def test_summary_reflects_stop(self):
        run = TestRun()
        run.finalize()
        assert run.summary["stop"] == run.stop_ms


class TestTestRunMergeWorkerResults:
    def _make_raw(self, **kwargs):
        defaults = {"nodeid": "t::test_a", "name": "test_a", "status": "passed", "duration_ms": 10.0}
        defaults.update(kwargs)
        return defaults

    def test_merges_basic_test(self):
        run = TestRun()
        run.merge_worker_results(
            [self._make_raw(status="failed")],
            excluded_statuses=set(),
            seen_collection_errors=set(),
        )
        assert run.summary["tests"] == 1
        assert run.summary["failed"] == 1
        assert len(run.tests) == 1
        assert run.tests[0].status == TestStatus.FAILED

    def test_excluded_status_not_in_tests(self):
        run = TestRun()
        run.merge_worker_results(
            [self._make_raw(status="passed")],
            excluded_statuses={"passed"},
            seen_collection_errors=set(),
        )
        assert run.summary["tests"] == 1
        assert run.summary["passed"] == 1
        assert len(run.tests) == 0

    def test_collection_error_deduplication(self):
        run = TestRun()
        seen = {"tests/t.py"}
        run.merge_worker_results(
            [self._make_raw(status="error", file_path="tests/t.py")],
            excluded_statuses=set(),
            seen_collection_errors=seen,
        )
        # Summary updated but test not added (duplicate)
        assert run.summary["tests"] == 1
        assert run.summary["error"] == 1
        assert len(run.tests) == 0

    def test_new_collection_error_added_to_seen(self):
        run = TestRun()
        seen: set[str] = set()
        run.merge_worker_results(
            [self._make_raw(status="error", file_path="tests/new.py")],
            excluded_statuses=set(),
            seen_collection_errors=seen,
        )
        assert "tests/new.py" in seen
        assert len(run.tests) == 1

    def test_unknown_status_maps_to_other(self):
        run = TestRun()
        run.merge_worker_results(
            [self._make_raw(status="unknown_xyz")],
            excluded_statuses=set(),
            seen_collection_errors=set(),
        )
        assert run.summary["other"] == 1

    def test_empty_list(self):
        run = TestRun()
        run.merge_worker_results([], excluded_statuses=set(), seen_collection_errors=set())
        assert run.summary["tests"] == 0
        assert run.tests == []

    def test_multiple_workers(self):
        run = TestRun()
        run.merge_worker_results(
            [self._make_raw(nodeid="t::a", status="passed")],
            excluded_statuses=set(),
            seen_collection_errors=set(),
        )
        run.merge_worker_results(
            [self._make_raw(nodeid="t::b", status="failed")],
            excluded_statuses=set(),
            seen_collection_errors=set(),
        )
        assert run.summary["tests"] == 2
        assert len(run.tests) == 2
