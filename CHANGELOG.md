# Changelog

All notable changes to this project will be documented in this file.

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