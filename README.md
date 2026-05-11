<div align="center">

![pytest-beacon](https://socialify.git.ci/l0kifs/pytest-beacon/image?description=0&font=Inter&language=1&name=1&owner=1&pattern=Signal&theme=Light)

# Pytest Beacon

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
![GitHub last commit](https://img.shields.io/github/last-commit/l0kifs/pytest-beacon)
![GitHub Release Date](https://img.shields.io/github/release-date/l0kifs/pytest-beacon?label=last%20release)

</div>

**Pytest Beacon** is a highly customizable pytest reporting plugin. Generates [CTRF](https://ctrf.io) 1.0.0 reports with rich test metadata — marks, parameters, Allure IDs, environment — and exports them to a local file and/or a remote HTTP service. Reports can be serialised as JSON, YAML, or **TOON** — a compact, indentation-based format designed for token-efficient LLM consumption.

### Why you might need this

- You want machine-readable test results that CI/CD pipelines can consume
- Your test suite is large and you need token-efficient reports (passed tests excluded by default)
- You feed test results into an LLM and want to minimise token cost
- You send test metrics to a remote service or dashboard for trend analysis
- You run tests in parallel with `pytest-xdist` and need a unified report
- You need collection errors (import errors, syntax errors) tracked alongside test results
- You want captured log output split by test phase (setup / call / teardown) directly in the report
- You want optional captured stdout/stderr in reports without mixing it into log records

---

## ✨ Features

- **CTRF 1.0.0 compliance**: JSON, YAML, or TOON reports following the Common Test Results Format standard
- **Token-efficient by default**: Passed tests excluded from output; summary counters are always accurate
- **Independent output filtering**: Separate exclude rules for local file and HTTP export
- **Rich metadata**: Marks, parametrized params, Allure IDs, and environment name per test
- **HTTP export**: POST reports to a remote metrics service after each run
- **xdist support**: Full `pytest-xdist` compatibility for parallel execution
- **Collection error tracking**: Import errors and syntax errors appear in the report
- **Direct log capture**: Structured per-phase stdlib logging and Loguru records with level filtering and entry capping
- **Optional console output capture**: Captured stdout/stderr per phase, keeping the last N lines with truncation metadata
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
# or for token-efficient LLM consumption:
pytest --beacon --beacon-file=results.toon --beacon-format=toon
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

**10. Capture stdout/stderr per test phase, keeping the last 50 lines**
```bash
pytest --beacon --beacon-console-output
```

**11. Capture stdout/stderr, keeping the last 20 lines per stream per phase**
```bash
pytest --beacon --beacon-console-output --beacon-console-lines=20
```

## 🛠 CLI Options

| Option | Default | Description |
| :--- | :--- | :--- |
| `--beacon` | off | Enable reporting |
| `--beacon-file PATH` | `beacon_reports/report-<ts>.json` | Output file. Bare filename → placed in `beacon_reports/` with timestamp. |
| `--beacon-url URL` | — | Full URL to POST the report to. |
| `--beacon-format json\|yaml\|toon` | `json` | Report serialisation format |
| `--beacon-verbose` | off | Include captured stdout/stderr for passed tests |
| `--beacon-file-exclude-status STATUSES` | `passed` | Comma-separated statuses to omit from the **local file** report. Empty string includes all. |
| `--beacon-http-exclude-status STATUSES` | `passed` | Comma-separated statuses to omit from the **HTTP export**. Empty string includes all. |
| `--beacon-meta KEY=VALUE` | — | Arbitrary metadata pair added to the report environment. Repeatable. |
| `--beacon-logs` | off | Enable direct log capture. Stdlib logging and Loguru records are split into setup / call / teardown phases per test. Logs from the collection phase appear as `generalLogs` in `extra`. |
| `--beacon-logs-level LEVEL` | `WARNING` | Minimum log level to include. Valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `--beacon-logs-max N` | unlimited | Maximum log entries per phase per test (and for general logs). The last entries are kept when the cap is reached. |
| `--beacon-console-output` | off | Include captured stdout/stderr in `consoleOutput` per test and `test_console_output` in HTTP metrics. |
| `--beacon-console-lines N` | `50` | Number of last stdout/stderr lines to keep per stream per phase. Includes truncation metadata when lines are omitted. |

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
| `PYTEST_BEACON__CONSOLE_OUTPUT_ENABLED` | `false` | Enable console output capture (equivalent to `--beacon-console-output`) |
| `PYTEST_BEACON__CONSOLE_OUTPUT_LINES` | `50` | Number of last stdout/stderr lines to keep per stream per phase |

### Logs vs Console Output

`--beacon-logs` captures log records from the logging system itself. It does not depend on pytest's rendered log-line format, so changing console log formatting does not break log capture. Standard-library logging is captured directly, and Loguru is captured directly when Loguru is installed. Pytest captured-log sections are still used as a fallback.

`--beacon-console-output` captures raw stdout/stderr separately. Plain `print()` output is stored under `consoleOutput`, not under `logs`.

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
        "params": [{"key": "role", "value": "admin"}],
        "allureId": 42,
        "stdout": "setting up admin session\n",
        "stderr": "",
        "logs": {
          "setup": [
            {
              "level": "WARNING",
              "message": "slow fixture detected",
              "logger": "app.fixtures",
              "timestamp": "2026-05-08T10:00:00+00:00",
              "data": {
                "filename": "conftest.py",
                "lineno": 12,
                "extra": { "fixture": "admin_session" }
              }
            }
          ],
          "call": [
            { "level": "ERROR", "message": "unexpected response code 401", "logger": "app.api" }
          ]
        },
        "consoleOutput": {
          "call": {
            "stdout": {
              "lines": ["request id: abc-123", "response code: 401"],
              "truncated": false,
              "omittedLines": 0
            },
            "stderr": {
              "lines": ["retry exhausted"],
              "truncated": false,
              "omittedLines": 0
            }
          },
          "teardown": {
            "stdout": {
              "lines": ["cleanup complete"],
              "truncated": true,
              "omittedLines": 3
            }
          }
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
      "pluginVersion": "0.5.0",
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
              "params":   { "type": "array", "items": { "type": "object", "required": ["key", "value"], "properties": { "key": { "type": "string" }, "value": { "type": "string" } } }, "description": "Parametrize parameters as a list of {key, value} pairs" },
              "allureId": { "type": ["string", "integer", "null"], "description": "Value of the @allure.id marker; numeric values are stored as integers" },
              "stdout":   { "type": "string", "description": "Captured stdout; present only with --beacon-verbose" },
              "stderr":   { "type": "string", "description": "Captured stderr; present only with --beacon-verbose" },
              "logs": {
                "type": "object",
                "description": "Captured stdlib logging / Loguru records grouped by phase; present only with --beacon-logs. Only non-empty phases are included.",
                "properties": {
                  "setup":    { "$ref": "#/$defs/logEntryArray" },
                  "call":     { "$ref": "#/$defs/logEntryArray" },
                  "teardown": { "$ref": "#/$defs/logEntryArray" }
                }
              },
              "consoleOutput": {
                "type": "object",
                "description": "Captured stdout/stderr grouped by phase; present only with --beacon-console-output. Only phases/streams with retained or truncated output are included.",
                "properties": {
                  "setup":    { "$ref": "#/$defs/consolePhaseOutput" },
                  "call":     { "$ref": "#/$defs/consolePhaseOutput" },
                  "teardown": { "$ref": "#/$defs/consolePhaseOutput" }
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
        "timestamp": { "type": "string", "description": "ISO-8601 timestamp if available" },
        "data":      { "type": "object", "description": "Structured logging metadata captured from the underlying log record" }
      }
    },
    "logEntryArray": {
      "type": "array",
      "items": { "$ref": "#/$defs/logEntry" }
    },
    "consoleStream": {
      "type": "object",
      "required": ["lines", "truncated", "omittedLines"],
      "properties": {
        "lines":        { "type": "array", "items": { "type": "string" }, "description": "Retained output lines" },
        "truncated":    { "type": "boolean", "description": "True when earlier lines were omitted" },
        "omittedLines": { "type": "integer", "description": "Number of omitted earlier lines" }
      }
    },
    "consolePhaseOutput": {
      "type": "object",
      "properties": {
        "stdout": { "$ref": "#/$defs/consoleStream" },
        "stderr": { "$ref": "#/$defs/consoleStream" }
      }
    }
  }
}
```

</details>

<details>
<summary>📄 <b>Example TOON Report</b> (click to expand)</summary>

TOON (Token-Oriented Object Notation) is a whitespace-indented format optimised for LLM token efficiency. Use `--beacon-format=toon` to emit it.

```
results:
  tool:
    name: pytest
    version: 9.0.0
  summary:
    tests: 12
    passed: 9
    failed: 2
    pending: 0
    skipped: 1
    error: 0
    other: 0
    start: 1700000000000
    stop: 1700000005000
  tests[1]:
    - name: "tests/test_api.py::test_login[admin]"
      status: failed
      duration: 142
      filePath: tests/test_api.py
      line: 34
      message: "AssertionError: expected 200, got 401"
      trace: "Traceback (most recent call last):\n  ..."
      failureLocation:
        file: tests/test_api.py
        line: 38
      marks[2]: smoke,auth
      params[1]{key,value}:
        role,admin
      allureId: 42
      stdout: "setting up admin session\n"
      stderr: ""
      logs:
        setup[1]:
          - level: WARNING
            message: slow fixture detected
            logger: app.fixtures
            timestamp: "2026-05-08T10:00:00+00:00"
            data:
              filename: conftest.py
              lineno: 12
              extra:
                fixture: admin_session
        call[1]{level,message,logger,timestamp,data}:
          ERROR,unexpected response code 401,app.api,null,null
      consoleOutput:
        call:
          stdout:
            lines[2]: "request id: abc-123","response code: 401"
            truncated: false
            omittedLines: 0
          stderr:
            lines[1]: retry exhausted
            truncated: false
            omittedLines: 0
        teardown:
          stdout:
            lines[1]: cleanup complete
            truncated: true
            omittedLines: 3
  environment:
    pythonVersion: 3.12.0
    pytestVersion: 9.0.0
    xdistWorkers: 4
    build: "123"
    branch: main
  extra:
    pluginName: pytest-beacon
    pluginVersion: 0.5.0
    ctrf: 1.0.0
    generatedAt: 1700000005000
    pytestSummary:
      failed: 2
      passed: 9
      skipped: 1
      deselected: 0
      xfailed: 0
      xpassed: 0
      warnings: 3
      error: 0
      rerun: 0
    generalLogs[1]{level,message,logger,timestamp,data}:
      WARNING,deprecated import path used,app.compat,"2026-05-08T10:00:00+00:00",null
```

</details>

<details>
<summary>📐 <b>TOON Report Schema</b> (click to expand)</summary>

Type annotations use `<type>` placeholders. `?` marks optional fields (present as `null` when absent). `# comment` lines are not part of the output.

```
results:
  tool:
    name: <string>
    version: <string>
  summary:
    tests: <integer>
    passed: <integer>
    failed: <integer>
    pending: <integer>
    skipped: <integer>
    error: <integer>
    other: <integer>
    start: <integer>          # epoch ms
    stop: <integer>           # epoch ms
  tests[N]:                   # N = number of included test results
    - name: <string>          # full pytest node ID
      status: passed|failed|skipped|error|other
      duration: <number>      # milliseconds
      filePath: <string|null>?
      line: <integer|null>?
      message: <string|null>?
      trace: <string|null>?
      failureLocation: <object|null>?
        file: <string>
        line: <integer>
      marks[N]: <string>,...  # N=0 → marks[0]: (empty); primitive inline array
      params[N]{key,value}:?  # tabular; null when no params
        <string>,<string>
        ...
      allureId: <string|integer|null>?
      stdout: <string|null>?
      stderr: <string|null>?
      logs: <object|null>?    # present only with --beacon-logs
        setup[N]{level,message,logger,timestamp,data}:   # tabular when data=null for all entries
          <string>,<string>,<string|null>,<string|null>,<null>
          ...
        # OR expanded form when any entry has a non-null data object:
        setup[N]:
          - level: <string>
            message: <string>
            logger: <string|null>
            timestamp: <string|null>  # ISO-8601
            data: <object|null>
              ...
        call[N]{level,message,logger,timestamp,data}:    # same rules as setup
          ...
        teardown[N]{level,message,logger,timestamp,data}:
          ...
      consoleOutput: <object|null>?   # present only with --beacon-console-output
        setup:?
          stdout:?
            lines[N]: <string>,...
            truncated: <boolean>
            omittedLines: <integer>
          stderr:?
            lines[N]: <string>,...
            truncated: <boolean>
            omittedLines: <integer>
        call:?
          stdout:?
            ...
          stderr:?
            ...
        teardown:?
          stdout:?
            ...
          stderr:?
            ...
  environment:
    pythonVersion: <string>
    pytestVersion: <string>
    xdistWorkers: <integer>?  # present only when pytest-xdist is active
    <key>: <string>           # zero or more --beacon-meta pairs
    ...
  extra:
    pluginName: <string>
    pluginVersion: <string>
    ctrf: <string>            # always "1.0.0"
    generatedAt: <integer>    # epoch ms
    pytestSummary:?           # present only when terminal reporter is available
      failed: <integer>
      passed: <integer>
      skipped: <integer>
      deselected: <integer>
      xfailed: <integer>
      xpassed: <integer>
      warnings: <integer>
      error: <integer>
      rerun: <integer>
    generalLogs[N]{level,message,logger,timestamp,data}:?   # tabular form
      <string>,<string>,<string|null>,<string|null>,<null>
      ...
    # OR expanded form when any entry has a non-null data object:
    generalLogs[N]:?
      - level: <string>
        message: <string>
        logger: <string|null>
        timestamp: <string|null>
        data: <object|null>
          ...
```

</details>

<details>
<summary>📐 <b>TOON Format Syntax</b> (click to expand)</summary>

TOON uses indentation (2 spaces per level) to express structure. The key encoding rules:

| Construct | TOON syntax | Example |
| :--- | :--- | :--- |
| Object field | `key: value` | `status: failed` |
| Nested object | indented block under `key:` | `failureLocation:\n  file: ...` |
| String — safe (no special chars) | unquoted | `status: failed` |
| String — contains spaces / special chars | double-quoted; only `\`, `"`, `\n`, `\r`, `\t` escaped | `message: "expected 200, got 401"` |
| `null` | `null` | `data: null` |
| Boolean | `true` / `false` | `truncated: false` |
| Number | no trailing zeros; whole floats as int | `duration: 142` |
| Primitive array | `key[N]: v1,v2,...` | `marks[2]: smoke,auth` |
| Array of uniform objects (all-primitive values) | `key[N]{f1,f2,...}:` header + one row per object | `params[1]{key,value}:\n  role,admin` |
| Array of objects (non-uniform or nested values) | `key[N]:` header + `- field: value` expanded items | `setup[1]:\n  - level: WARNING\n    message: ...` |

Field order within each object is preserved from the source dict. All optional test and log fields are always emitted (as `null` when absent) so the `tests` array and per-phase log arrays qualify for tabular encoding, which is the primary source of token savings over JSON.

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
      "test_params": [{"key": "role", "value": "admin"}],
      "test_stacktrace": "Traceback (most recent call last):\n  ...",
      "test_message": "AssertionError: expected 200, got 401",
      "test_allure_id": "TC-42",
      "test_logs": {
        "setup": [
          {
            "level": "WARNING",
            "message": "slow fixture detected",
            "logger": "app.fixtures",
            "timestamp": "2026-05-08T10:00:00+00:00",
            "data": { "filename": "conftest.py", "lineno": 12 }
          }
        ],
        "call": [
          { "level": "ERROR", "message": "unexpected response code 401", "logger": "app.api" }
        ]
      },
      "test_console_output": {
        "call": {
          "stdout": {
            "lines": ["request id: abc-123", "response code: 401"],
            "truncated": false,
            "omittedLines": 0
          },
          "stderr": {
            "lines": ["retry exhausted"],
            "truncated": false,
            "omittedLines": 0
          }
        }
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
          "test_params":   { "type": "array",            "items": { "type": "object", "required": ["key", "value"], "properties": { "key": { "type": "string" }, "value": { "type": "string" } } }, "description": "Parametrize parameters as a list of {key, value} pairs" },
          "test_stacktrace": { "type": ["string", "null"], "description": "Full traceback string" },
          "test_message":  { "type": ["string", "null"], "description": "Short failure or skip reason" },
          "test_allure_id": { "type": ["string", "null"], "description": "Value of the @allure.id marker" },
          "test_logs": {
            "type": "object",
            "description": "Captured stdlib logging / Loguru records grouped by phase; present only with --beacon-logs. Only non-empty phases are included.",
            "properties": {
              "setup":    { "$ref": "#/$defs/logEntryArray" },
              "call":     { "$ref": "#/$defs/logEntryArray" },
              "teardown": { "$ref": "#/$defs/logEntryArray" }
            }
          },
          "test_console_output": {
            "type": "object",
            "description": "Captured stdout/stderr grouped by phase; present only with --beacon-console-output. Only phases/streams with retained or truncated output are included.",
            "properties": {
              "setup":    { "$ref": "#/$defs/consolePhaseOutput" },
              "call":     { "$ref": "#/$defs/consolePhaseOutput" },
              "teardown": { "$ref": "#/$defs/consolePhaseOutput" }
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
        "timestamp": { "type": "string", "description": "ISO-8601 timestamp if available" },
        "data":      { "type": "object", "description": "Structured logging metadata captured from the underlying log record" }
      }
    },
    "logEntryArray": {
      "type": "array",
      "items": { "$ref": "#/$defs/logEntry" }
    },
    "consoleStream": {
      "type": "object",
      "required": ["lines", "truncated", "omittedLines"],
      "properties": {
        "lines":        { "type": "array", "items": { "type": "string" }, "description": "Retained output lines" },
        "truncated":    { "type": "boolean", "description": "True when earlier lines were omitted" },
        "omittedLines": { "type": "integer", "description": "Number of omitted earlier lines" }
      }
    },
    "consolePhaseOutput": {
      "type": "object",
      "properties": {
        "stdout": { "$ref": "#/$defs/consoleStream" },
        "stderr": { "$ref": "#/$defs/consoleStream" }
      }
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
