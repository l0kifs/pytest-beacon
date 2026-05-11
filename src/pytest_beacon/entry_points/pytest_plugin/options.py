"""
CLI option definitions for the pytest-beacon plugin.
"""
import pytest


def add_options(parser: pytest.Parser) -> None:
    group = parser.getgroup("beacon", "pytest-beacon reporting")
    group.addoption(
        "--beacon",
        action="store_true",
        default=False,
        help="Enable pytest-beacon reporting",
    )
    group.addoption(
        "--beacon-file",
        action="store",
        default=None,
        metavar="PATH",
        help=(
            "Output file for the report. "
            "Bare filename → saved in beacon_reports/ with timestamp. "
            "Relative or absolute path → used as-is. "
            "Default: beacon_reports/report-YYYYMMDD-HHMMSS.json"
        ),
    )
    group.addoption(
        "--beacon-url",
        action="store",
        default=None,
        metavar="URL",
        help="Full URL to POST the report to (e.g. http://localhost:8000/api/v1/metrics)",
    )
    group.addoption(
        "--beacon-format",
        action="store",
        default="json",
        choices=["json", "yaml", "toon"],
        help="Report serialisation format: json (default), yaml, or toon",
    )
    group.addoption(
        "--beacon-verbose",
        action="store_true",
        default=False,
        help="Include stdout/stderr captured from passed tests (increases report size)",
    )
    group.addoption(
        "--beacon-file-exclude-status",
        action="store",
        default="passed",
        metavar="STATUSES",
        help=(
            "Comma-separated test statuses to omit from the local file report. "
            "Summary counters are always accurate regardless of this setting. "
            "Valid values: passed, failed, skipped, error. "
            "Default: 'passed'. "
            "Use empty string to include all: --beacon-file-exclude-status=''"
        ),
    )
    group.addoption(
        "--beacon-http-exclude-status",
        action="store",
        default=None,
        metavar="STATUSES",
        help=(
            "Comma-separated test statuses to omit from the HTTP export. "
            "Falls back to --beacon-file-exclude-status if not set. "
            "Valid values: passed, failed, skipped, error. "
            "Default: same as --beacon-file-exclude-status. "
            "Use empty string to include all: --beacon-http-exclude-status=''"
        ),
    )
    group.addoption(
        "--beacon-meta",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help=(
            "Arbitrary metadata key-value pair to include in the report environment section. "
            "Can be specified multiple times. "
            "Example: --beacon-meta build=123 --beacon-meta branch=main"
        ),
    )
    group.addoption(
        "--beacon-logs",
        action="store_true",
        default=False,
        help=(
            "Enable log capture in the report. "
            "Logs are split by phase (setup, call, teardown) per test. "
            "Logs captured outside tests (collection phase) are reported as general logs."
        ),
    )
    group.addoption(
        "--beacon-logs-level",
        action="store",
        default="WARNING",
        metavar="LEVEL",
        help=(
            "Minimum log level to include in the report. "
            "Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL. "
            "Default: WARNING"
        ),
    )
    group.addoption(
        "--beacon-logs-max",
        action="store",
        default=None,
        type=int,
        metavar="N",
        help=(
            "Maximum number of log entries per phase category (setup, call, teardown) per test "
            "and for general logs. Default: unlimited."
        ),
    )
    group.addoption(
        "--beacon-console-output",
        action="store_true",
        default=False,
        help=(
            "Include captured stdout/stderr in the report. "
            "Console output is split by phase (setup, call, teardown) per test."
        ),
    )
    group.addoption(
        "--beacon-console-lines",
        action="store",
        default=50,
        type=int,
        metavar="N",
        help=(
            "Number of last stdout/stderr lines to keep per phase per test "
            "when --beacon-console-output is enabled. Default: 50."
        ),
    )
