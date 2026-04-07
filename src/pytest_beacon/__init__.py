"""Project package root."""

from __future__ import annotations

import logging

logging.getLogger("pytest_beacon").addHandler(logging.NullHandler())
