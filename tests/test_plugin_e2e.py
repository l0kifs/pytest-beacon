"""
End-to-end integration tests for the pytest-beacon plugin.

Uses pytest's `pytester` fixture to run isolated pytest sessions and inspect
the generated CTRF report files.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json_report(pytester):
    reports = list(pytester.path.glob("beacon_reports/*.json"))
    assert reports, "No JSON report generated in beacon_reports/"
    return json.loads(reports[0].read_text())


def _load_yaml_report(pytester):
    reports = list(pytester.path.glob("beacon_reports/*.yaml"))
    assert reports, "No YAML report generated in beacon_reports/"
    return yaml.safe_load(reports[0].read_text())


def _results(report):
    return report["results"]


# ---------------------------------------------------------------------------
# Plugin activation
# ---------------------------------------------------------------------------


class TestPluginActivation:
    def test_no_flag_no_report_generated(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest()
        result.assert_outcomes(passed=1)
        assert list(pytester.path.glob("beacon_reports/*.json")) == []

    def test_flag_generates_report(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest("--beacon", "--beacon-exclude-status=")
        result.assert_outcomes(passed=1)
        assert len(list(pytester.path.glob("beacon_reports/*.json"))) == 1

    def test_report_has_valid_ctrf_structure(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        r = _results(data)
        assert "tool" in r
        assert "summary" in r
        assert "tests" in r
        assert "environment" in r
        assert "extra" in r

    def test_ctrf_metadata(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        extra = _results(data)["extra"]
        assert extra["pluginName"] == "pytest-beacon"
        assert extra["ctrf"] == "1.0.0"

    def test_environment_section(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        env = _results(data)["environment"]
        assert "pythonVersion" in env
        assert "pytestVersion" in env


# ---------------------------------------------------------------------------
# Test outcome capture
# ---------------------------------------------------------------------------


class TestOutcomeCapture:
    def test_passed_test(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        s = _results(data)["summary"]
        assert s["passed"] == 1
        assert s["tests"] == 1

    def test_failed_test(self, pytester):
        pytester.makepyfile("def test_fail(): assert False, 'intentional failure'")
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        s = _results(data)["summary"]
        assert s["failed"] == 1
        tests = _results(data)["tests"]
        failed = [t for t in tests if t["status"] == "failed"]
        assert len(failed) == 1
        assert "intentional failure" in failed[0]["message"]

    def test_skipped_test(self, pytester):
        pytester.makepyfile("""
            import pytest
            @pytest.mark.skip(reason="not ready")
            def test_skip(): pass
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        s = _results(data)["summary"]
        assert s["skipped"] == 1
        tests = _results(data)["tests"]
        skipped = [t for t in tests if t["status"] == "skipped"]
        assert len(skipped) == 1
        assert "not ready" in skipped[0]["message"]

    def test_setup_failure_is_error(self, pytester):
        pytester.makepyfile("""
            import pytest
            @pytest.fixture
            def broken():
                raise RuntimeError("fixture boom")
            def test_with_broken(broken): pass
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        s = _results(data)["summary"]
        assert s["error"] == 1

    def test_all_statuses_in_one_run(self, pytester):
        pytester.makepyfile("""
            import pytest
            def test_pass(): pass
            def test_fail(): assert False
            @pytest.mark.skip(reason="skip")
            def test_skip(): pass
            @pytest.fixture
            def broken(): raise RuntimeError("boom")
            def test_error(broken): pass
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        s = _results(data)["summary"]
        assert s["passed"] == 1
        assert s["failed"] == 1
        assert s["skipped"] == 1
        assert s["error"] == 1
        assert s["tests"] == 4

    def test_failed_test_has_trace(self, pytester):
        pytester.makepyfile("def test_fail(): assert 1 == 2")
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        failed = [t for t in _results(data)["tests"] if t["status"] == "failed"]
        assert failed[0].get("trace") is not None

    def test_failed_test_has_file_and_line(self, pytester):
        pytester.makepyfile("def test_fail(): assert False")
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        failed = [t for t in _results(data)["tests"] if t["status"] == "failed"][0]
        assert "filePath" in failed
        assert "line" in failed

    def test_empty_test_session(self, pytester):
        pytester.makepyfile("# no tests")
        pytester.runpytest("--beacon")
        data = _load_json_report(pytester)
        assert _results(data)["summary"]["tests"] == 0


# ---------------------------------------------------------------------------
# Status exclusion
# ---------------------------------------------------------------------------


class TestStatusExclusion:
    def test_passed_excluded_by_default(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon")
        data = _load_json_report(pytester)
        tests = _results(data)["tests"]
        assert all(t["status"] != "passed" for t in tests)

    def test_summary_accurate_even_when_excluded(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon")
        data = _load_json_report(pytester)
        assert _results(data)["summary"]["passed"] == 1

    def test_include_all_with_empty_string(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        tests = _results(data)["tests"]
        assert any(t["status"] == "passed" for t in tests)

    def test_exclude_multiple_statuses(self, pytester):
        pytester.makepyfile("""
            import pytest
            def test_pass(): pass
            def test_fail(): assert False
            @pytest.mark.skip(reason="s")
            def test_skip(): pass
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=passed,skipped")
        data = _load_json_report(pytester)
        tests = _results(data)["tests"]
        statuses = {t["status"] for t in tests}
        assert "passed" not in statuses
        assert "skipped" not in statuses
        assert "failed" in statuses
        # Summary still accurate
        s = _results(data)["summary"]
        assert s["passed"] == 1
        assert s["skipped"] == 1
        assert s["failed"] == 1

    def test_exclude_failed(self, pytester):
        pytester.makepyfile("""
            def test_pass(): pass
            def test_fail(): assert False
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=passed,failed")
        data = _load_json_report(pytester)
        assert _results(data)["tests"] == []
        assert _results(data)["summary"]["tests"] == 2


# ---------------------------------------------------------------------------
# Report output
# ---------------------------------------------------------------------------


class TestReportOutput:
    def test_default_output_in_beacon_reports(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon")
        reports = list(pytester.path.glob("beacon_reports/*.json"))
        assert len(reports) == 1

    def test_custom_file_absolute_path(self, pytester):
        target = pytester.path / "custom_report.json"
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", f"--beacon-file={target}")
        assert target.exists()
        data = json.loads(target.read_text())
        assert "results" in data

    def test_custom_file_bare_name_in_beacon_reports(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-file=myreport.json")
        reports = list(pytester.path.glob("beacon_reports/myreport-*.json"))
        assert len(reports) == 1

    def test_yaml_format(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-format=yaml", "--beacon-exclude-status=")
        reports = list(pytester.path.glob("beacon_reports/*.yaml"))
        assert len(reports) == 1
        data = yaml.safe_load(reports[0].read_text())
        assert _results(data)["summary"]["passed"] == 1

    def test_json_is_valid(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon")
        reports = list(pytester.path.glob("beacon_reports/*.json"))
        # Should not raise
        json.loads(reports[0].read_text())

    def test_summary_printed_to_stdout(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        result = pytester.runpytest("--beacon")
        result.stdout.fnmatch_lines(["*pytest-beacon report*"])


# ---------------------------------------------------------------------------
# Verbose mode
# ---------------------------------------------------------------------------


class TestVerboseMode:
    def test_verbose_captures_stdout(self, pytester):
        pytester.makepyfile("""
            def test_with_output():
                print("hello from test")
        """)
        pytester.runpytest("--beacon", "--beacon-verbose", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        tests = _results(data)["tests"]
        passed = [t for t in tests if t["status"] == "passed"]
        assert passed
        assert "hello from test" in (passed[0].get("stdout") or "")

    def test_no_verbose_no_stdout(self, pytester):
        pytester.makepyfile("""
            def test_with_output():
                print("hello from test")
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        tests = _results(data)["tests"]
        passed = [t for t in tests if t["status"] == "passed"]
        assert "stdout" not in (passed[0] if passed else {})


# ---------------------------------------------------------------------------
# Metadata (--beacon-meta)
# ---------------------------------------------------------------------------


class TestMetadata:
    def test_single_meta_in_environment(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-meta=build=123")
        data = _load_json_report(pytester)
        assert _results(data)["environment"]["build"] == "123"

    def test_multiple_meta_in_environment(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-meta=build=123", "--beacon-meta=branch=main")
        data = _load_json_report(pytester)
        env = _results(data)["environment"]
        assert env["build"] == "123"
        assert env["branch"] == "main"

    def test_meta_value_with_equals(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-meta=url=http://x.com/a=1")
        data = _load_json_report(pytester)
        assert _results(data)["environment"]["url"] == "http://x.com/a=1"

    def test_malformed_meta_skipped(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-meta=nodash", "--beacon-meta=good=value")
        data = _load_json_report(pytester)
        env = _results(data)["environment"]
        assert env.get("good") == "value"
        assert "nodash" not in env

    def test_no_meta_no_extra_keys(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon")
        data = _load_json_report(pytester)
        env = _results(data)["environment"]
        expected_keys = {"pythonVersion", "pytestVersion"}
        assert set(env.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Test marks, params, allure ID capture
# ---------------------------------------------------------------------------


class TestTestMetadataCapture:
    def test_marks_captured(self, pytester):
        pytester.makepyfile("""
            import pytest
            @pytest.mark.smoke
            def test_marked(): pass
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        tests = _results(data)["tests"]
        marked = [t for t in tests if "smoke" in t.get("marks", [])]
        assert len(marked) == 1

    def test_allure_id_captured_from_mark_without_allure_plugin(self, pytester):
        """allureId is extracted from @pytest.mark.allure_id — allure-pytest not required."""
        pytester.makepyfile("""
            import pytest
            @pytest.mark.allure_id("TC-42")
            def test_with_allure_id(): pass
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        tests = _results(data)["tests"]
        assert tests[0].get("allureId") == "TC-42"

    def test_allure_id_absent_when_no_mark(self, pytester):
        """allureId must not appear in the report when no allure mark is used."""
        pytester.makepyfile("def test_plain(): pass")
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        tests = _results(data)["tests"]
        assert "allureId" not in tests[0]

    def test_parametrized_params_captured(self, pytester):
        pytester.makepyfile("""
            import pytest
            @pytest.mark.parametrize("x,y", [(1, 2), (3, 4)])
            def test_param(x, y): pass
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        tests = _results(data)["tests"]
        assert len(tests) == 2
        for t in tests:
            assert "params" in t
            assert "x" in t["params"]
            assert "y" in t["params"]


# ---------------------------------------------------------------------------
# Collection errors
# ---------------------------------------------------------------------------


class TestCollectionErrors:
    def test_import_error_captured_as_error(self, pytester):
        pytester.makepyfile("""
            import totally_nonexistent_module_xyz
            def test_something(): pass
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        s = _results(data)["summary"]
        assert s["error"] >= 1

    def test_collection_error_in_tests_list(self, pytester):
        pytester.makepyfile("""
            import totally_nonexistent_module_xyz
            def test_something(): pass
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        errors = [t for t in _results(data)["tests"] if t["status"] == "error"]
        assert len(errors) >= 1

    def test_collection_error_not_duplicated(self, pytester):
        # Multiple tests in the same broken file should only produce one error entry
        pytester.makepyfile("""
            import totally_nonexistent_module_xyz
            def test_a(): pass
            def test_b(): pass
            def test_c(): pass
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=")
        data = _load_json_report(pytester)
        errors = [t for t in _results(data)["tests"] if t["status"] == "error"]
        assert len(errors) == 1


# ---------------------------------------------------------------------------
# xdist parallel execution
# ---------------------------------------------------------------------------


class TestXdist:
    def test_no_xdist_workers_key_without_n_flag(self, pytester):
        """xdistWorkers must not appear in environment when xdist is not active."""
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon")
        data = _load_json_report(pytester)
        assert "xdistWorkers" not in _results(data)["environment"]

    def test_xdist_parallel_produces_correct_summary(self, pytester):
        pytester.makepyfile("""
            import pytest
            @pytest.mark.parametrize("n", list(range(8)))
            def test_parallel(n): pass
        """)
        result = pytester.runpytest("--beacon", "--beacon-exclude-status=", "-n", "2")
        result.assert_outcomes(passed=8)
        data = _load_json_report(pytester)
        s = _results(data)["summary"]
        assert s["passed"] == 8
        assert s["tests"] == 8

    def test_xdist_worker_count_in_environment(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", "--beacon-exclude-status=", "-n", "2")
        data = _load_json_report(pytester)
        env = _results(data)["environment"]
        assert "xdistWorkers" in env

    def test_xdist_failed_tests_captured(self, pytester):
        pytester.makepyfile("""
            import pytest
            @pytest.mark.parametrize("n", [0, 1, 2])
            def test_some_fail(n):
                assert n != 1  # index 1 fails
        """)
        pytester.runpytest("--beacon", "--beacon-exclude-status=", "-n", "2")
        data = _load_json_report(pytester)
        s = _results(data)["summary"]
        assert s["passed"] == 2
        assert s["failed"] == 1

    def test_xdist_default_exclusion_keeps_passed_in_summary(self, pytester):
        """Even when passed tests are excluded from payload, xdist summary must keep passed counts."""
        pytester.makepyfile("""
            import pytest

            @pytest.mark.parametrize("n", list(range(6)))
            def test_only_passes(n):
                assert n >= 0
        """)
        result = pytester.runpytest("--beacon", "-n", "2")
        result.assert_outcomes(passed=6)

        data = _load_json_report(pytester)
        summary = _results(data)["summary"]

        assert summary["passed"] == 6
        assert summary["tests"] == 6
        assert _results(data)["tests"] == []

    def test_xdist_runtime_errors_not_deduplicated_by_file(self, pytester):
        """Runtime/setup errors from the same file should be preserved as separate test entries."""
        pytester.makepyfile("""
            import pytest

            @pytest.fixture
            def broken():
                raise RuntimeError("fixture boom")

            def test_error_a(broken):
                pass

            def test_error_b(broken):
                pass
        """)
        result = pytester.runpytest("--beacon", "--beacon-exclude-status=", "-n", "2")
        result.assert_outcomes(errors=2)

        data = _load_json_report(pytester)
        summary = _results(data)["summary"]
        errors = [t for t in _results(data)["tests"] if t["status"] == "error"]

        assert summary["error"] == 2
        assert summary["tests"] == 2
        assert len(errors) == 2


class TestHookwrapperFailures:
    def test_teardown_exception_in_other_plugin_does_not_drop_outcome(self, pytester):
        """If another hookwrapper crashes, beacon should still keep already executed outcomes."""
        pytester.makeconftest("""
            import pytest

            @pytest.hookimpl(hookwrapper=True)
            def pytest_runtest_makereport(item, call):
                outcome = yield
                report = outcome.get_result()
                if report.when == "call" and item.name == "test_broken_hook_target":
                    raise RuntimeError("synthetic teardown failure")
        """)
        pytester.makepyfile("""
            def test_broken_hook_target():
                assert False, "first failure"

            def test_regular_failure():
                assert False, "second failure"
        """)

        result = pytester.runpytest("--beacon", "--beacon-exclude-status=")
        assert result.ret == 3  # internal error from the synthetic crashing plugin
        data = _load_json_report(pytester)
        summary = _results(data)["summary"]

        assert summary["failed"] == 1
        assert summary["tests"] == 1


# ---------------------------------------------------------------------------
# HTTP URL export
# ---------------------------------------------------------------------------


class _CapturingHandler(BaseHTTPRequestHandler):
    received_bodies = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _CapturingHandler.received_bodies.append(json.loads(body))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass  # silence server logs


class TestHttpExport:
    def test_url_export_sends_metrics(self, pytester):
        _CapturingHandler.received_bodies = []
        server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request)
        thread.daemon = True
        thread.start()

        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", f"--beacon-url=http://127.0.0.1:{port}")

        thread.join(timeout=5)
        server.server_close()

        assert len(_CapturingHandler.received_bodies) == 1
        assert "metrics" in _CapturingHandler.received_bodies[0]

    def test_url_failure_does_not_crash_pytest(self, pytester):
        pytester.makepyfile("def test_pass(): pass")
        # Port 1 is typically refused — should fail gracefully
        result = pytester.runpytest("--beacon", "--beacon-url=http://127.0.0.1:1/metrics")
        # pytest itself should still exit cleanly (not crash)
        assert result.ret in (0, 1, 2, 5)  # any valid pytest exit code

    def test_url_and_file_both_produced(self, pytester):
        _CapturingHandler.received_bodies = []
        server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request)
        thread.daemon = True
        thread.start()

        target = pytester.path / "also_file.json"
        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest(
            "--beacon",
            f"--beacon-url=http://127.0.0.1:{port}",
            f"--beacon-file={target}",
        )

        thread.join(timeout=5)
        server.server_close()

        assert target.exists()
        assert len(_CapturingHandler.received_bodies) == 1

    def test_only_url_no_local_file_by_default(self, pytester):
        """When only --beacon-url is provided (no --beacon-file), no local file is written."""
        _CapturingHandler.received_bodies = []
        server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request)
        thread.daemon = True
        thread.start()

        pytester.makepyfile("def test_pass(): pass")
        pytester.runpytest("--beacon", f"--beacon-url=http://127.0.0.1:{port}")

        thread.join(timeout=5)
        server.server_close()

        assert list(pytester.path.glob("beacon_reports/*.json")) == []
