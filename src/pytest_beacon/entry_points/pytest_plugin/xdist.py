"""
xdist worker/master coordination helpers.
"""
import multiprocessing
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_WORKER_OUTPUT_KEY = "beacon_results"


def is_worker(session) -> bool:
    """Return True when running inside an xdist worker process."""
    try:
        import xdist  # noqa: PLC0415
        return xdist.get_xdist_worker_id(session) != "master"
    except (ImportError, AttributeError):
        return hasattr(session.config, "workerinput")


def send_to_master(config, tests: list[dict[str, Any]]) -> None:
    """Serialise collected test dicts into workeroutput for the master to read."""
    try:
        if hasattr(config, "workeroutput"):
            config.workeroutput[_WORKER_OUTPUT_KEY] = {"tests": tests}
    except Exception:
        log.exception("beacon.xdist: failed to send results to master")


def collect_from_worker(node) -> list[dict[str, Any]]:
    """Read and return test dicts from a finished worker node."""
    try:
        if hasattr(node, "workeroutput") and _WORKER_OUTPUT_KEY in node.workeroutput:
            data = node.workeroutput[_WORKER_OUTPUT_KEY]
            if isinstance(data, dict):
                return data.get("tests", [])
    except Exception:
        log.exception("beacon.xdist: failed to collect worker results", worker=getattr(node, "workerid", "unknown"))
    return []


def get_worker_count(config) -> int | None:
    """Return the number of xdist workers if parallel execution is active."""
    try:
        n = getattr(config.option, "numprocesses", None) or getattr(config.option, "n", None)
        if n is None:
            return None
        if isinstance(n, str) and n.lower() == "auto":
            return multiprocessing.cpu_count()
        if isinstance(n, int) and n > 0:
            return n
    except Exception:
        pass
    return None
