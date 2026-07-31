"""Tests for the Story Mode essentials kit."""

from __future__ import annotations

import zipfile
from pathlib import Path

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.result import Result
from gta_mod_manager.detector.component_catalog import default_catalog
from gta_mod_manager.detector.component_detector import ComponentDetector
from gta_mod_manager.models.enums import GamePlatform
from gta_mod_manager.models.essentials import EssentialAction
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.services import essentials_service as essentials_mod
from gta_mod_manager.services.essentials_service import EssentialsService


class _Game:
    def __init__(self, install: GameInstall) -> None:
        self.active = install

    def resolve_active(self) -> Result[GameInstall]:
        return Result.ok(self.active)

    def ensure_mods_folder(self, install: GameInstall) -> Path:
        path = install.root_path / "mods"
        path.mkdir(parents=True, exist_ok=True)
        return path


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


def _zip_with(path: Path, names: tuple[str, ...]) -> Path:
    with zipfile.ZipFile(path, "w") as bundle:
        for name in names:
            bundle.writestr(name, b"payload")
    return path


def test_status_and_auto_install(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    game = _install(tmp_path / "game")
    paths = AppPaths(tmp_path / "app").ensure()
    service = EssentialsService(_Game(game), ComponentDetector(default_catalog()), paths)  # type: ignore[arg-type]

    shvdn = _zip_with(
        tmp_path / "shvdn.zip",
        (
            "ScriptHookVDotNet.asi",
            "ScriptHookVDotNet2.dll",
            "ScriptHookVDotNet3.dll",
            "ScriptHookVDotNet.ini",
        ),
    )
    native = _zip_with(tmp_path / "native.zip", ("NativeUI.dll", "NativeUI.xml"))

    def fake_cached(name: str, url: str, sha256: str, label: str) -> Path:
        return shvdn if "ScriptHook" in label or "SHVDN" in label or "DotNet" in name else native

    monkeypatch.setattr(service, "_cached_archive", fake_cached)

    before = service.status().unwrap()
    assert not before.ready
    assert "ScriptHookVDotNet" in before.auto_installable
    assert "NativeUI" in before.auto_installable
    assert any(item.action is EssentialAction.OPEN_BROWSER for item in before.items)

    after = service.install_auto().unwrap()
    assert (game.root_path / "mods").is_dir()
    assert (game.root_path / "ScriptHookVDotNet.asi").is_file()
    assert (game.root_path / "scripts" / "NativeUI.dll").is_file()
    assert "ScriptHookVDotNet" not in after.auto_installable
    assert "NativeUI" not in after.auto_installable


def test_pinned_hashes_are_lowercase_hex() -> None:
    assert len(essentials_mod._SHVDN_SHA256) == 64
    assert essentials_mod._SHVDN_SHA256 == essentials_mod._SHVDN_SHA256.lower()
    assert len(essentials_mod._NATIVEUI_SHA256) == 64
    assert essentials_mod._NATIVEUI_SHA256 == essentials_mod._NATIVEUI_SHA256.lower()
