# Changelog

All notable changes to this project will be documented in this file.

## 0.6.0 - 2026-05-11

### Features

- Add TOON (Token-Oriented Object Notation) report format (`--beacon-format=toon`). TOON is a compact, indentation-based encoding optimised for LLM token efficiency, producing ~18% fewer tokens than compact JSON for typical reports.
- JSON report files are now written in compact format (no indentation) to reduce file size.

### Breaking Changes

- `params` field in CTRF report changed from an object `{"key": "value"}` to an array of `{"key": …, "value": …}` pairs. This gives all test objects a uniform schema, enabling tabular encoding in TOON.
- `allureId` is now stored as an integer when its value is all-digit (e.g. `42` instead of `"42"`). String values are preserved as-is.
- All optional test-level fields (`filePath`, `line`, `message`, `trace`, `failureLocation`, `marks`, `params`, `allureId`, `stdout`, `stderr`, `logs`, `consoleOutput`) are now always emitted with `null` when absent, instead of being omitted entirely.
- All optional log entry fields (`logger`, `timestamp`, `data`) are now always emitted with `null` when absent.

### Documentation

- Document TOON format in `README.md`: added example report, full structural schema, and format syntax reference.
- Update CTRF JSON report schema and examples to reflect new `params` and `allureId` types.
- Update CLI options table to include `toon` as a valid `--beacon-format` value.

## 0.5.0 - 2026-05-09

### Features

- Add opt-in console output capture via `--beacon-console-output`.
- Add `--beacon-console-lines` CLI option and `PYTEST_BEACON__CONSOLE_OUTPUT_LINES` env var to keep the last N stdout/stderr lines per stream per phase.
- Store captured console output separately from logs under `consoleOutput` in CTRF reports and `test_console_output` in HTTP export metrics.
- Include console truncation metadata with `truncated` and `omittedLines` fields.
- Capture stdlib logging directly from the logging system instead of relying on rendered pytest log sections.
- Capture Loguru records directly when Loguru is installed, including structured `extra` metadata.
- Add structured log record metadata under each log entry's `data` field.
- Change `--beacon-logs-max` behavior to keep the last N log entries per phase.

### Documentation

- Document direct log capture, console output capture, new CLI options, new env vars, CTRF fields, and HTTP payload fields in `README.md`.

### Tests

- Add dedicated console output e2e coverage in `tests/test_plugin_console_output_e2e.py`.
- Add real Loguru integration coverage by including Loguru in dev dependencies.
- Extend formatter and HTTP exporter tests for log metadata and console output fields.

## 0.4.0 - 2026-05-08

### Features

- Add opt-in log capture to CTRF reports and HTTP export via `--beacon-logs` flag.
- Capture per-phase log entries (setup, call, teardown) for every test, stored under a `logs` key in the CTRF test entry and as `test_logs` in HTTP export metrics.
- Capture collection-phase logs as `generalLogs` in the CTRF `results.extra` section.
- Add `--beacon-logs-level` CLI option (and `PYTEST_BEACON__LOGS_LEVEL` env var) to set the minimum log level captured (default: `WARNING`).
- Add `--beacon-logs-max` CLI option (and `PYTEST_BEACON__LOGS_MAX_PER_CATEGORY` env var) to cap the number of log entries per phase category (default: unlimited).
- Full xdist compatibility: per-test logs are serialized by workers and reconstructed on the master node before export.

### Tests

- Add `tests/test_plugin_logs_e2e.py` with 49 end-to-end tests covering: opt-in behaviour, per-phase capture, level filtering, max-entries cap, general logs, status-exclusion interaction, edge cases, xdist, and HTTP export.

## 0.3.0 - 2026-04-17

### Features

- Add `pytestSummary` field to `results.extra` in CTRF report, mirroring pytest's own terminal-reporter categories (`failed`, `passed`, `skipped`, `deselected`, `xfailed`, `xpassed`, `warnings`, `error`, `rerun`).
- Print a `Pytest:` summary line in local console output that matches pytest's terminal summary format, making it easy to compare beacon output with the pytest final line.
- Track teardown failures: tests that pass the call phase but raise in teardown are now correctly reclassified as `failed` and their summary counters updated accordingly.

### Tests

- Add formatter tests asserting `pytestSummary` is included in the CTRF `extra` section.
- Add e2e tests covering teardown failure reclassification and `pytestSummary` in exported reports.

## 0.2.0 - 2026-04-11

### Features

- Add separate status exclusion controls for local file report and HTTP export.
- Add `--beacon-file-exclude-status` CLI option (replaces `--beacon-exclude-status`) to omit statuses from the local file report. Default: `passed`.
- Add `--beacon-http-exclude-status` CLI option to omit statuses from the HTTP export independently of the file report. Default: `passed`.
- Add `PYTEST_BEACON__FILE_EXCLUDE_STATUSES` and `PYTEST_BEACON__HTTP_EXCLUDE_STATUSES` environment variable settings.

### Fixed

- Fix `pluginVersion` in CTRF report `extra` section — it was hardcoded to `"0.1.0"` and never updated with the actual installed version.

### Tests

- Add `TestSeparateExcludeStatuses` e2e test class covering positive and negative cases for independent HTTP/file exclude parameters.
- Update `test_extra_section` in formatter tests to assert against the live `app_version` setting rather than a hardcoded string.

## 0.1.1 - 2026-04-07

Patch release focused on report correctness and xdist reliability.

### Fixed

- Fix xdist summary aggregation when passed tests are excluded from exported test entries.
- Fix xdist merge logic to deduplicate only collection errors, while preserving multiple runtime/setup errors from the same file.
- Add fallback handling for makereport hookwrapper teardown exceptions to keep already executed test outcomes in beacon reports.

### Tests

- Add regression tests for xdist summary counters with default status exclusion.
- Add regression tests ensuring runtime errors from the same file are not dropped.
- Add regression tests for hookwrapper teardown exception resilience.

## 0.1.0 - 2026-04-07

Initial public release.

### Features

- Add a pytest plugin that generates CTRF 1.0.0 reports with rich test metadata.
- Support JSON and YAML report output with configurable local file export.
- Add HTTP export for test metrics with retry and timeout settings.
- Support pytest-xdist and collection error reporting.
- Expose CLI flags and environment-variable based configuration for report generation.

### Internal

- Add structured logging and end-to-end coverage for plugin behavior.
- Add unit tests for entities, formatters, exporters, helpers, and logging.
