"""Unit tests for pytest-beacon logging helpers."""

from __future__ import annotations

import logging

from pytest_beacon.infrastructure.observability.logging import get_logger


def test_structured_kwargs_become_log_record_fields(caplog) -> None:
    log = get_logger("pytest_beacon.tests.logging")

    with caplog.at_level(logging.INFO, logger="pytest_beacon.tests.logging"):
        log.info("hello", url="http://example.com", attempt=2)

    record = caplog.records[0]
    assert record.message == "hello"
    assert record.url == "http://example.com"
    assert record.attempt == 2


def test_bind_adds_persistent_context(caplog) -> None:
    log = get_logger("pytest_beacon.tests.logging").bind(session_id="abc123")

    with caplog.at_level(logging.INFO, logger="pytest_beacon.tests.logging"):
        log.info("session finished", tests=3)

    record = caplog.records[0]
    assert record.session_id == "abc123"
    assert record.tests == 3


def test_exception_keeps_exc_info_and_context(caplog) -> None:
    log = get_logger("pytest_beacon.tests.logging")

    with caplog.at_level(logging.ERROR, logger="pytest_beacon.tests.logging"):
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            log.exception("export failed", nodeid="tests/test_file.py::test_case")

    record = caplog.records[0]
    assert record.message == "export failed"
    assert record.nodeid == "tests/test_file.py::test_case"
    assert record.exc_info is not None
