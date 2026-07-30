"""Preflight health check and launching Grand Theft Auto V.

GTA V must be started through Steam / Epic / Rockstar Launcher. Starting
``GTA5.exe`` directly raises ``ERR_NO_LAUNCHER``.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.result import Result
from gta_mod_manager.models.diagnostic import DiagnosticSeverity
from gta_mod_manager.models.enums import ConflictSeverity, GamePlatform
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.launch import (
    LaunchIssue,
    LaunchIssueSeverity,
    LaunchOutcome,
    LaunchPreflightReport,
)
from gta_mod_manager.services.conflict_service import ConflictService
from gta_mod_manager.services.crash_monitor_service import CrashMonitorService
from gta_mod_manager.services.diagnostics_service import DiagnosticsService
from gta_mod_manager.services.game_service import GameService
from gta_mod_manager.utils import windows as win

_LOGGER = get_logger("services.launch")

#: Game-folder stubs that hand off to Rockstar Games Launcher.
_LAUNCHER_STUBS: tuple[str, ...] = (
    "PlayGTAV.exe",
    "GTAVLauncher.exe",
    "PlayGTA5_Enhanced.exe",
)


@dataclass(frozen=True, slots=True)
class LaunchTarget:
    """How the game should actually be started."""

    label: str
    command: tuple[str, ...]
    cwd: Path | None = None
    via_uri: bool = False


class LaunchService:
    """Runs a quick health check, then starts the game through its launcher."""

    def __init__(
        self,
        game: GameService,
        diagnostics: DiagnosticsService,
        conflicts: ConflictService,
        crash_monitor: CrashMonitorService | None = None,
    ) -> None:
        self._game = game
        self._diagnostics = diagnostics
        self._conflicts = conflicts
        self._crash_monitor = crash_monitor

    def preflight(self, install: GameInstall | None = None) -> Result[LaunchPreflightReport]:
        """Collect issues that often crash or break a modded session."""
        target = install or self._game.active
        if target is None:
            resolved = self._game.resolve_active()
            if resolved.is_error:
                return Result.fail(
                    resolved.error or "No GTA V installation selected",
                    code=resolved.code or "launch.no_game",
                )
            target = resolved.unwrap()

        executable = self.resolve_executable(target)
        launch_target = self.resolve_launch_target(target)
        issues: list[LaunchIssue] = []

        report = self._diagnostics.run(target)
        if report is not None:
            for finding in report.findings:
                if not finding.is_problem:
                    continue
                severity = (
                    LaunchIssueSeverity.ERROR
                    if finding.severity is DiagnosticSeverity.ERROR
                    else LaunchIssueSeverity.WARNING
                )
                issues.append(
                    LaunchIssue(
                        code=finding.code,
                        severity=severity,
                        title=finding.title,
                        detail=finding.detail,
                        source="diagnostics",
                    )
                )

        conflict_report = self._conflicts.audit(target)
        for conflict in conflict_report.conflicts:
            if conflict.severity is ConflictSeverity.INFO:
                continue
            severity = (
                LaunchIssueSeverity.ERROR
                if conflict.severity is ConflictSeverity.BLOCKING
                else LaunchIssueSeverity.WARNING
            )
            issues.append(
                LaunchIssue(
                    code=f"conflict.{conflict.conflict_type.value}",
                    severity=severity,
                    title=conflict.conflict_type.display_name,
                    detail=conflict.description,
                    source="conflicts",
                )
            )

        if self._crash_monitor is not None:
            session = self._crash_monitor.last_report
            if session is not None and session.crashed:
                for finding in session.findings:
                    if not finding.is_problem:
                        continue
                    issues.append(
                        LaunchIssue(
                            code=f"crash.{finding.code}",
                            severity=LaunchIssueSeverity.WARNING,
                            title=finding.title,
                            detail=finding.detail,
                            source="crash",
                        )
                    )

        if executable is None:
            issues.append(
                LaunchIssue(
                    code="launch.exe_missing",
                    severity=LaunchIssueSeverity.ERROR,
                    title="Game executable not found",
                    detail="Neither GTA5.exe nor GTA5_Enhanced.exe was found in the game folder.",
                    source="launch",
                )
            )
        if launch_target is None:
            issues.append(
                LaunchIssue(
                    code="launch.launcher_missing",
                    severity=LaunchIssueSeverity.ERROR,
                    title="Launcher not found",
                    detail=(
                        "GTA V must be started through Steam, Epic or Rockstar Games "
                        "Launcher. Direct GTA5.exe starts cause ERR_NO_LAUNCHER."
                    ),
                    source="launch",
                )
            )

        return Result.ok(
            LaunchPreflightReport(
                game_root=target.root_path,
                executable=executable,
                issues=tuple(issues),
            )
        )

    def launch(
        self,
        install: GameInstall | None = None,
        *,
        force: bool = False,
    ) -> Result[LaunchOutcome]:
        """Start the game after (or despite) the preflight check."""
        target = install or self._game.active
        if target is None:
            resolved = self._game.resolve_active()
            if resolved.is_error:
                return Result.fail(
                    resolved.error or "No GTA V installation selected",
                    code=resolved.code or "launch.no_game",
                )
            target = resolved.unwrap()

        checked = self.preflight(target)
        if checked.is_error:
            return Result.fail(checked.error or "Preflight failed", code=checked.code)
        report = checked.unwrap()
        launch_target = self.resolve_launch_target(target)
        if launch_target is None:
            return Result.fail(
                "Could not find Steam, Epic or Rockstar Games Launcher to start GTA V",
                code="launch.launcher_missing",
            )
        if not force and report.has_blocking:
            return Result.fail(
                "Blocking issues found — fix them or launch anyway.",
                code="launch.blocked",
            )

        try:
            self._start(launch_target)
        except OSError as error:
            return Result.fail(str(error), code="launch.failed")

        display = report.executable or Path(launch_target.command[0])
        _LOGGER.info("Launched GTA V via %s (%s)", launch_target.label, launch_target.command)
        return Result.ok(
            LaunchOutcome(
                executable=display,
                message=f"Started GTA V via {launch_target.label}",
            )
        )

    def resolve_launch_target(self, install: GameInstall) -> LaunchTarget | None:
        """Return the safest way to start ``install`` without ERR_NO_LAUNCHER."""
        platform = install.platform
        if platform is GamePlatform.UNKNOWN:
            platform = self._guess_platform(install.root_path)

        if platform is GamePlatform.STEAM or self._looks_like_steam(install.root_path):
            return LaunchTarget(
                label="Steam",
                command=(f"steam://rungameid/{constants.STEAM_APP_ID_GTA_V}",),
                via_uri=True,
            )

        if platform is GamePlatform.EPIC:
            app_name = next(iter(constants.EPIC_GTA_V_APP_NAMES), "")
            if app_name:
                return LaunchTarget(
                    label="Epic Games",
                    command=(
                        f"com.epicgames.launcher://apps/{app_name}?action=launch&silent=true",
                    ),
                    via_uri=True,
                )

        stub = self._find_stub(install.root_path)
        if stub is not None:
            return LaunchTarget(
                label=stub.name,
                command=(str(stub),),
                cwd=install.root_path,
            )

        rockstar = self._find_rockstar_launcher()
        if rockstar is not None:
            return LaunchTarget(
                label="Rockstar Games Launcher",
                command=(str(rockstar),),
                cwd=rockstar.parent,
            )

        # Last resort for true manual copies only — still prefer stubs above.
        if platform is GamePlatform.MANUAL:
            executable = self.resolve_executable(install)
            if executable is not None:
                return LaunchTarget(
                    label=executable.name,
                    command=(str(executable),),
                    cwd=install.root_path,
                )
        return None

    @staticmethod
    def resolve_executable(install: GameInstall) -> Path | None:
        """Return the game binary used to prove the install is present."""
        candidates: list[Path] = []
        if install.executable is not None:
            candidates.append(install.executable)
        for name in constants.GAME_EXECUTABLES:
            candidates.append(install.root_path / name)
        seen: set[Path] = set()
        for path in candidates:
            resolved = path if path.is_absolute() else install.root_path / path
            key = resolved.resolve() if resolved.exists() else resolved
            if key in seen:
                continue
            seen.add(key)
            if resolved.is_file():
                return resolved
        return None

    @staticmethod
    def _guess_platform(root: Path) -> GamePlatform:
        text = str(root).lower()
        if "steamapps" in text:
            return GamePlatform.STEAM
        if "epic games" in text:
            return GamePlatform.EPIC
        if "rockstar games" in text:
            return GamePlatform.ROCKSTAR
        return GamePlatform.MANUAL

    @staticmethod
    def _looks_like_steam(root: Path) -> bool:
        return "steamapps" in str(root).lower()

    @staticmethod
    def _find_stub(game_root: Path) -> Path | None:
        for name in _LAUNCHER_STUBS:
            candidate = game_root / name
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _find_rockstar_launcher() -> Path | None:
        candidates: list[Path] = []
        for hive, key_path, value_name in constants.REG_ROCKSTAR_PATHS:
            if "Launcher" not in key_path:
                continue
            folder = win.read_registry_string(hive, key_path, value_name)
            if folder:
                candidates.append(Path(folder) / "Launcher.exe")
        candidates.extend(
            (
                Path(r"C:\Program Files\Rockstar Games\Launcher\Launcher.exe"),
                Path(r"C:\Program Files (x86)\Rockstar Games\Launcher\Launcher.exe"),
            )
        )
        for path in candidates:
            if path.is_file():
                return path
        return None

    @staticmethod
    def _start(target: LaunchTarget) -> None:
        """Start ``target`` detached from this process."""
        if target.via_uri:
            # Protocol handlers (steam://, com.epicgames.launcher://) must go
            # through the shell — Popen on the URI alone fails on Windows.
            if win.IS_WINDOWS:
                os.startfile(target.command[0])  # noqa: S606 - intentional URI launch
            else:
                subprocess.Popen(  # noqa: S603
                    ["xdg-open", target.command[0]],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    close_fds=True,
                )
            return

        creationflags = 0
        if hasattr(subprocess, "DETACHED_PROCESS"):
            creationflags |= subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        subprocess.Popen(  # noqa: S603 - launching the user's own game / launcher
            list(target.command),
            cwd=str(target.cwd) if target.cwd is not None else None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
