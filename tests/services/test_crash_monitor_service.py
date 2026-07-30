"""Tests for the background game-session watcher."""

from __future__ import annotations

import threading
from pathlib import Path

from gta_mod_manager.core.events import (
    EventBus,
    GameSessionEndedEvent,
    GameSessionStartedEvent,
)
from gta_mod_manager.models.crash_report import GameSessionReport
from gta_mod_manager.models.enums import GamePlatform
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.services.crash_monitor_service import CrashMonitorService


class _FakeGame:
    """Stands in for GameService: only ``active`` is used by the monitor."""

    def __init__(self, install: GameInstall) -> None:
        self.active = install


class _FakeMods:
    """Stands in for JsonModRepository."""

    @staticmethod
    def list_for_game(_root: Path) -> tuple[()]:
        return ()


class _FakeWatch:
    """Reports the process as running once, then exited with a crash code."""

    def __init__(self, pid: int, name: str) -> None:
        self.pid = pid
        self.name = name
        self._polls = 0
        self.closed = False

    def poll(self) -> tuple[bool, int | None]:
        self._polls += 1
        if self._polls == 1:
            return True, None
        return False, 0xC0000005

    def close(self) -> None:
        self.closed = True


def test_monitor_reports_a_crashed_session(tmp_path: Path) -> None:
    game_root = tmp_path / "game"
    game_root.mkdir()
    install = GameInstall(
        game_id="gta_v", root_path=game_root, platform=GamePlatform.MANUAL
    )
    bus = EventBus()

    found = {"served": False}

    def find_process(_names: tuple[str, ...]) -> tuple[int, str] | None:
        if found["served"]:
            return None
        found["served"] = True
        return 4242, "GTA5.exe"

    started = threading.Event()
    ended = threading.Event()
    captured: list[GameSessionReport] = []

    bus.subscribe(GameSessionStartedEvent, lambda _e: started.set())

    def on_ended(event: GameSessionEndedEvent) -> None:
        assert isinstance(event.report, GameSessionReport)
        captured.append(event.report)
        ended.set()

    bus.subscribe(GameSessionEndedEvent, on_ended)

    monitor = CrashMonitorService(
        game=_FakeGame(install),  # type: ignore[arg-type]
        mods=_FakeMods(),  # type: ignore[arg-type]
        bus=bus,
        reports_dir=tmp_path / "sessions",
        find_process=find_process,
        make_watch=_FakeWatch,
        poll_seconds=0.02,
        grace_seconds=0.01,
    )
    monitor.start()
    try:
        assert started.wait(5.0), "session start was never published"
        assert ended.wait(5.0), "session end was never published"
    finally:
        monitor.stop()

    report = captured[0]
    assert report.crashed
    assert report.exit_code == 0xC0000005
    assert report.process_name == "GTA5.exe"
    assert monitor.last_report is report

    saved = list((tmp_path / "sessions").glob("session_*.json"))
    assert len(saved) == 1
    assert "crash.exit_code" in saved[0].read_text(encoding="utf-8")


def test_monitor_start_and_stop_are_idempotent(tmp_path: Path) -> None:
    install = GameInstall(
        game_id="gta_v", root_path=tmp_path, platform=GamePlatform.MANUAL
    )
    monitor = CrashMonitorService(
        game=_FakeGame(install),  # type: ignore[arg-type]
        mods=_FakeMods(),  # type: ignore[arg-type]
        bus=EventBus(),
        reports_dir=tmp_path / "sessions",
        find_process=lambda _names: None,
        poll_seconds=0.02,
    )
    monitor.start()
    monitor.start()
    assert monitor.is_running
    monitor.stop()
    monitor.stop()
    assert not monitor.is_running
    assert monitor.last_report is None
