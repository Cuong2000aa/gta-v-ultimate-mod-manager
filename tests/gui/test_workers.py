"""Tests for the background task runner behind every view model call."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from gta_mod_manager.gui.workers import TaskRunner  # noqa: E402


def _drain(runner: TaskRunner, timeout_ms: int = 5000) -> None:
    """Wait for every task and deliver the queued signals."""
    assert runner.wait(timeout_ms)
    QCoreApplication.processEvents()


def test_a_result_is_delivered_to_the_success_callback(qt_app) -> None:  # noqa: ANN001, ARG001
    runner = TaskRunner()
    received: list[int] = []

    runner.submit(lambda: 42, received.append)
    _drain(runner)

    assert received == [42]


def test_an_exception_is_delivered_to_the_error_callback(qt_app) -> None:  # noqa: ANN001, ARG001
    runner = TaskRunner()
    errors: list[str] = []

    def explode() -> None:
        raise RuntimeError("service refused")

    runner.submit(explode, on_error=errors.append)
    _drain(runner)

    assert errors == ["service refused"]


def test_busy_is_reported_while_work_is_running(qt_app) -> None:  # noqa: ANN001, ARG001
    runner = TaskRunner()
    states: list[bool] = []
    runner.busyChanged.connect(states.append)

    runner.submit(lambda: None)
    _drain(runner)

    assert states == [True, False]
    assert not runner.is_busy


def test_finished_tasks_are_released(qt_app) -> None:  # noqa: ANN001, ARG001
    runner = TaskRunner()

    for _ in range(5):
        runner.submit(lambda: None, lambda _result: None)
    _drain(runner)

    assert not runner._pending
    assert not runner.is_busy
