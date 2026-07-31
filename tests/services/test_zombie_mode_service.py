"""Tests for the managed Simple Zombies Reborn game mode."""

from __future__ import annotations

import zipfile
from pathlib import Path

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.result import Result
from gta_mod_manager.models.enums import GamePlatform
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.services.zombie_mode_service import ZombieModeService


class _Game:
    def __init__(self, install: GameInstall) -> None:
        self.active = install

    def resolve_active(self) -> Result[GameInstall]:
        return Result.ok(self.active)


def _install(root: Path) -> GameInstall:
    root.mkdir(parents=True)
    executable = root / "GTA5.exe"
    executable.write_bytes(b"exe")
    return GameInstall(
        game_id="gta_v",
        root_path=root,
        platform=GamePlatform.STEAM,
        executable=executable,
    )


def _dependencies(root: Path) -> None:
    for name in (
        "ScriptHookV.dll",
        "dinput8.dll",
        "ScriptHookVDotNet.asi",
        "ScriptHookVDotNet2.dll",
        "scripts/NativeUI.dll",
    ):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"dependency")


def _archive(path: Path) -> Path:
    payload = (
        "SimpleZombiesReborn.dll",
        "SimpleZombiesReborn.pdb",
        "SimpleZombiesReborn.PhoneBridge.dll",
        "SimpleZombiesReborn.PhoneBridge.pdb",
        "SimpleZombiesReborn.ini",
        "SimpleZombiesReborn/builtin-languages.xml",
    )
    with zipfile.ZipFile(path, "w") as bundle:
        for name in payload:
            bundle.writestr(name, b"payload")
    return path


def test_install_status_and_uninstall(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    game = _install(tmp_path / "game")
    _dependencies(game.root_path)
    paths = AppPaths(tmp_path / "app").ensure()
    service = ZombieModeService(_Game(game), paths)  # type: ignore[arg-type]
    archive = _archive(tmp_path / "zombie.zip")
    monkeypatch.setattr(service, "_archive", lambda: archive)

    before = service.status().unwrap()
    assert not before.installed

    installed = service.install().unwrap()
    assert installed.installed
    assert installed.ready
    assert installed.version == "1.0.5f"
    assert (game.root_path / "scripts" / "SimpleZombiesReborn.dll").is_file()

    removed = service.uninstall().unwrap()
    assert not removed.installed
    assert not (game.root_path / "scripts" / "SimpleZombiesReborn.dll").exists()
    assert (paths.backup / "zombie-mode").is_dir()


def test_status_reports_missing_dependencies(tmp_path: Path) -> None:
    game = _install(tmp_path / "game")
    scripts = game.root_path / "scripts"
    (scripts / "SimpleZombiesReborn").mkdir(parents=True)
    (scripts / "SimpleZombiesReborn.dll").write_bytes(b"mod")
    service = ZombieModeService(
        _Game(game),  # type: ignore[arg-type]
        AppPaths(tmp_path / "app").ensure(),
    )

    status = service.status().unwrap()

    assert status.installed
    assert not status.ready
    assert "ScriptHookV" in status.missing_dependencies
    assert "NativeUI" in status.missing_dependencies
