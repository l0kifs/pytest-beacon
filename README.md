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
- You want captured log output split by test phase (setup / call / teardown) directly in the report

---

## ✨ Features

- **CTRF 1.0.0 compliance**: JSON/YAML reports following the Common Test Results Format standard
- **Token-efficient by default**: Passed tests excluded from output; summary counters are always accurate
- **Independent output filtering**: Separate exclude rules for local file and HTTP export
- **Rich metadata**: Marks, parametrized params, Allure IDs, and environment name per test
- **HTTP export**: POST reports to a remote metrics service after each run
- **xdist support**: Full `pytest-xdist` compatibility for parallel execution
- **Collection error tracking**: Import errors and syntax errors appear in the report
- **Log capture**: Structured per-phase logs (setup / call / teardown) with level filtering and entry capping
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

**5. Send all statuses to HTTP but keep local file lean**
```bash
pytest --beacon --beacon-url=http://localhost:8000/api/v1/metrics --beacon-http-exclude-status=''
```

**6. Parallel execution with xdist**
```bash
pytest --beacon -n auto
```

**7. Attach arbitrary metadata**
```bash
pytest --beacon --beacon-meta build=123 --beacon-meta branch=main --beacon-meta triggered_by=ci
```

**8. Capture logs per test phase**
```bash
pytest --beacon --beacon-logs
```

**9. Capture DEBUG-and-above logs, capped at 50 entries per phase**
```bash
pytest --beacon --beacon-logs --beacon-logs-level=DEBUG --beacon-logs-max=50
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
| `--beacon-logs` | off | Enable log capture. Logs are split into setup / call / teardown phases per test. Logs from the collection phase appear as `generalLogs` in `extra`. |
| `--beacon-logs-level LEVEL` | `WARNING` | Minimum log level to include. Valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `--beacon-logs-max N` | unlimited | Maximum log entries per phase per test (and for general logs). Earlier entries are kept when the cap is reached. |

### Environment Variables

All variables use the `PYTEST_BEACON__` prefix. Can also be set in a `.env` file at the project root.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PYTEST_BEACON__REPORT_FORMAT` | `json` | Default report format |
| `PYTEST_BEACON__FILE_EXCLUDE_STATUSES` | `passed` | Statuses to omit from local file report |
| `PYTEST_BEACON__HTTP_EXCLUDE_STATUSES` | `passed` | Statuses to omit from HTTP export |
| `PYTEST_BEACON__HTTP_TIMEOUT` | `10.0` | HTTP export timeout in seconds |
| `PYTEST_BEACON__HTTP_MAX_RETRIES` | `3` | HTTP export retry attempts |
| `PYTEST_BEACON__LOGS_ENABLED` | `false` | Enable log capture (equivalent to `--beacon-logs`) |
| `PYTEST_BEACON__LOGS_LEVEL` | `WARNING` | Minimum log level to capture |
| `PYTEST_BEACON__LOGS_MAX_PER_CATEGORY` | — | Max log entries per phase per test |

## 📊 Report Format

Summary counters always reflect all tests regardless of `--beacon-file-exclude-status` or `--beacon-http-exclude-status`.

Beacon also stores a pytest-style summary in `results.extra.pytestSummary` when pytest's terminal reporter is available. This mirrors pytest's own terminal categories as closely as possible, which makes it easy to compare beacon output with the pytest final line.

The local console output includes this as an extra line, for example:

```text
Pytest:  79 failed, 759 passed, 123 skipped, 3 xfailed, 57 warnings, 12 errors, 4 rerun in 1211.04s
```

<details>
<summary>📄 <b>Example CTRF JSON Report</b> (click to expand)</summary>

```json
{
  "results": {
    "tool": { "name": "pytest", "version": "9.0.0" },
    "summary": {
      "tests": 12,
      "passed": 9,
      "failed": 2,
      "pending": 0,
      "skipped": 1,
      "error": 0,
      "other": 0,
      "start": 1700000000000,
      "stop": 1700000005000
    },
    "tests": [
      {
        "name": "tests/test_api.py::test_login[admin]",
        "status": "failed",
        "duration": 142,
        "filePath": "tests/test_api.py",
        "line": 34,
        "message": "AssertionError: expected 200, got 401",
        "trace": "Traceback (most recent call last):\n  ...",
        "failureLocation": { "file": "tests/test_api.py", "line": 38 },
        "marks": ["smoke", "auth"],
        "params": { "role": "admin" },
        "allureId": "TC-42",
        "stdout": "setting up admin session\n",
        "stderr": "",
        "logs": {
          "setup": [
            { "level": "WARNING", "message": "slow fixture detected", "logger": "app.fixtures" }
          ],
          "call": [
            { "level": "ERROR", "message": "unexpected response code 401", "logger": "app.api" }
          ]
        }
      }
    ],
    "environment": {
      "pythonVersion": "3.12.0",
      "pytestVersion": "9.0.0",
      "xdistWorkers": 4,
      "build": "123",
      "branch": "main"
    },
    "extra": {
      "pluginName": "pytest-beacon",
      "pluginVersion": "0.4.0",
      "ctrf": "1.0.0",
      "generatedAt": 1700000005000,
      "pytestSummary": {
        "failed": 2,
        "passed": 9,
        "skipped": 1,
        "deselected": 0,
        "xfailed": 0,
        "xpassed": 0,
        "warnings": 3,
        "error": 0,
        "rerun": 0
      },
      "generalLogs": [
        { "level": "WARNING", "message": "deprecated import path used", "logger": "app.compat", "timestamp": "2026-05-08T10:00:00+00:00" }
      ]
    }
  }
}
```

</details>

<details>
<summary>📐 <b>CTRF JSON Report Schema</b> (click to expand)</summary>

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CTRF Report",
  "type": "object",
  "required": ["results"],
  "properties": {
    "results": {
      "type": "object",
      "required": ["tool", "summary", "tests", "environment", "extra"],
      "properties": {
        "tool": {
          "type": "object",
          "required": ["name", "version"],
          "properties": {
            "name":    { "type": "string", "example": "pytest" },
            "version": { "type": "string", "example": "9.0.0" }
          }
        },
        "summary": {
          "type": "object",
          "required": ["tests", "passed", "failed", "pending", "skipped", "error", "other", "start", "stop"],
          "properties": {
            "tests":   { "type": "integer", "description": "Total number of collected tests" },
            "passed":  { "type": "integer" },
            "failed":  { "type": "integer" },
            "pending": { "type": "integer" },
            "skipped": { "type": "integer" },
            "error":   { "type": "integer" },
            "other":   { "type": "integer" },
            "start":   { "type": "integer", "description": "Session start time (epoch ms)" },
            "stop":    { "type": "integer", "description": "Session stop time (epoch ms)" }
          }
        },
        "tests": {
          "type": "array",
          "description": "Test results; statuses in --beacon-file-exclude-status are omitted",
          "items": {
            "type": "object",
            "required": ["name", "status", "duration"],
            "properties": {
              "name":     { "type": "string", "description": "Full pytest node ID" },
              "status":   { "type": "string", "enum": ["passed", "failed", "skipped", "error", "other"] },
              "duration": { "type": "number", "description": "Test duration in milliseconds" },
              "filePath": { "type": "string", "description": "Source file path" },
              "line":     { "type": "integer", "description": "Line number of the test function" },
              "message":  { "type": "string", "description": "Short failure or skip reason" },
              "trace":    { "type": "string", "description": "Full traceback string" },
              "failureLocation": {
                "type": "object",
                "description": "Exact location of the assertion / exception that caused the failure",
                "required": ["file", "line"],
                "properties": {
                  "file": { "type": "string" },
                  "line": { "type": "integer" }
                }
              },
              "marks":    { "type": "array", "items": { "type": "string" }, "description": "pytest marks applied to the test" },
              "params":   { "type": "object", "description": "Parametrize parameters (key → value)" },
              "allureId": { "type": "string", "description": "Value of the @allure.id marker" },
              "stdout":   { "type": "string", "description": "Captured stdout; present only with --beacon-verbose" },
              "stderr":   { "type": "string", "description": "Captured stderr; present only with --beacon-verbose" },
              "logs": {
                "type": "object",
                "description": "Captured log entries grouped by phase; present only with --beacon-logs. Only non-empty phases are included.",
                "properties": {
                  "setup":    { "$ref": "#/$defs/logEntryArray" },
                  "call":     { "$ref": "#/$defs/logEntryArray" },
                  "teardown": { "$ref": "#/$defs/logEntryArray" }
                }
              }
            }
          }
        },
        "environment": {
          "type": "object",
          "required": ["pythonVersion", "pytestVersion"],
          "properties": {
            "pythonVersion": { "type": "string" },
            "pytestVersion": { "type": "string" },
            "xdistWorkers":  { "type": "integer", "description": "Number of xdist workers; present only when pytest-xdist is active" }
          },
          "additionalProperties": { "description": "Extra key/value pairs injected via --beacon-meta" }
        },
        "extra": {
          "type": "object",
          "required": ["pluginName", "pluginVersion", "ctrf", "generatedAt"],
          "properties": {
            "pluginName":    { "type": "string", "example": "pytest-beacon" },
            "pluginVersion": { "type": "string" },
            "ctrf":          { "type": "string", "example": "1.0.0" },
            "generatedAt":   { "type": "integer", "description": "Report generation time (epoch ms)" },
            "pytestSummary": {
              "type": "object",
              "description": "Mirrors pytest terminal summary counters; present only when the terminal reporter is available",
              "required": ["failed", "passed", "skipped", "deselected", "xfailed", "xpassed", "warnings", "error", "rerun"],
              "properties": {
                "failed":     { "type": "integer" },
                "passed":     { "type": "integer" },
                "skipped":    { "type": "integer" },
                "deselected": { "type": "integer" },
                "xfailed":    { "type": "integer" },
                "xpassed":    { "type": "integer" },
                "warnings":   { "type": "integer" },
                "error":      { "type": "integer" },
                "rerun":      { "type": "integer" }
              }
            },
            "generalLogs": {
              "$ref": "#/$defs/logEntryArray",
              "description": "Log entries captured during the collection phase; present only with --beacon-logs when collection-phase logs exist."
            }
          }
        }
      }
    }
  },
  "$defs": {
    "logEntry": {
      "type": "object",
      "required": ["level", "message"],
      "properties": {
        "level":     { "type": "string", "description": "Log level name, e.g. WARNING, ERROR" },
        "message":   { "type": "string", "description": "Formatted log message" },
        "logger":    { "type": "string", "description": "Logger name (dotted module path)" },
        "timestamp": { "type": "string", "description": "ISO-8601 timestamp if available" }
      }
    },
    "logEntryArray": {
      "type": "array",
      "items": { "$ref": "#/$defs/logEntry" }
    }
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
      "test_stacktrace": "Traceback (most recent call last):\n  ...",
      "test_message": "AssertionError: expected 200, got 401",
      "test_allure_id": "TC-42",
      "test_logs": {
        "setup": [
          { "level": "WARNING", "message": "slow fixture detected", "logger": "app.fixtures" }
        ],
        "call": [
          { "level": "ERROR", "message": "unexpected response code 401", "logger": "app.api" }
        ]
      }
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

<details>
<summary>📐 <b>HTTP Request Body Schema</b> (click to expand)</summary>

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "HTTP Export Payload",
  "type": "object",
  "required": ["metrics", "environment"],
  "properties": {
    "metrics": {
      "type": "array",
      "description": "One entry per test result; statuses in --beacon-http-exclude-status are omitted",
      "items": {
        "type": "object",
        "required": ["test_nodeid", "test_name", "test_result", "test_duration", "test_marks", "test_params"],
        "properties": {
          "test_nodeid":    { "type": "string",           "description": "Full pytest node ID" },
          "test_name":     { "type": "string",           "description": "Short test name (part after the last ::)" },
          "test_result":   { "type": "string",           "enum": ["passed", "failed", "skipped", "error", "other"] },
          "test_duration": { "type": "number",           "description": "Test duration in seconds" },
          "test_marks":    { "type": "array",            "items": { "type": "string" }, "description": "pytest marks applied to the test" },
          "test_params":   { "type": "object",           "description": "Parametrize parameters (key → value)" },
          "test_stacktrace": { "type": ["string", "null"], "description": "Full traceback string" },
          "test_message":  { "type": ["string", "null"], "description": "Short failure or skip reason" },
          "test_allure_id": { "type": ["string", "null"], "description": "Value of the @allure.id marker" },
          "test_logs": {
            "type": "object",
            "description": "Captured log entries grouped by phase; present only with --beacon-logs. Only non-empty phases are included.",
            "properties": {
              "setup":    { "$ref": "#/$defs/logEntryArray" },
              "call":     { "$ref": "#/$defs/logEntryArray" },
              "teardown": { "$ref": "#/$defs/logEntryArray" }
            }
          }
        }
      }
    },
    "environment": {
      "type": "object",
      "required": ["pythonVersion", "pytestVersion"],
      "properties": {
        "pythonVersion": { "type": "string" },
        "pytestVersion": { "type": "string" },
        "xdistWorkers":  { "type": "integer", "description": "Number of xdist workers; present only when pytest-xdist is active" }
      },
      "additionalProperties": { "description": "Extra key/value pairs injected via --beacon-meta" }
    }
  },
  "$defs": {
    "logEntry": {
      "type": "object",
      "required": ["level", "message"],
      "properties": {
        "level":     { "type": "string", "description": "Log level name, e.g. WARNING, ERROR" },
        "message":   { "type": "string", "description": "Formatted log message" },
        "logger":    { "type": "string", "description": "Logger name (dotted module path)" },
        "timestamp": { "type": "string", "description": "ISO-8601 timestamp if available" }
      }
    },
    "logEntryArray": {
      "type": "array",
      "items": { "$ref": "#/$defs/logEntry" }
    }
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
