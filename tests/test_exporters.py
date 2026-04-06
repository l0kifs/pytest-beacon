"""Unit tests for FileExporter and HttpExporter."""
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import httpx
import pytest
import yaml

from pytest_beacon.infrastructure.exporters.file_exporter import FileExporter
from pytest_beacon.infrastructure.exporters.http_exporter import HttpExporter


_SAMPLE_REPORT = {
    "results": {
        "tool": {"name": "pytest", "version": "9.0.0"},
        "summary": {"tests": 2, "passed": 1, "failed": 1, "skipped": 0, "error": 0, "other": 0, "pending": 0, "start": 1000, "stop": 2000},
        "tests": [
            {"name": "tests/t.py::test_fail", "status": "failed", "duration": 50},
        ],
        "environment": {"pythonVersion": "3.12.0", "pytestVersion": "9.0.0"},
        "extra": {"pluginName": "pytest-beacon", "pluginVersion": "0.1.0", "ctrf": "1.0.0", "generatedAt": 2000},
    }
}


# ===========================================================================
# FileExporter
# ===========================================================================


class TestFileExporterPathResolution:
    def test_default_path_in_beacon_reports(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        exp = FileExporter()
        assert exp.output_path.parent.name == "beacon_reports"
        assert exp.output_path.suffix == ".json"

    def test_default_path_has_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        exp = FileExporter()
        name = exp.output_path.name
        assert name.startswith("report-")

    def test_absolute_path_preserved(self, tmp_path):
        target = tmp_path / "mydir" / "out.json"
        exp = FileExporter(str(target))
        assert exp.output_path == target

    def test_relative_path_with_dir_preserved(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        exp = FileExporter("subdir/report.json")
        assert exp.output_path == Path("subdir/report.json")

    def test_bare_filename_placed_in_beacon_reports(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        exp = FileExporter("myreport.json")
        assert exp.output_path.parent.name == "beacon_reports"
        assert "myreport" in exp.output_path.name

    def test_bare_filename_gets_timestamp(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        exp = FileExporter("myreport")
        # timestamp makes it unique
        assert exp.output_path.name != "myreport.json"
        assert "myreport" in exp.output_path.name

    def test_yaml_format_ext(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        exp = FileExporter(fmt="yaml")
        assert exp.output_path.suffix == ".yaml"

    def test_invalid_format_defaults_to_json(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        exp = FileExporter(fmt="xml")
        assert exp.output_path.suffix == ".json"


class TestFileExporterWrite:
    def test_writes_json_file(self, tmp_path):
        out = tmp_path / "report.json"
        exp = FileExporter(str(out))
        exp.export(_SAMPLE_REPORT)
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["results"]["summary"]["tests"] == 2

    def test_writes_yaml_file(self, tmp_path):
        out = tmp_path / "report.yaml"
        exp = FileExporter(str(out), fmt="yaml")
        exp.export(_SAMPLE_REPORT)
        assert out.exists()
        data = yaml.safe_load(out.read_text())
        assert data["results"]["summary"]["tests"] == 2

    def test_creates_parent_directories(self, tmp_path):
        out = tmp_path / "nested" / "deeply" / "report.json"
        exp = FileExporter(str(out))
        exp.export(_SAMPLE_REPORT)
        assert out.exists()

    def test_default_path_creates_beacon_reports_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        exp = FileExporter()
        exp.export(_SAMPLE_REPORT)
        assert (tmp_path / "beacon_reports").is_dir()
        assert exp.output_path.exists()

    def test_export_never_raises_on_bad_directory(self, tmp_path):
        # Simulate unwritable path — export should swallow the error
        exp = FileExporter.__new__(FileExporter)
        exp._fmt = "json"
        exp._output_path = Path("/root/no_permission/report.json")
        # Should not raise
        exp.export(_SAMPLE_REPORT)

    def test_prints_summary_to_stdout(self, tmp_path, capsys):
        out = tmp_path / "report.json"
        exp = FileExporter(str(out))
        exp.export(_SAMPLE_REPORT)
        captured = capsys.readouterr()
        assert "pytest-beacon report" in captured.out
        assert "Total" in captured.out
        assert "Failed" in captured.out

    def test_json_is_valid_and_complete(self, tmp_path):
        out = tmp_path / "report.json"
        exp = FileExporter(str(out))
        exp.export(_SAMPLE_REPORT)
        data = json.loads(out.read_text())
        assert "results" in data
        assert "tool" in data["results"]
        assert "summary" in data["results"]
        assert "tests" in data["results"]


# ===========================================================================
# HttpExporter
# ===========================================================================


def _mock_response(status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="error",
            request=MagicMock(),
            response=MagicMock(status_code=status_code, text="bad request"),
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestHttpExporterPayload:
    def test_posts_to_configured_url(self):
        exp = HttpExporter("http://example.com/api/metrics")
        with patch("httpx.post", return_value=_mock_response()) as mock_post:
            exp.export(_SAMPLE_REPORT)
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "http://example.com/api/metrics"

    def test_payload_structure(self):
        exp = HttpExporter("http://example.com/api")
        with patch("httpx.post", return_value=_mock_response()) as mock_post:
            exp.export(_SAMPLE_REPORT)
        payload = mock_post.call_args[1]["json"]
        assert "metrics" in payload
        assert isinstance(payload["metrics"], list)

    def test_metric_fields(self):
        exp = HttpExporter("http://example.com/api")
        with patch("httpx.post", return_value=_mock_response()) as mock_post:
            exp.export(_SAMPLE_REPORT)
        metric = mock_post.call_args[1]["json"]["metrics"][0]
        assert metric["test_nodeid"] == "tests/t.py::test_fail"
        assert metric["test_name"] == "test_fail"
        assert metric["test_result"] == "failed"
        assert metric["test_duration"] == pytest.approx(0.05)  # 50ms → 0.05s

    def test_duration_converted_ms_to_seconds(self):
        report = {**_SAMPLE_REPORT}
        report["results"] = {**report["results"], "tests": [{"name": "t::t", "status": "passed", "duration": 1000}]}
        exp = HttpExporter("http://x.com")
        with patch("httpx.post", return_value=_mock_response()) as mock_post:
            exp.export(report)
        metric = mock_post.call_args[1]["json"]["metrics"][0]
        assert metric["test_duration"] == pytest.approx(1.0)

    def test_optional_fields_present(self):
        report = {
            "results": {
                "summary": {},
                "tests": [{
                    "name": "t::t",
                    "status": "failed",
                    "duration": 0,
                    "marks": ["smoke"],
                    "params": {"x": 1},
                    "trace": "tb...",
                    "message": "boom",
                    "allureId": "TC-1",
                }],
            }
        }
        exp = HttpExporter("http://x.com")
        with patch("httpx.post", return_value=_mock_response()) as mock_post:
            exp.export(report)
        metric = mock_post.call_args[1]["json"]["metrics"][0]
        assert metric["test_marks"] == ["smoke"]
        assert metric["test_params"] == {"x": 1}
        assert metric["test_stacktrace"] == "tb..."
        assert metric["test_message"] == "boom"
        assert metric["test_allure_id"] == "TC-1"

    def test_empty_tests_list(self):
        report = {"results": {"summary": {}, "tests": []}}
        exp = HttpExporter("http://x.com")
        with patch("httpx.post", return_value=_mock_response()) as mock_post:
            exp.export(report)
        assert mock_post.call_args[1]["json"]["metrics"] == []


class TestHttpExporterRetry:
    def test_retries_on_timeout(self):
        exp = HttpExporter("http://x.com", max_retries=3)
        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")) as mock_post:
            exp.export(_SAMPLE_REPORT)
        assert mock_post.call_count == 3

    def test_no_retry_on_4xx(self):
        exp = HttpExporter("http://x.com", max_retries=3)
        with patch("httpx.post", return_value=_mock_response(400)) as mock_post:
            exp.export(_SAMPLE_REPORT)
        assert mock_post.call_count == 1

    def test_no_retry_on_5xx(self):
        exp = HttpExporter("http://x.com", max_retries=3)
        with patch("httpx.post", return_value=_mock_response(500)) as mock_post:
            exp.export(_SAMPLE_REPORT)
        assert mock_post.call_count == 1

    def test_retries_on_generic_exception(self):
        exp = HttpExporter("http://x.com", max_retries=2)
        with patch("httpx.post", side_effect=ConnectionError("refused")) as mock_post:
            exp.export(_SAMPLE_REPORT)
        assert mock_post.call_count == 2

    def test_export_never_raises(self):
        exp = HttpExporter("http://x.com", max_retries=1)
        with patch("httpx.post", side_effect=RuntimeError("unexpected")):
            exp.export(_SAMPLE_REPORT)  # must not raise

    def test_timeout_passed_to_httpx(self):
        exp = HttpExporter("http://x.com", timeout=42.0, max_retries=1)
        with patch("httpx.post", return_value=_mock_response()) as mock_post:
            exp.export(_SAMPLE_REPORT)
        assert mock_post.call_args[1]["timeout"] == 42.0

    def test_payload_build_error_does_not_raise(self):
        exp = HttpExporter("http://x.com")
        # Pass a report that will cause _build_payload to fail
        with patch.object(exp, "_build_payload", side_effect=ValueError("bad")):
            exp.export(_SAMPLE_REPORT)  # must not raise
