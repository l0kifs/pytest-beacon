"""Unit tests for pure helper functions in the pytest plugin hooks module."""
from unittest.mock import MagicMock

import pytest

from pytest_beacon.domains.test_run.value_objects import TestStatus
from pytest_beacon.entry_points.pytest_plugin.hooks import (
    _extract_allure_id,
    _extract_error_message,
    _extract_marks,
    _extract_params,
    _extract_skip_reason,
    _failure_location,
    _map_outcome,
    _parse_meta,
    _sanitize_param,
    _truncate_traceback,
)


# ---------------------------------------------------------------------------
# _map_outcome
# ---------------------------------------------------------------------------


class _Report:
    def __init__(self, when, outcome):
        self.when = when
        self.outcome = outcome


class TestMapOutcome:
    def test_call_passed(self):
        assert _map_outcome(_Report("call", "passed")) == TestStatus.PASSED

    def test_call_failed(self):
        assert _map_outcome(_Report("call", "failed")) == TestStatus.FAILED

    def test_call_skipped(self):
        assert _map_outcome(_Report("call", "skipped")) == TestStatus.SKIPPED

    def test_call_error(self):
        assert _map_outcome(_Report("call", "error")) == TestStatus.ERROR

    def test_setup_failure_is_error(self):
        assert _map_outcome(_Report("setup", "failed")) == TestStatus.ERROR

    def test_teardown_failure_is_failed(self):
        # Teardown failures use "failed" outcome but when=="teardown" — still maps to FAILED
        assert _map_outcome(_Report("teardown", "failed")) == TestStatus.FAILED

    def test_unknown_outcome_is_other(self):
        assert _map_outcome(_Report("call", "xpassed")) == TestStatus.OTHER


# ---------------------------------------------------------------------------
# _extract_error_message
# ---------------------------------------------------------------------------


class _ExcInfo:
    def __init__(self, value=None, typename="Exception", traceback=None):
        self.value = value
        self.typename = typename
        self.traceback = traceback


class _Report2:
    def __init__(self, longrepr=None, excinfo=None):
        self.longrepr = longrepr
        self.excinfo = excinfo


class TestExtractErrorMessage:
    def test_assertion_error_from_excinfo(self):
        exc = AssertionError("expected True, got False")
        info = _ExcInfo(value=exc, typename="AssertionError")
        msg = _extract_error_message(_Report2(), info)
        assert "expected True" in msg

    def test_non_assertion_error_from_excinfo(self):
        exc = RuntimeError("something exploded")
        info = _ExcInfo(value=exc, typename="RuntimeError")
        msg = _extract_error_message(_Report2(), info)
        assert "something exploded" in msg

    def test_truncates_to_500_chars(self):
        exc = AssertionError("x" * 1000)
        info = _ExcInfo(value=exc, typename="AssertionError")
        msg = _extract_error_message(_Report2(), info)
        assert len(msg) <= 500

    def test_extracts_from_longrepr_e_line(self):
        report = _Report2(longrepr="some context\nE assert False\nmore context")
        msg = _extract_error_message(report, None)
        assert "assert False" in msg

    def test_falls_back_to_first_line(self):
        report = _Report2(longrepr="first line\nsecond line")
        msg = _extract_error_message(report, None)
        assert msg == "first line"

    def test_returns_unknown_error_when_nothing(self):
        msg = _extract_error_message(_Report2(), None)
        assert msg == "Unknown error"

    def test_no_excinfo_value_falls_through_to_longrepr(self):
        info = _ExcInfo(value=None)
        report = _Report2(longrepr="E value error here")
        msg = _extract_error_message(report, info)
        assert "value error here" in msg


# ---------------------------------------------------------------------------
# _extract_skip_reason
# ---------------------------------------------------------------------------


class TestExtractSkipReason:
    def test_from_skipped_in_longrepr(self):
        report = _Report2(longrepr="path/to/test.py:10: Skipped: not implemented yet")
        reason = _extract_skip_reason(report)
        assert "not implemented yet" in reason

    def test_truncates_to_200_chars(self):
        report = _Report2(longrepr=f"Skipped: {'x' * 300}")
        reason = _extract_skip_reason(report)
        assert len(reason) <= 200

    def test_returns_expected_failure_for_xfail(self):
        report = _Report2(longrepr=None)
        report.wasxfail = "reason"
        reason = _extract_skip_reason(report)
        assert reason == "Expected failure"

    def test_default_when_nothing(self):
        report = _Report2(longrepr=None)
        reason = _extract_skip_reason(report)
        assert reason == "Test was skipped"

    def test_bare_longrepr_returned(self):
        report = _Report2(longrepr="some skip info without keyword")
        reason = _extract_skip_reason(report)
        assert "some skip info" in reason


# ---------------------------------------------------------------------------
# _truncate_traceback
# ---------------------------------------------------------------------------


class TestTruncateTraceback:
    def test_short_traceback_unchanged(self):
        tb = "\n".join(f"line {i}" for i in range(10))
        assert _truncate_traceback(tb) == tb

    def test_exactly_20_lines_unchanged(self):
        tb = "\n".join(f"line {i}" for i in range(20))
        assert _truncate_traceback(tb) == tb

    def test_long_traceback_truncated(self):
        lines = [f"line {i}" for i in range(50)]
        tb = "\n".join(lines)
        result = _truncate_traceback(tb)
        assert "..." in result
        result_lines = result.split("\n")
        # first 10, "...", last 10 = 21 lines
        assert len(result_lines) == 21

    def test_first_and_last_preserved(self):
        lines = [f"line {i}" for i in range(30)]
        tb = "\n".join(lines)
        result = _truncate_traceback(tb)
        assert "line 0" in result
        assert "line 29" in result
        assert "line 10" not in result


# ---------------------------------------------------------------------------
# _failure_location
# ---------------------------------------------------------------------------


class TestFailureLocation:
    def test_returns_none_when_no_excinfo(self):
        assert _failure_location(None) is None

    def test_returns_none_when_no_traceback(self):
        info = _ExcInfo(traceback=None)
        assert _failure_location(info) is None

    def test_extracts_last_entry(self):
        entry = MagicMock()
        entry.path = "/path/to/test.py"
        entry.lineno = 42
        info = _ExcInfo(traceback=[MagicMock(), entry])
        loc = _failure_location(info)
        assert loc == {"file": "/path/to/test.py", "line": 42}


# ---------------------------------------------------------------------------
# _extract_marks
# ---------------------------------------------------------------------------


class TestExtractMarks:
    def test_single_mark(self):
        m = MagicMock()
        m.name = "smoke"
        item = MagicMock()
        item.iter_markers.return_value = [m]
        assert _extract_marks(item) == ["smoke"]

    def test_multiple_marks(self):
        marks = [MagicMock(name=n) for n in ("smoke", "slow", "regression")]
        for m, name in zip(marks, ("smoke", "slow", "regression")):
            m.name = name
        item = MagicMock()
        item.iter_markers.return_value = marks
        assert _extract_marks(item) == ["smoke", "slow", "regression"]

    def test_no_marks(self):
        item = MagicMock()
        item.iter_markers.return_value = []
        assert _extract_marks(item) == []

    def test_returns_empty_on_exception(self):
        item = MagicMock()
        item.iter_markers.side_effect = RuntimeError("boom")
        assert _extract_marks(item) == []


# ---------------------------------------------------------------------------
# _extract_params
# ---------------------------------------------------------------------------


class TestExtractParams:
    def test_parametrized_test(self):
        item = MagicMock()
        item.callspec.params = {"x": 1, "y": "hello"}
        result = _extract_params(item)
        assert result == {"x": 1, "y": "hello"}

    def test_non_parametrized_returns_empty(self):
        item = MagicMock(spec=[])  # no callspec attribute
        result = _extract_params(item)
        assert result == {}

    def test_complex_param_sanitized(self):
        item = MagicMock()
        item.callspec.params = {"obj": object()}
        result = _extract_params(item)
        assert isinstance(result["obj"], str)

    def test_returns_empty_on_exception(self):
        item = MagicMock()
        item.callspec.params = None
        # Accessing .items() on None raises AttributeError
        result = _extract_params(item)
        assert result == {}


# ---------------------------------------------------------------------------
# _sanitize_param
# ---------------------------------------------------------------------------


class TestSanitizeParam:
    def test_primitives_unchanged(self):
        assert _sanitize_param(1) == 1
        assert _sanitize_param(3.14) == 3.14
        assert _sanitize_param("hello") == "hello"
        assert _sanitize_param(True) is True
        assert _sanitize_param(None) is None

    def test_list_recursive(self):
        result = _sanitize_param([1, "two", object()])
        assert result[0] == 1
        assert result[1] == "two"
        assert isinstance(result[2], str)

    def test_tuple_becomes_list(self):
        result = _sanitize_param((1, 2))
        assert result == [1, 2]

    def test_dict_recursive(self):
        result = _sanitize_param({"a": 1, "b": object()})
        assert result["a"] == 1
        assert isinstance(result["b"], str)

    def test_arbitrary_object_stringified(self):
        class Custom:
            def __str__(self):
                return "custom_value"
        result = _sanitize_param(Custom())
        assert result == "custom_value"

    def test_nested_structure(self):
        result = _sanitize_param({"key": [1, {"nested": True}]})
        assert result == {"key": [1, {"nested": True}]}


# ---------------------------------------------------------------------------
# _extract_allure_id
# ---------------------------------------------------------------------------


class TestExtractAllureId:
    def test_allure_id_mark(self):
        m = MagicMock()
        m.name = "allure_id"
        m.args = ("TC-42",)
        item = MagicMock()
        item.iter_markers.return_value = [m]
        assert _extract_allure_id(item) == "TC-42"

    def test_allure_dot_id_mark(self):
        m = MagicMock()
        m.name = "allure.id"
        m.args = ("TC-99",)
        item = MagicMock()
        item.iter_markers.return_value = [m]
        assert _extract_allure_id(item) == "TC-99"

    def test_id_mark(self):
        m = MagicMock()
        m.name = "id"
        m.args = ("TC-1",)
        item = MagicMock()
        item.iter_markers.return_value = [m]
        assert _extract_allure_id(item) == "TC-1"

    def test_no_matching_mark(self):
        m = MagicMock()
        m.name = "smoke"
        m.args = ()
        item = MagicMock()
        item.iter_markers.return_value = [m]
        assert _extract_allure_id(item) is None

    def test_no_marks(self):
        item = MagicMock()
        item.iter_markers.return_value = []
        assert _extract_allure_id(item) is None

    def test_returns_none_on_exception(self):
        item = MagicMock()
        item.iter_markers.side_effect = RuntimeError("boom")
        assert _extract_allure_id(item) is None


# ---------------------------------------------------------------------------
# _parse_meta
# ---------------------------------------------------------------------------


class TestParseMeta:
    def test_single_entry(self):
        assert _parse_meta(["build=123"]) == {"build": "123"}

    def test_multiple_entries(self):
        result = _parse_meta(["build=123", "branch=main", "env=staging"])
        assert result == {"build": "123", "branch": "main", "env": "staging"}

    def test_value_contains_equals(self):
        result = _parse_meta(["url=http://example.com/path=1"])
        assert result == {"url": "http://example.com/path=1"}

    def test_malformed_no_equals_skipped(self):
        result = _parse_meta(["malformed"])
        assert result == {}

    def test_empty_key_skipped(self):
        result = _parse_meta(["=value"])
        assert result == {}

    def test_empty_list(self):
        assert _parse_meta([]) == {}

    def test_none_returns_empty(self):
        assert _parse_meta(None) == {}

    def test_whitespace_stripped_from_key(self):
        result = _parse_meta([" build =123"])
        assert "build" in result

    def test_mixed_valid_and_invalid(self):
        result = _parse_meta(["build=123", "bad", "branch=main"])
        assert result == {"build": "123", "branch": "main"}
