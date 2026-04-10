<div align="center">

![pytest-beacon](https://socialify.git.ci/l0kifs/pytest-beacon/image?description=0&font=Inter&language=1&name=1&owner=1&pattern=Signal&theme=Light)

# Pytest Beacon

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
![GitHub last commit](https://img.shields.io/github/last-commit/l0kifs/pytest-beacon)
![GitHub Release Date](https://img.shields.io/github/release-date/l0kifs/pytest-beacon?label=last%20release)

</div>

**Pytest Beacon** is a highly customizable pytest reporting plugin. Generates [CTRF](https://ctrf.io) 1.0.0 reports with rich test metadata — marks, parameters, Allure IDs, environment — and exports them to a local file and/or a remote HTTP service.

### Why you might need this

- You want machine-readable test results that CI/CD pipelines can consume
- Your test suite is large and you need token-efficient reports (passed tests excluded by default)
- You send test metrics to a remote service or dashboard for trend analysis
- You run tests in parallel with `pytest-xdist` and need a unified report
- You need collection errors (import errors, syntax errors) tracked alongside test results

---

## ✨ Features

- **CTRF 1.0.0 compliance**: JSON/YAML reports following the Common Test Results Format standard
- **Token-efficient by default**: Passed tests excluded from output; summary counters are always accurate
- **Independent output filtering**: Separate exclude rules for local file and HTTP export
- **Rich metadata**: Marks, parametrized params, Allure IDs, and environment name per test
- **HTTP export**: POST reports to a remote metrics service after each run
- **xdist support**: Full `pytest-xdist` compatibility for parallel execution
- **Collection error tracking**: Import errors and syntax errors appear in the report
- **Flexible configuration**: CLI flags, environment variables, and `.env` file support

## 🚀 Installation

```bash
uv add pytest-beacon
# or
pip install pytest-beacon
```

## ⚡ Quick Start

**1. Generate a local report**
Writes to `beacon_reports/report-YYYYMMDD-HHMMSS.json` by default:
```bash
pytest --beacon
```

**2. Custom file and format**
```bash
pytest --beacon --beacon-file=results.json --beacon-format=yaml
```

**3. Send to a remote service**
```bash
pytest --beacon --beacon-url=http://localhost:8000/api/v1/metrics
```

**4. Include all statuses and captured output**
```bash
pytest --beacon --beacon-file-exclude-status='' --beacon-verbose
```

**7. Send all statuses to HTTP but keep local file lean**
```bash
pytest --beacon --beacon-url=http://localhost:8000/api/v1/metrics --beacon-http-exclude-status=''
```

**5. Parallel execution with xdist**
```bash
pytest --beacon -n auto
```

**6. Attach arbitrary metadata**
```bash
pytest --beacon --beacon-meta build=123 --beacon-meta branch=main --beacon-meta triggered_by=ci
```

## 🛠 CLI Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `--beacon` | off | Enable reporting |
| `--beacon-file PATH` | `beacon_reports/report-<ts>.json` | Output file. Bare filename → placed in `beacon_reports/` with timestamp. |
| `--beacon-url URL` | — | Full URL to POST the report to. |
| `--beacon-format json\|yaml` | `json` | Report serialisation format |
| `--beacon-verbose` | off | Include captured stdout/stderr for passed tests |
| `--beacon-file-exclude-status STATUSES` | `passed` | Comma-separated statuses to omit from the **local file** report. Empty string includes all. |
| `--beacon-http-exclude-status STATUSES` | `passed` | Comma-separated statuses to omit from the **HTTP export**. Empty string includes all. |
| `--beacon-meta KEY=VALUE` | — | Arbitrary metadata pair added to the report environment. Repeatable. |

### Environment Variables

All variables use the `PYTEST_BEACON__` prefix. Can also be set in a `.env` file at the project root.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PYTEST_BEACON__REPORT_FORMAT` | `json` | Default report format |
| `PYTEST_BEACON__FILE_EXCLUDE_STATUSES` | `passed` | Statuses to omit from local file report |
| `PYTEST_BEACON__HTTP_EXCLUDE_STATUSES` | `passed` | Statuses to omit from HTTP export |
| `PYTEST_BEACON__HTTP_TIMEOUT` | `10.0` | HTTP export timeout in seconds |
| `PYTEST_BEACON__HTTP_MAX_RETRIES` | `3` | HTTP export retry attempts |

## 📊 Report Format

Summary counters always reflect all tests regardless of `--beacon-file-exclude-status` or `--beacon-http-exclude-status`.

<details>
<summary>📄 <b>Example CTRF JSON Report</b> (click to expand)</summary>

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
    "extra": { "pluginName": "pytest-beacon", "pluginVersion": "0.2.0", "ctrf": "1.0.0" }
  }
}
```

</details>

## 📤 Remote HTTP Export

When `--beacon-url` is set, a POST request with a JSON body is sent to the specified URL after the run. Export errors are logged and never interrupt test execution.

<details>
<summary>📄 <b>Example HTTP Request Body</b> (click to expand)</summary>

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
  ],
  "environment": {
    "pythonVersion": "3.12.0",
    "pytestVersion": "9.0.0",
    "xdistWorkers": 4,
    "build": "123",
    "branch": "main"
  }
}
```

</details>

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
uv run pytest your_tests/ --beacon --beacon-file-exclude-status=
```

## ⚖️ License
MIT
