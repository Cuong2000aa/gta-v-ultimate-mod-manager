"""Tests for component detection and missing-dependency reporting."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.detector.component_catalog import ComponentProbe
from gta_mod_manager.detector.component_detector import ComponentDetector
from gta_mod_manager.detector.game_detector import GameDetector
from gta_mod_manager.models.component import ComponentSpec
from gta_mod_manager.models.enums import ComponentStatus
from gta_mod_manager.models.game_install import GameInstall


def _install(game_root: Path) -> GameInstall:
    """Return the installation entity for the fake game folder."""
    return GameDetector(()).from_path(game_root)


def test_a_missing_component_is_reported_as_missing(game_root: Path) -> None:
    report = ComponentDetector().detect(_install(game_root))

    script_hook = report.find(constants.COMPONENT_SCRIPT_HOOK_V)
    assert script_hook is not None
    assert script_hook.status is ComponentStatus.MISSING
    assert not report.has(constants.COMPONENT_SCRIPT_HOOK_V)


def test_an_existing_file_makes_the_component_installed(game_root: Path) -> None:
    (game_root / "ScriptHookV.dll").write_bytes(b"MZ")

    report = ComponentDetector().detect(_install(game_root))

    script_hook = report.find(constants.COMPONENT_SCRIPT_HOOK_V)
    assert script_hook is not None
    assert script_hook.status is ComponentStatus.INSTALLED
    assert script_hook.location == game_root.resolve() / "ScriptHookV.dll"


def test_essential_components_drive_the_missing_dependency_list(game_root: Path) -> None:
    report = ComponentDetector().detect(_install(game_root))

    missing_ids = {item.component_id for item in report.missing_dependencies}

    assert constants.COMPONENT_MODS_FOLDER in missing_ids
    assert constants.COMPONENT_SCRIPT_HOOK_V in missing_ids
    # Optional tools must not be reported as missing dependencies.
    assert constants.COMPONENT_RESHADE not in missing_ids


def test_the_mods_folder_probe_reacts_to_the_folder(game_root: Path) -> None:
    (game_root / constants.MODS_FOLDER_NAME).mkdir()

    report = ComponentDetector().detect(_install(game_root))

    assert report.has(constants.COMPONENT_MODS_FOLDER)


def test_a_probe_inside_the_mods_folder_is_resolved(game_root: Path) -> None:
    gameconfig = game_root / "mods" / "update" / "update.rpf" / "common" / "data"
    gameconfig.mkdir(parents=True)
    (gameconfig / constants.GAMECONFIG_XML).write_text("<Root/>", encoding="utf-8")

    report = ComponentDetector().detect(_install(game_root))

    assert report.has(constants.COMPONENT_GAMECONFIG)


def test_require_all_needs_every_listed_entry(game_root: Path) -> None:
    probe = ComponentProbe(
        spec=ComponentSpec(component_id="demo", display_name="Demo"),
        root_files=("first.dll", "second.dll"),
        require_all=True,
    )
    (game_root / "first.dll").write_bytes(b"MZ")

    partial = ComponentDetector((probe,)).detect(_install(game_root))
    assert not partial.has("demo")

    (game_root / "second.dll").write_bytes(b"MZ")
    complete = ComponentDetector((probe,)).detect(_install(game_root))
    assert complete.has("demo")


def test_an_empty_catalog_produces_an_empty_report(game_root: Path) -> None:
    report = ComponentDetector(()).detect(_install(game_root))

    assert report.components == ()
    assert report.find("anything") is None
