"""End-to-end integration tests for pytest-beacon console output capture."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def _load_json_report(pytester):
    reports = list(pytester.path.glob("beacon_reports/*.json"))
    assert reports, "No JSON report generated in beacon_reports/"
    return json.loads(reports[0].read_text())


def _tests(report):
    return report["results"]["tests"]


class TestConsoleOutputCapture:
    def test_console_output_absent_without_flag(self, pytester):
        pytester.makepyfile("""
            def test_prints():
                print("hello from stdout")
        """)
        pytester.runpytest("--beacon", "--beacon-file-exclude-status=")
        data = _load_json_report(pytester)
        assert "consoleOutput" not in _tests(data)[0]

    def test_console_output_captured_with_flag(self, pytester):
        pytester.makepyfile("""
            import sys

            def test_prints():
                print("hello from stdout")
                print("hello from stderr", file=sys.stderr)
        """)
        pytester.runpytest(
            "--beacon",
            "--beacon-console-output",
            "--beacon-file-exclude-status=",
        )
        data = _load_json_report(pytester)
        output = _tests(data)[0]["consoleOutput"]["call"]
        assert output["stdout"]["lines"] == ["hello from stdout"]
        assert output["stdout"]["truncated"] is False
        assert output["stdout"]["omittedLines"] == 0
        assert output["stderr"]["lines"] == ["hello from stderr"]

    def test_console_output_keeps_last_n_lines_per_stream_per_phase(self, pytester):
        pytester.makepyfile("""
            import sys

            def test_many_lines():
                for i in range(5):
                    print(f"out {i}")
                    print(f"err {i}", file=sys.stderr)
        """)
        pytester.runpytest(
            "--beacon",
            "--beacon-console-output",
            "--beacon-console-lines=2",
            "--beacon-file-exclude-status=",
        )
        data = _load_json_report(pytester)
        output = _tests(data)[0]["consoleOutput"]["call"]
        assert output["stdout"]["lines"] == ["out 3", "out 4"]
        assert output["stdout"]["truncated"] is True
        assert output["stdout"]["omittedLines"] == 3
        assert output["stderr"]["lines"] == ["err 3", "err 4"]
        assert output["stderr"]["truncated"] is True
        assert output["stderr"]["omittedLines"] == 3

    def test_console_output_truncation_metadata_when_limit_zero(self, pytester):
        pytester.makepyfile("""
            def test_zero_lines():
                print("hidden")
        """)
        pytester.runpytest(
            "--beacon",
            "--beacon-console-output",
            "--beacon-console-lines=0",
            "--beacon-file-exclude-status=",
        )
        data = _load_json_report(pytester)
        stdout = _tests(data)[0]["consoleOutput"]["call"]["stdout"]
        assert stdout["lines"] == []
        assert stdout["truncated"] is True
        assert stdout["omittedLines"] == 1


class _CapturingHandler(BaseHTTPRequestHandler):
    received_bodies: list = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _CapturingHandler.received_bodies.append(json.loads(body))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def _run_with_http_server(pytester, *pytest_args):
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


class TestConsoleOutputHttpExport:
    def test_console_output_present_in_http_payload_when_flag_set(self, pytester):
        pytester.makepyfile("""
            def test_prints():
                for i in range(3):
                    print(f"http output {i}")
        """)
        body = _run_with_http_server(
            pytester,
            "--beacon",
            "--beacon-console-output",
            "--beacon-console-lines=2",
            "--beacon-http-exclude-status=",
        )
        output = body["metrics"][0]["test_console_output"]["call"]["stdout"]
        assert output["lines"] == ["http output 1", "http output 2"]
        assert output["truncated"] is True
        assert output["omittedLines"] == 1
