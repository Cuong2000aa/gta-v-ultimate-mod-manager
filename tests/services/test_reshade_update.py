"""Tests for in-app ReShade injector updates."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.result import Result
from gta_mod_manager.graphics import reshade_updater
from gta_mod_manager.models.enums import GamePlatform
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.services.graphics_service import GraphicsService


class _Game:
    def __init__(self, install: GameInstall) -> None:
        self.active = install

    def resolve_active(self) -> Result[GameInstall]:
        return Result.ok(self.active)


def _fake_game(root: Path) -> GameInstall:
    root.mkdir(parents=True, exist_ok=True)
    exe = root / "GTA5.exe"
    exe.write_bytes(b"exe")
    return GameInstall(
        game_id="gta_v",
        root_path=root,
        platform=GamePlatform.STEAM,
        executable=exe,
    )


def test_setup_href_prefers_signed_build() -> None:
    html = """
    <a href="/downloads/ReShade_Setup_6.7.3_Addon.exe" class="button">Addon</a>
    <a href="/downloads/ReShade_Setup_6.7.3.exe" class="button">Download ReShade 6.7.3</a>
    """
    signed = None
    for match in reshade_updater._SETUP_HREF.finditer(html):  # noqa: SLF001
        if "_Addon" not in match.group(2):
            signed = match
            break
    assert signed is not None
    assert signed.group(3) == "6.7.3"


def test_update_reshade_replaces_injector(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    install = _fake_game(tmp_path / "game")
    paths = AppPaths(tmp_path / "app").ensure()
    service = GraphicsService(_Game(install), paths=paths)

    injector_dir = tmp_path / "pack" / "injector"
    injector_dir.mkdir(parents=True)
    injector = injector_dir / "d3d11.dll"
    injector.write_bytes(b"old-reshade")

    monkeypatch.setattr(
        "gta_mod_manager.services.graphics_service.pack_files.pack_root",
        lambda: tmp_path / "pack",
    )
    monkeypatch.setattr(
        "gta_mod_manager.services.graphics_service.pack_files.injector_dll",
        lambda: injector,
    )
    monkeypatch.setattr(
        reshade_updater,
        "discover_latest",
        lambda: ("6.7.3", "https://reshade.me/downloads/ReShade_Setup_6.7.3.exe"),
    )
    monkeypatch.setattr(
        reshade_updater,
        "resolve_seven_zip",
        lambda _configured=None: Path("C:/fake/7z.exe"),
    )
    monkeypatch.setattr(
        "gta_mod_manager.services.graphics_service.http_client.download_file",
        lambda url, destination, **_kwargs: destination.write_bytes(b"setup") or destination,
    )

    def fake_extract(setup: Path, destination: Path, seven_zip: Path) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        dll = destination / "ReShade64.dll"
        dll.write_bytes(b"new-reshade-673")
        return dll

    monkeypatch.setattr(reshade_updater, "extract_reshade64", fake_extract)
    monkeypatch.setattr(reshade_updater, "read_injector_version", lambda _path: "6.3.3")

    result = service.update_reshade()
    assert result.is_ok
    assert "6.7.3" in (result.value or "")
    assert injector.read_bytes() == b"new-reshade-673"
    assert (injector_dir / "VERSION.txt").read_text(encoding="utf-8").startswith("6.7.3")


def test_update_reshade_requires_seven_zip(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    install = _fake_game(tmp_path / "game")
    paths = AppPaths(tmp_path / "app").ensure()
    service = GraphicsService(_Game(install), paths=paths)
    monkeypatch.setattr(reshade_updater, "resolve_seven_zip", lambda _configured=None: None)
    result = service.update_reshade()
    assert result.is_error
    assert result.code == "graphics.reshade_need_7zip"
