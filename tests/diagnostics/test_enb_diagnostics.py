"""Tests for ENB leftover detection and one-click quarantine repair."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.diagnostics.actions import FIX_QUARANTINE_ENB_LEFTOVERS
from gta_mod_manager.diagnostics.enb import list_enb_leftover_files
from gta_mod_manager.diagnostics.repairs import apply_diagnostic_fix
from gta_mod_manager.diagnostics.scanner import DiagnosticsScanner
from gta_mod_manager.models.diagnostic import DiagnosticSeverity
from gta_mod_manager.models.enums import GamePlatform
from gta_mod_manager.models.game_install import GameInstall


def _install(root: Path) -> GameInstall:
    (root / "GTA5.exe").write_bytes(b"exe")
    return GameInstall(game_id="gta_v", root_path=root, platform=GamePlatform.STEAM)


def test_detects_orphan_enb_config_as_fixable(tmp_path: Path) -> None:
    root = tmp_path / "game"
    root.mkdir()
    (root / "enblocal.ini").write_text("[GLOBAL]\n", encoding="utf-8")
    (root / "enbseries.ini").write_text("[EFFECT]\n", encoding="utf-8")
    (root / "enbeffect.fx").write_text("// fx\n", encoding="utf-8")

    leftovers = list_enb_leftover_files(root)
    assert set(leftovers) >= {"enblocal.ini", "enbseries.ini", "enbeffect.fx"}

    report = DiagnosticsScanner().scan(_install(root))
    finding = next(item for item in report.findings if item.code == "enb.orphan_config")
    assert finding.severity is DiagnosticSeverity.WARNING
    assert finding.fix_action == FIX_QUARANTINE_ENB_LEFTOVERS
    assert finding.is_fixable
    assert "enblocal.ini" in finding.fix_targets


def test_quarantine_moves_enb_files_into_mods(tmp_path: Path) -> None:
    root = tmp_path / "game"
    root.mkdir()
    (root / "GTA5.exe").write_bytes(b"exe")
    (root / "enblocal.ini").write_text("x", encoding="utf-8")
    (root / "enbseries.ini").write_text("y", encoding="utf-8")

    result = apply_diagnostic_fix(
        root,
        FIX_QUARANTINE_ENB_LEFTOVERS,
        ("enblocal.ini", "enbseries.ini"),
    )
    assert result.is_ok
    assert not (root / "enblocal.ini").exists()
    assert not (root / "enbseries.ini").exists()
    quarantine = root.joinpath(*constants.ENB_QUARANTINE_FOLDER.split("/"))
    assert (quarantine / "enblocal.ini").is_file()
    assert (quarantine / "enbseries.ini").is_file()

    # Re-scan should no longer flag orphan ENB config.
    report = DiagnosticsScanner().scan(_install(root))
    assert all(item.code != "enb.orphan_config" for item in report.findings)


def test_quarantine_refuses_proxy_dll(tmp_path: Path) -> None:
    root = tmp_path / "game"
    root.mkdir()
    (root / "d3d11.dll").write_bytes(b"dll")
    result = apply_diagnostic_fix(root, FIX_QUARANTINE_ENB_LEFTOVERS, ("d3d11.dll",))
    assert not result.is_ok
    assert (root / "d3d11.dll").is_file()
