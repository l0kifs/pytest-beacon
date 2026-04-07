"""
File exporter: writes CTRF report to a JSON or YAML file.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from pytest_beacon.infrastructure.observability.logging import get_logger

log = get_logger(__name__)

_DEFAULT_DIR = "beacon_reports"


class FileExporter:
    """Writes a CTRF report dict to disk as JSON or YAML."""

    def __init__(self, output_file: str | None = None, fmt: str = "json") -> None:
        self._fmt = fmt if fmt in ("json", "yaml") else "json"
        self._output_path = self._resolve_path(output_file)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def export(self, report: dict[str, Any]) -> None:
        """Write *report* to disk. Never raises."""
        try:
            self._output_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            log.exception(
                "beacon.file_exporter: failed to create output directory",
                path=str(self._output_path),
            )
            return

        try:
            with self._output_path.open("w", encoding="utf-8") as fh:
                if self._fmt == "yaml":
                    yaml.dump(
                        report,
                        fh,
                        default_flow_style=False,
                        allow_unicode=True,
                        sort_keys=False,
                    )
                else:
                    json.dump(report, fh, indent=2, ensure_ascii=False)
        except Exception:
            log.exception(
                "beacon.file_exporter: failed to write report",
                path=str(self._output_path),
            )
            return

        self._print_summary(report)

    @property
    def output_path(self) -> Path:
        return self._output_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, user_file: str | None) -> Path:
        ext = f".{self._fmt}"
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        if not user_file:
            return Path(_DEFAULT_DIR) / f"report-{timestamp}{ext}"

        p = Path(user_file)
        if p.is_absolute() or p.parent != Path():
            return p.with_suffix(p.suffix or ext)

        # Bare filename → place in default dir with timestamp suffix
        return Path(_DEFAULT_DIR) / f"{p.stem}-{timestamp}{p.suffix or ext}"

    def _print_summary(self, report: dict[str, Any]) -> None:
        try:
            summary = report["results"]["summary"]
            sep = "=" * 60
            print(f"\n{sep}")
            print(f"pytest-beacon report: {self._output_path}")
            print(sep)
            print(f"Total:   {summary['tests']}")
            print(f"Passed:  {summary['passed']}")
            print(f"Failed:  {summary['failed']}")
            if summary.get("error", 0):
                print(f"Error:   {summary['error']}")
            print(f"Skipped: {summary['skipped']}")
            duration_s = (summary["stop"] - summary["start"]) / 1000
            print(f"Time:    {duration_s:.2f}s")
            print(f"{sep}\n")
        except Exception:
            pass
