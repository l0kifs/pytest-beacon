# Changelog

All notable changes to this project will be documented in this file.

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