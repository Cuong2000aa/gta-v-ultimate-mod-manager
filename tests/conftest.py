"""Shared fixtures: a temporary application, sample archives and a Qt app."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from gta_mod_manager.bootstrap import Application, build_application
from gta_mod_manager.core import constants
from gta_mod_manager.core.app_paths import AppPaths
from tests.helpers.rpf_fixtures import write_minimal_update_rpf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture()
def app_paths(tmp_path: Path) -> AppPaths:
    """Return an isolated working-directory layout."""
    return AppPaths(root=tmp_path / "appdata").ensure()


@pytest.fixture()
def game_root(tmp_path: Path) -> Path:
    """Create a fake but convincing GTA V installation."""
    root = tmp_path / "Grand Theft Auto V"
    root.mkdir(parents=True)
    for entry in constants.GAME_SIGNATURE_ENTRIES:
        target = root / entry
        if target.suffix:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fake archive")
        else:
            target.mkdir(parents=True, exist_ok=True)
    write_minimal_update_rpf(root / "update" / "update.rpf")
    (root / "x64" / "dlcpacks").mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture()
def application(app_paths: AppPaths, game_root: Path) -> Application:
    """Return a fully wired application pointed at the fake installation."""
    built = build_application(app_paths, console_logging=False)
    built.game.select(game_root).unwrap()
    return built


@pytest.fixture()
def script_mod_zip(tmp_path: Path) -> Path:
    """Return a zip containing a ScriptHookVDotNet script."""
    archive = tmp_path / "Cool Script 1.2.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("scripts/CoolScript.dll", b"MZ fake managed assembly")
        bundle.writestr("scripts/CoolScript.ini", "[Settings]\nEnabled=true\n")
        bundle.writestr("readme.txt", "Requires ScriptHookVDotNet.\nDrop into scripts/.\n")
    return archive


@pytest.fixture()
def addon_vehicle_zip(tmp_path: Path) -> Path:
    """Return a zip shaped like a typical add-on vehicle DLC pack."""
    archive = tmp_path / "Adder2 Addon.zip"
    vehicles_meta = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<CVehicleModelInfo__InitDataList>\n"
        "  <InitDatas>\n"
        "    <Item>\n"
        "      <modelName>adder2</modelName>\n"
        "      <handlingId>ADDER2</handlingId>\n"
        "      <txdName>adder2</txdName>\n"
        "      <vehicleMakeName>TRUFFADE</vehicleMakeName>\n"
        "    </Item>\n"
        "  </InitDatas>\n"
        "</CVehicleModelInfo__InitDataList>\n"
    )
    handling_meta = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<CHandlingDataMgr>\n"
        "  <HandlingData>\n"
        "    <Item type='CHandlingData'>\n"
        "      <handlingName>ADDER2</handlingName>\n"
        "      <fMass value='1800.0'/>\n"
        "    </Item>\n"
        "  </HandlingData>\n"
        "</CHandlingDataMgr>\n"
    )
    setup2 = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<SSetupData>\n"
        "  <deviceName>dlc_adder2</deviceName>\n"
        "  <datFile>content.xml</datFile>\n"
        "  <nameHash>adder2</nameHash>\n"
        "  <order value='24'/>\n"
        "</SSetupData>\n"
    )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<CDataFileMgr__ContentsOfDataFileXml>\n"
        "  <dataFiles>\n"
        "    <Item>\n"
        "      <filename>dlc_adder2:/%PLATFORM%/levels/gta5/vehicles.rpf</filename>\n"
        "      <fileType>RPF_FILE</fileType>\n"
        "    </Item>\n"
        "  </dataFiles>\n"
        "</CDataFileMgr__ContentsOfDataFileXml>\n"
    )
    base = "adder2/"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(f"{base}setup2.xml", setup2)
        bundle.writestr(f"{base}content.xml", content)
        bundle.writestr(f"{base}dlc.rpf", b"fake pack payload")
        bundle.writestr(f"{base}data/vehicles.meta", vehicles_meta)
        bundle.writestr(f"{base}data/handling.meta", handling_meta)
        bundle.writestr("readme.txt", "Add-on vehicle. Add dlcpacks:/adder2/ to dlclist.xml.\n")
    return archive


@pytest.fixture()
def asi_mod_zip(tmp_path: Path) -> Path:
    """Return a zip containing an ASI plugin destined for the game root."""
    archive = tmp_path / "SuperPlugin 5.0.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("SuperPlugin.asi", b"MZ fake asi")
        bundle.writestr("SuperPlugin.ini", "[Keys]\nMenu=F4\n")
    return archive


@pytest.fixture(scope="session")
def qt_app():  # noqa: ANN201 - QApplication, imported lazily
    """Return the single QApplication instance used by the GUI tests."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    instance = QApplication.instance() or QApplication([])
    yield instance
