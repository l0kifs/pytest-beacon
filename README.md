# pytest-beacon

Highly customizable pytest reporting plugin. Generates [CTRF](https://ctrf.io) 1.0.0 reports with rich test metadata — marks, parameters, Allure IDs, environment — and exports them to a local file and/or a remote HTTP service.

## Features

- CTRF 1.0.0 compliant JSON/YAML reports
- Token-efficient by default (passed tests excluded from output, summary always accurate)
- Rich metadata: marks, parametrized params, Allure IDs, environment name
- HTTP export to a remote metrics service
- Full `pytest-xdist` support (parallel execution)
- Collection error tracking (import errors, syntax errors)
- Configurable via CLI flags and environment variables

## Installation

```bash
pip install pytest-beacon
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add pytest-beacon
```

## Usage

```bash
# Basic — writes to beacon_reports/report-YYYYMMDD-HHMMSS.json
pytest --beacon

# Custom output file
pytest --beacon --beacon-file=results.json

# YAML format
pytest --beacon --beacon-format=yaml

# Send to remote service
pytest --beacon --beacon-url=http://localhost:8000/api/v1/metrics

# Include all test statuses in report (default excludes passed)
pytest --beacon --beacon-exclude-status=''

# Include stdout/stderr for passed tests
pytest --beacon --beacon-verbose

# Works with xdist
pytest --beacon -n auto

# Attach arbitrary metadata to the report
pytest --beacon --beacon-meta build=123 --beacon-meta branch=main --beacon-meta triggered_by=ci
```

## CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--beacon` | off | Enable reporting |
| `--beacon-file PATH` | `beacon_reports/report-<ts>.json` | Output file. Bare filename → placed in `beacon_reports/` with timestamp. |
| `--beacon-url URL` | — | Full URL to POST the report to. |
| `--beacon-format json\|yaml` | `json` | Report serialisation format |
| `--beacon-verbose` | off | Include captured stdout/stderr for passed tests |
| `--beacon-exclude-status STATUSES` | `passed` | Comma-separated statuses to omit from report output. Empty string includes all. |
| `--beacon-meta KEY=VALUE` | — | Arbitrary metadata pair added to the report environment. Repeatable. |

## Environment Variables

All variables use the `PYTEST_BEACON__` prefix.

| Variable | Description |
|----------|-------------|
| `PYTEST_BEACON__REPORT_FORMAT` | Default report format |
| `PYTEST_BEACON__HTTP_TIMEOUT` | HTTP export timeout in seconds (default: `10.0`) |
| `PYTEST_BEACON__HTTP_MAX_RETRIES` | HTTP export retry attempts (default: `3`) |

Variables can also be set in a `.env` file at the project root.

## Report Format

```json
{
  "results": {
    "tool": { "name": "pytest", "version": "9.x" },
    "summary": {
      "tests": 12, "passed": 9, "failed": 2, "skipped": 1, "error": 0,
      "start": 1700000000000, "stop": 1700000005000
    },
    "tests": [
      {
        "name": "tests/test_api.py::test_login[admin]",
        "status": "failed",
        "duration": 142,
        "filePath": "tests/test_api.py",
        "line": 34,
        "message": "AssertionError: expected 200, got 401",
        "trace": "...",
        "marks": ["smoke", "auth"],
        "params": { "role": "admin" },
        "allureId": "TC-42"
      }
    ],
    "environment": { "pythonVersion": "3.12.0", "pytestVersion": "9.0.0", "xdistWorkers": 4, "build": "123", "branch": "main" },
    "extra": { "pluginName": "pytest-beacon", "pluginVersion": "0.1.0", "ctrf": "1.0.0" }
  }
}
```

Summary counters always reflect all tests regardless of `--beacon-exclude-status`.

## Remote HTTP Export

When `--beacon-url` is set, a POST request with a JSON body is sent to the specified URL:

```json
{
  "metrics": [
    {
      "test_nodeid": "tests/test_api.py::test_login[admin]",
      "test_name": "test_login[admin]",
      "test_result": "failed",
      "test_duration": 0.142,
      "test_marks": ["smoke", "auth"],
      "test_params": { "role": "admin" },
      "test_stacktrace": "...",
      "test_message": "AssertionError: expected 200, got 401",
      "test_allure_id": "TC-42"
    }
  ]
}
```

Export errors are logged and never interrupt test execution.

## Local Development

**Install dependencies:**

```bash
uv sync
```

**Run tests:**

```bash
uv run pytest tests/
```

**Run a quick smoke test against your own test suite:**

```bash
uv run pytest your_tests/ --beacon --beacon-exclude-status=
```

## Requirements

- Python 3.11+
- pytest 9.0+
