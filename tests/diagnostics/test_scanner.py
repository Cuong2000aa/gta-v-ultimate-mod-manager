"""Tests for the GTA V diagnostics scanner."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.diagnostics.scanner import DiagnosticsScanner
from gta_mod_manager.models.diagnostic import DiagnosticSeverity
from gta_mod_manager.models.enums import GamePlatform
from gta_mod_manager.models.game_install import GameInstall


def _install(root: Path) -> GameInstall:
    (root / "GTA5.exe").write_bytes(b"exe")
    return GameInstall(game_id="gta_v", root_path=root, platform=GamePlatform.STEAM)


def test_detects_err_sys_invalidresource(tmp_path: Path) -> None:
    root = tmp_path / "game"
    root.mkdir()
    (root / "asiloader.log").write_text(
        "boot\nERR_SYS_INVALIDRESOURCE_5 Corrupt game data\n",
        encoding="utf-8",
    )
    report = DiagnosticsScanner().scan(_install(root))
    assert any(item.code == "sys.invalid_resource" for item in report.findings)


def test_detects_err_gfx_d3d_init_in_log(tmp_path: Path) -> None:
    root = tmp_path / "game"
    root.mkdir()
    (root / "ScriptHookV.log").write_text(
        "something\nERR_GFX_D3D_INIT\nFailed Initialization. Please reboot\n",
        encoding="utf-8",
    )
    report = DiagnosticsScanner().scan(_install(root))
    codes = {item.code for item in report.findings}
    assert "gfx.d3d_init" in codes
    finding = next(item for item in report.findings if item.code == "gfx.d3d_init")
    assert finding.severity is DiagnosticSeverity.ERROR
    assert "DirectX" in finding.title or "D3D" in finding.title


def test_detects_orphan_enb_config(tmp_path: Path) -> None:
    root = tmp_path / "game"
    root.mkdir()
    (root / "enblocal.ini").write_text("[PROXY]\nProxyLibrary=d3d11.dll\n", encoding="utf-8")
    report = DiagnosticsScanner().scan(_install(root))
    assert any(item.code == "enb.orphan_config" for item in report.findings)


def test_openiv_missing_when_mods_present(tmp_path: Path) -> None:
    root = tmp_path / "game"
    mods = root / "mods"
    mods.mkdir(parents=True)
    (mods / "x64e.rpf").write_bytes(b"rpf")
    report = DiagnosticsScanner().scan(_install(root))
    assert any(item.code == "asi.openiv_missing" for item in report.findings)


def test_clean_install_reports_ok(tmp_path: Path) -> None:
    root = tmp_path / "game"
    root.mkdir()
    (root / "dinput8.dll").write_bytes(b"asi")
    (root / "OpenIV.asi").write_bytes(b"asi")
    report = DiagnosticsScanner().scan(_install(root))
    assert report.problem_count == 0
    assert any(item.code == "ok.clean" for item in report.findings)
