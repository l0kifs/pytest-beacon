# Changelog

All notable changes to this project will be documented in this file.

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