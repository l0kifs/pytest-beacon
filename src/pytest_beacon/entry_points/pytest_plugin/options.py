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
        choices=["json", "yaml"],
        help="Report serialisation format: json (default) or yaml",
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
