"""Watches the game process and reports crashes while the tool is open.

The monitor runs a daemon thread. When ``GTA5.exe`` appears it records the
session start; when the process exits it reads the exit code, waits a short
grace period so Windows can flush crash dumps and logs, and then builds a
:class:`~gta_mod_manager.models.crash_report.GameSessionReport` that names the
most likely culprit mods. The GUI is informed through
:class:`~gta_mod_manager.core.events.GameSessionEndedEvent`.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.events import (
    EventBus,
    GameSessionEndedEvent,
    GameSessionStartedEvent,
)
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.diagnostics.crash_evidence import collect_session_evidence
from gta_mod_manager.models.crash_report import GameSessionReport
from gta_mod_manager.repository.mod_repository import JsonModRepository
from gta_mod_manager.services.game_service import GameService
from gta_mod_manager.utils import windows

_LOGGER = get_logger("services.crash_monitor")

#: How many session reports are kept on disk.
_MAX_SAVED_REPORTS = 20

FindProcess = Callable[[tuple[str, ...]], tuple[int, str] | None]
MakeWatch = Callable[[int, str], windows.ProcessWatch]


class CrashMonitorService:
    """Background watcher for game sessions and crashes."""

    def __init__(
        self,
        game: GameService,
        mods: JsonModRepository,
        bus: EventBus,
        reports_dir: Path,
        *,
        find_process: FindProcess = windows.find_running_process,
        make_watch: MakeWatch = windows.ProcessWatch,
        poll_seconds: float = 3.0,
        grace_seconds: float = 5.0,
    ) -> None:
        self._game = game
        self._mods = mods
        self._bus = bus
        self._reports_dir = reports_dir
        self._find_process = find_process
        self._make_watch = make_watch
        self._poll_seconds = poll_seconds
        self._grace_seconds = grace_seconds

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._last_report: GameSessionReport | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        """Return whether the watcher thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def last_report(self) -> GameSessionReport | None:
        """Return the most recent session report, if any."""
        with self._lock:
            return self._last_report

    def start(self) -> None:
        """Start the watcher thread (idempotent)."""
        if self.is_running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="crash-monitor", daemon=True
        )
        self._thread.start()
        _LOGGER.info("Crash monitor started (poll every %.1fs)", self._poll_seconds)

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the watcher thread."""
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout)
        self._thread = None

    # ------------------------------------------------------------------
    # Watch loop
    # ------------------------------------------------------------------
    def _loop(self) -> None:
        """Poll for the game process until stopped."""
        watch: windows.ProcessWatch | None = None
        started_at: datetime | None = None

        while not self._stop.wait(self._poll_seconds):
            try:
                if watch is None:
                    found = self._find_process(constants.GAME_PROCESS_NAMES)
                    if found is None:
                        continue
                    pid, name = found
                    watch = self._make_watch(pid, name)
                    started_at = datetime.now(timezone.utc)
                    _LOGGER.info("Game session started: %s (pid %d)", name, pid)
                    self._bus.publish(GameSessionStartedEvent(process_name=name, pid=pid))
                    continue

                running, exit_code = watch.poll()
                if running:
                    continue

                ended_at = datetime.now(timezone.utc)
                name = watch.name
                watch.close()
                watch = None
                _LOGGER.info(
                    "Game session ended: %s exit_code=%s", name, exit_code
                )
                # Give Windows Error Reporting and SHVDN time to flush files.
                self._stop.wait(self._grace_seconds)
                assert started_at is not None
                report = self._build_report(name, started_at, ended_at, exit_code)
                if report is None:
                    continue
                with self._lock:
                    self._last_report = report
                self._persist(report)
                self._bus.publish(GameSessionEndedEvent(report=report))
            except Exception as error:  # noqa: BLE001 - the watcher must survive
                _LOGGER.warning("Crash monitor iteration failed: %s", error)
                if watch is not None:
                    watch.close()
                    watch = None

        if watch is not None:
            watch.close()

    def _build_report(
        self,
        process_name: str,
        started_at: datetime,
        ended_at: datetime,
        exit_code: int | None,
    ) -> GameSessionReport | None:
        """Collect the evidence for one finished session."""
        install = self._game.active
        if install is None:
            resolved = self._game.resolve_active()
            if resolved.is_error:
                _LOGGER.debug("No active installation; skipping session report")
                return None
            install = resolved.unwrap()
        installed = self._mods.list_for_game(install.root_path)
        return collect_session_evidence(
            game_root=Path(install.root_path),
            process_name=process_name,
            installed=installed,
            started_at=started_at,
            ended_at=ended_at,
            exit_code=exit_code,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _persist(self, report: GameSessionReport) -> None:
        """Write the report to disk and prune old ones."""
        try:
            self._reports_dir.mkdir(parents=True, exist_ok=True)
            stamp = report.ended_at.strftime("%Y%m%d-%H%M%S")
            payload = {
                "game_root": str(report.game_root),
                "process_name": report.process_name,
                "started_at": report.started_at.isoformat(),
                "ended_at": report.ended_at.isoformat(),
                "exit_code": report.exit_code,
                "crashed": report.crashed,
                "duration_seconds": report.duration_seconds,
                "findings": [
                    {
                        "code": item.code,
                        "severity": item.severity.value,
                        "title": item.title,
                        "detail": item.detail,
                        "fix": item.fix,
                        "evidence": item.evidence,
                        "targets": list(item.fix_targets),
                    }
                    for item in report.findings
                ],
            }
            path = self._reports_dir / f"session_{stamp}.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self._prune()
        except OSError as error:
            _LOGGER.warning("Could not persist session report: %s", error)

    def _prune(self) -> None:
        """Keep only the newest reports."""
        files = sorted(self._reports_dir.glob("session_*.json"))
        for stale in files[:-_MAX_SAVED_REPORTS]:
            try:
                stale.unlink()
            except OSError:
                continue
