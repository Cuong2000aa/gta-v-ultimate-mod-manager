"""Tests for the launch / preflight service."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.result import Result
from gta_mod_manager.models.conflict import Conflict, ConflictReport
from gta_mod_manager.models.diagnostic import (
    DiagnosticFinding,
    DiagnosticReport,
    DiagnosticSeverity,
)
from gta_mod_manager.models.enums import ConflictSeverity, ConflictType, GamePlatform
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.launch import LaunchIssueSeverity
from gta_mod_manager.services.launch_service import LaunchService, LaunchTarget


class _Game:
    def __init__(self, install: GameInstall) -> None:
        self.active = install

    def resolve_active(self) -> Result[GameInstall]:
        return Result.ok(self.active)


class _Diagnostics:
    def __init__(self, report: DiagnosticReport | None) -> None:
        self._report = report

    def run(self, _install=None) -> DiagnosticReport | None:
        return self._report


class _Conflicts:
    def __init__(self, report: ConflictReport) -> None:
        self._report = report

    def audit(self, _install) -> ConflictReport:
        return self._report


def _install(root: Path, platform: GamePlatform = GamePlatform.STEAM) -> GameInstall:
    exe = root / "GTA5.exe"
    exe.write_bytes(b"exe")
    return GameInstall(
        game_id="gta_v",
        root_path=root,
        platform=platform,
        executable=exe,
    )


def test_preflight_is_clean_when_no_problems(tmp_path: Path) -> None:
    install = _install(tmp_path)
    service = LaunchService(
        _Game(install),
        _Diagnostics(DiagnosticReport(game_root=tmp_path, findings=())),
        _Conflicts(ConflictReport()),
    )

    report = service.preflight().unwrap()

    assert report.is_clean
    assert report.can_launch
    assert report.executable == install.executable


def test_preflight_collects_diagnostics_and_conflicts(tmp_path: Path) -> None:
    install = _install(tmp_path)
    diagnostics = DiagnosticReport(
        game_root=tmp_path,
        findings=(
            DiagnosticFinding(
                code="mods.orphan_dlcpack",
                severity=DiagnosticSeverity.WARNING,
                title="Orphan pack",
                detail="orphan",
            ),
            DiagnosticFinding(
                code="ok.clean",
                severity=DiagnosticSeverity.OK,
                title="Clean",
                detail="",
            ),
        ),
    )
    conflicts = ConflictReport(
        conflicts=(
            Conflict(
                conflict_type=ConflictType.FILE_OVERWRITE,
                severity=ConflictSeverity.BLOCKING,
                key="x",
                description="Two mods share a file",
            ),
        )
    )
    service = LaunchService(_Game(install), _Diagnostics(diagnostics), _Conflicts(conflicts))

    report = service.preflight().unwrap()

    assert not report.is_clean
    assert report.has_blocking
    assert any(item.code == "mods.orphan_dlcpack" for item in report.issues)
    assert any(item.severity is LaunchIssueSeverity.ERROR for item in report.issues)


def test_launch_force_starts_via_steam_uri(tmp_path: Path, monkeypatch) -> None:
    install = _install(tmp_path)
    conflicts = ConflictReport(
        conflicts=(
            Conflict(
                conflict_type=ConflictType.FILE_OVERWRITE,
                severity=ConflictSeverity.BLOCKING,
                key="x",
                description="clash",
            ),
        )
    )
    service = LaunchService(
        _Game(install),
        _Diagnostics(DiagnosticReport(game_root=tmp_path)),
        _Conflicts(conflicts),
    )
    called: list[LaunchTarget] = []
    monkeypatch.setattr(
        LaunchService,
        "_start",
        staticmethod(lambda target: called.append(target)),
    )

    blocked = service.launch(force=False)
    assert blocked.is_error

    outcome = service.launch(force=True).unwrap()
    assert outcome.executable == install.executable
    assert "Steam" in outcome.message
    assert len(called) == 1
    assert called[0].via_uri
    assert called[0].command == (f"steam://rungameid/{constants.STEAM_APP_ID_GTA_V}",)


def test_resolve_launch_target_prefers_steam_uri(tmp_path: Path) -> None:
    install = _install(tmp_path, GamePlatform.STEAM)
    target = LaunchService(_Game(install), _Diagnostics(None), _Conflicts(ConflictReport())).resolve_launch_target(
        install
    )

    assert target is not None
    assert target.via_uri
    assert target.label == "Steam"
    assert target.command[0] == f"steam://rungameid/{constants.STEAM_APP_ID_GTA_V}"


def test_resolve_launch_target_detects_steamapps_path(tmp_path: Path) -> None:
    steam_root = tmp_path / "steamapps" / "common" / "Grand Theft Auto V"
    steam_root.mkdir(parents=True)
    install = _install(steam_root, GamePlatform.UNKNOWN)

    target = LaunchService(_Game(install), _Diagnostics(None), _Conflicts(ConflictReport())).resolve_launch_target(
        install
    )

    assert target is not None
    assert target.via_uri
    assert target.label == "Steam"


def test_resolve_launch_target_uses_playgtav_stub(tmp_path: Path) -> None:
    install = _install(tmp_path, GamePlatform.ROCKSTAR)
    stub = tmp_path / "PlayGTAV.exe"
    stub.write_bytes(b"stub")

    target = LaunchService(_Game(install), _Diagnostics(None), _Conflicts(ConflictReport())).resolve_launch_target(
        install
    )

    assert target is not None
    assert not target.via_uri
    assert target.command == (str(stub),)


def test_resolve_executable_falls_back_to_enhanced(tmp_path: Path) -> None:
    enhanced = tmp_path / "GTA5_Enhanced.exe"
    enhanced.write_bytes(b"exe")
    install = GameInstall(
        game_id="gta_v",
        root_path=tmp_path,
        platform=GamePlatform.STEAM,
        executable=None,
    )

    assert LaunchService.resolve_executable(install) == enhanced
