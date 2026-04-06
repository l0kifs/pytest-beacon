"""
HTTP exporter: POSTs the CTRF report to a user-specified URL.

Body: {"metrics": [...]}
"""
from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)


class HttpExporter:
    """Sends test metrics to a remote HTTP endpoint."""

    def __init__(self, url: str, timeout: float = 10.0, max_retries: int = 3) -> None:
        self._url = url
        self._timeout = timeout
        self._max_retries = max_retries

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def export(self, report: dict[str, Any]) -> None:
        """POST metrics payload to the configured endpoint. Never raises."""
        try:
            payload = self._build_payload(report)
        except Exception:
            log.exception("beacon.http_exporter: failed to build payload")
            return

        url = self._url
        for attempt in range(1, self._max_retries + 1):
            try:
                response = httpx.post(url, json=payload, timeout=self._timeout)
                response.raise_for_status()
                log.info(
                    "beacon.http_exporter: metrics sent",
                    url=url,
                    status=response.status_code,
                    metrics_count=len(payload["metrics"]),
                )
                return
            except httpx.TimeoutException:
                log.warning("beacon.http_exporter: request timed out", url=url, attempt=attempt)
            except httpx.HTTPStatusError as exc:
                log.error(
                    "beacon.http_exporter: HTTP error",
                    url=url,
                    status=exc.response.status_code,
                    body_preview=exc.response.text[:200],
                    attempt=attempt,
                )
                return  # 4xx/5xx — no point retrying
            except Exception:
                log.exception("beacon.http_exporter: unexpected error", url=url, attempt=attempt)

        log.error("beacon.http_exporter: all retries exhausted", url=url, max_retries=self._max_retries)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_payload(self, report: dict[str, Any]) -> dict[str, Any]:
        results = report.get("results", {})
        environment = results.get("environment", {})
        metrics = []
        for test in results.get("tests", []):
            metrics.append({
                "test_nodeid": test.get("name"),
                "test_name": test.get("name", "").split("::")[-1],
                "test_result": test.get("status", "other"),
                "test_duration": test.get("duration", 0) / 1000,  # ms → seconds
                "test_marks": test.get("marks", []),
                "test_params": test.get("params", {}),
                "test_stacktrace": test.get("trace"),
                "test_message": test.get("message"),
                "test_allure_id": test.get("allureId"),
            })
        return {"metrics": metrics, "environment": environment}
