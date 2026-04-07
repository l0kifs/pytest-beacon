"""Logging helpers for pytest-beacon.

The project uses the standard library logging module so host applications can
control routing, formatting, and filtering with their normal logging setup.
"""

from __future__ import annotations

import logging
from typing import Any

_RESERVED_LOG_KWARGS = {"exc_info", "stack_info", "stacklevel", "extra"}


class BeaconLoggerAdapter(logging.LoggerAdapter):
    """LoggerAdapter that accepts structlog-style keyword context.

    Calls like ``log.info("message", url=url, attempt=1)`` are translated into
    stdlib ``extra`` data so existing call sites stay concise while remaining
    compatible with regular logging handlers and formatters.
    """

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = dict(self.extra)

        explicit_extra = kwargs.pop("extra", None)
        if explicit_extra:
            extra.update(explicit_extra)

        structured = {
            key: kwargs.pop(key)
            for key in list(kwargs)
            if key not in _RESERVED_LOG_KWARGS
        }
        if structured:
            extra.update(structured)

        if extra:
            kwargs["extra"] = extra

        return msg, kwargs

    def bind(self, **kwargs: Any) -> "BeaconLoggerAdapter":
        extra = dict(self.extra)
        extra.update(kwargs)
        return type(self)(self.logger, extra)


def get_logger(name: str) -> BeaconLoggerAdapter:
    """Return a logger adapter for the given module name."""
    return BeaconLoggerAdapter(logging.getLogger(name), {})