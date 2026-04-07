# Logging Rules

> **Version:** 2.0.0
> **Purpose:** Rules for logging in `pytest-beacon`. This project is a reusable pytest plugin/library that uses the standard library `logging` module so host applications can control it with normal Python logging configuration.

---

## Core Principles

1. **Use standard library `logging`, not `print()` or the root logger, for diagnostics**. This keeps the plugin compatible with normal Python logging, pytest capture, JSON formatters, and host-side routing.
2. **Treat `pytest-beacon` as library code**. The plugin may emit logs, but it must not take over global logging handlers, formatters, or routing inside the host pytest process.
3. **Use a module-local logger**. In this project, use `log = get_logger(__name__)` from `pytest_beacon.infrastructure.observability.logging`.
4. **Keep messages understandable even in plain-text environments**. The current codebase prefers self-contained event text such as `"beacon.http_exporter: metrics sent"` because host environments may not render a separate `logger` field.
5. **Pass context as keyword arguments**. The local logger adapter converts them into stdlib `extra` fields so callers can still write concise `log.info("...", key=value)` calls.
6. **Never log secrets, tokens, credentials, PII, or full report payloads**.

---

## Where Logging Lives

| Location | Responsibility |
|----------|----------------|
| `entry_points/pytest_plugin/*.py` | Plugin lifecycle logs, outer exception boundaries, xdist coordination |
| `infrastructure/exporters/*.py` | File and HTTP I/O, retries, status codes, failure paths |
| `domains/**/*.py` | Domain events or business-state decisions when they add value |
| `infrastructure/observability/logging.py` | Small adapter around stdlib logging that preserves `key=value` call-site ergonomics |
| `config/settings.py` | Settings only. No logging configuration today. |

The package root installs a `NullHandler` for the `pytest_beacon` logger namespace so the library stays quiet unless the host project chooses to configure logging.

---

## Logger Setup Pattern

### Inside `pytest-beacon` modules

Use a normal module-local logger:

```python
from pytest_beacon.infrastructure.observability.logging import get_logger

log = get_logger(__name__)
```

This keeps logger names aligned with module names while letting call sites attach structured context using regular keyword arguments.

### Example from the current code style

```python
from pytest_beacon.infrastructure.observability.logging import get_logger

log = get_logger(__name__)


class HttpExporter:
    def export(self, report: dict[str, object]) -> None:
        try:
            ...
            log.info(
                "beacon.http_exporter: metrics sent",
                url=self._url,
                status=response.status_code,
                metrics_count=len(payload["metrics"]),
            )
        except Exception:
            log.exception("beacon.http_exporter: unexpected error", url=self._url)
```

### If a host application wants to configure output

That configuration belongs outside the reusable plugin package. A standalone wrapper, demo app, or test harness may configure `logging`, but code under `src/pytest_beacon/` should not do so implicitly.

---

## Log Levels

| Level | When to use | Examples |
|-------|-------------|----------|
| `DEBUG` | Diagnostic detail useful during troubleshooting | Plugin options, excluded statuses, xdist merge details |
| `INFO` | Normal successful operations worth observing | Report written, metrics sent |
| `WARNING` | Unexpected but recoverable behavior | Retry timeout, partial degradation |
| `ERROR` | Operation failed and the plugin continues | Non-retriable HTTP failure, retries exhausted |
| `EXCEPTION` (`log.exception(...)`) | Unexpected exception with traceback inside `except` | Hook failure, serialization failure, file write failure |

Avoid `CRITICAL` in plugin code. This project is not a standalone process owner and should not imply that the host test run must terminate immediately.

---

## Structured Logging Rules

Always pass runtime context as keyword arguments:

```python
# Good
log.info("beacon.http_exporter: metrics sent", url=url, status=response.status_code)
log.warning("beacon.http_exporter: request timed out", url=url, attempt=attempt)
log.error(
    "beacon.http_exporter: HTTP error",
    url=url,
    status=exc.response.status_code,
    body_preview=exc.response.text[:200],
    attempt=attempt,
)

# Bad
log.info(f"Sent metrics to {url}, status={response.status_code}")
log.warning("Request to " + url + " timed out on attempt " + str(attempt))
```

### Message style for this repository

Because `pytest-beacon` runs inside user-controlled environments, log output may appear as plain text, partially structured text, or fully rendered JSON depending on the host configuration.

For that reason, message strings in this repository should be:

- Short and stable
- Lowercase prose or a short sentence fragment
- Self-contained enough to understand without extra formatting
- Consistent within a module

Current examples from the codebase:

```text
"beacon: plugin initialised"
"beacon.http_exporter: metrics sent"
"beacon.http_exporter: request timed out"
"beacon.file_exporter: failed to write report"
```

Do not build huge dynamic messages. Put changing data in fields such as `url`, `status`, `attempt`, `nodeid`, `worker`, `path`, or `max_retries`.

### Field naming

Prefer stable, explicit names:

- `url`
- `status`
- `attempt`
- `path`
- `nodeid`
- `worker`
- `metrics_count`
- `max_retries`

If a field may be very large or noisy, log a bounded preview instead of the full value.

---

## Layer-Specific Rules

### Domain Layer (`domains/`)

- Log business decisions or domain state changes only when they help explain behavior.
- Keep domain logs free of infrastructure-only details such as URLs, raw HTTP bodies, or filesystem paths unless those values are part of the domain meaning.
- Do not configure logging here.

Example:

```python
from pytest_beacon.infrastructure.observability.logging import get_logger

log = get_logger(__name__)


def complete(self) -> None:
    if self.status != "ACTIVE":
        log.warning("task cannot be completed from current status", task_id=self.id, status=self.status)
        raise InvalidStatusError()
    log.info("task completed", task_id=self.id)
    self.status = "COMPLETED"
```

### Infrastructure Layer (`infrastructure/`)

- Log file writes, HTTP calls, retries, and other I/O boundaries.
- Use `log.exception(...)` inside `except` blocks when a traceback is useful.
- Keep payload logging bounded. Prefer counts, identifiers, and previews over full serialized content.
- Do not log domain conclusions here if the same event is better expressed in the domain layer.

Example:

```python
from pytest_beacon.infrastructure.observability.logging import get_logger

log = get_logger(__name__)


for attempt in range(1, self._max_retries + 1):
    try:
        response = httpx.post(url, json=payload, timeout=self._timeout)
        response.raise_for_status()
        log.info("beacon.http_exporter: metrics sent", url=url, status=response.status_code, attempt=attempt)
        return
    except httpx.TimeoutException:
        log.warning("beacon.http_exporter: request timed out", url=url, attempt=attempt)
    except Exception:
        log.exception("beacon.http_exporter: unexpected error", url=url, attempt=attempt)
```

### Entry Points Layer (`entry_points/`)

- Log plugin lifecycle and outer exception boundaries.
- Log registration, startup diagnostics, and xdist worker/master coordination when helpful.
- Do not configure global logging from plugin hooks.
- Do not dump per-test noise at `INFO` unless it is genuinely useful to operators.

Example:

```python
from pytest_beacon.infrastructure.observability.logging import get_logger

log = get_logger(__name__)


class BeaconPlugin:
    def __init__(self, config: pytest.Config) -> None:
        log.debug(
            "beacon: plugin initialised",
            fmt=self._fmt,
            verbose=self._verbose,
            excluded=list(self._excluded),
            meta=self._meta,
        )
```

---

## What Not To Log

| Rule | Bad example | Why |
|------|-------------|-----|
| No root logger usage | `logging.info("...")` | Makes host-side filtering and routing harder |
| No `print()` for diagnostics | `print(f"Sending to {url}")` | Unstructured and bypasses log policy |
| No secrets or tokens | `log.debug("auth", token=api_key)` | Security risk |
| No PII | `log.info("user", email=user.email)` | Compliance and privacy risk |
| No full payload/report dumps | `log.debug("payload", payload=payload)` | Noisy, expensive, and may leak data |
| No raw exception string only | `log.error(f"Error: {e}")` | Loses traceback context |
| No unbounded external text | `log.error("response", body=response.text)` | Can flood logs or enable log injection |

`print()` is still acceptable for deliberate user-facing console output that is not diagnostic logging. In this project, the end-of-run report summary is an example of plugin UX, not structured operational logging.

---

## Quick Checklist

- [ ] Each logging module defines `log = get_logger(__name__)`
- [ ] No code under `src/pytest_beacon/` configures global logging handlers or formatters
- [ ] Messages are short, stable, and readable in plain text
- [ ] Variable data is passed as keyword arguments
- [ ] `log.exception(...)` is used inside `except` blocks when traceback context matters
- [ ] Large values are truncated or summarized before logging
- [ ] No secrets, credentials, tokens, PII, or full report bodies are logged
- [ ] Domain logs focus on domain behavior; infrastructure logs focus on I/O; entry points log lifecycle and boundaries
- [ ] `print()` is reserved for explicit user-facing console output, not diagnostics

---

## Quick Reference

```python
from pytest_beacon.infrastructure.observability.logging import get_logger

log = get_logger(__name__)

log.debug("beacon: plugin initialised", fmt="json")
log.info("beacon.http_exporter: metrics sent", url=url, status=200)
log.warning("beacon.http_exporter: request timed out", url=url, attempt=2)
log.error("beacon.http_exporter: all retries exhausted", url=url, max_retries=3)

try:
    exporter.export(report)
except Exception:
    log.exception("beacon: export failed")

bound = log.bind(session_id=session_id)
bound.info("beacon: session finished")
```

---

**Remember:** `pytest-beacon` is a guest inside the user's pytest process. Emit useful logs through stdlib logging and let the host environment decide how they are filtered, formatted, and routed.
