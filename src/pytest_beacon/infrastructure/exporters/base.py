"""
Abstract exporter protocol.
Any callable that satisfies this protocol can be used as a report exporter.
"""
from typing import Any, Protocol


class BaseExporter(Protocol):
    def export(self, report: dict[str, Any]) -> None:
        """Persist or transmit *report*. Must not raise."""
        ...
