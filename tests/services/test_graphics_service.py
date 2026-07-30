"""Tests for CuongVision graphics install / level switch / uninstall."""

from __future__ import annotations

from pathlib import Path

from fivefury import RpfArchive
from fivefury.crypto import OPEN_ENCRYPTION

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.result import Result
from gta_mod_manager.graphics.pack import pack_info, pack_root, preset_path
from gta_mod_manager.models.enums import GamePlatform
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.graphics import GraphicsLevel
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


def test_pack_presets_exist_and_differ() -> None:
    root = pack_root()
    assert pack_info().levels == (GraphicsLevel.CINEMATIC_DETAIL_AA,)
    assert (root / "injector" / "d3d11.dll").is_file() or (
        root / "injector" / "dxgi.dll"
    ).is_file()
    texts = {
        level: preset_path(level).read_text(encoding="utf-8") for level in GraphicsLevel
    }
    assert texts[GraphicsLevel.LIGHT] != texts[GraphicsLevel.MEDIUM]
    assert texts[GraphicsLevel.MEDIUM] != texts[GraphicsLevel.HIGH]
    assert texts[GraphicsLevel.HIGH] != texts[GraphicsLevel.VERY_HIGH]
    assert "MagicBloom" not in texts[GraphicsLevel.LIGHT]
    # FineSharp.fx exports Mode1/Mode2/Mode3 — not a technique named FineSharp.
    assert "Mode1" in texts[GraphicsLevel.MEDIUM]
    assert "[FineSharp.fx]" in texts[GraphicsLevel.MEDIUM]
    assert "AmbientLight" in texts[GraphicsLevel.HIGH]
    assert "MagicBloom" not in texts[GraphicsLevel.HIGH]
    assert "MagicBloom" in texts[GraphicsLevel.VERY_HIGH]
    assert "FilmGrain2" in texts[GraphicsLevel.VERY_HIGH]
    techniques = next(
        line
        for line in texts[GraphicsLevel.VERY_HIGH].splitlines()
        if line.startswith("Techniques=")
    )
    tech_names = {
        name.strip() for name in techniques.split("=", 1)[1].split(",") if name.strip()
    }
    assert "Bloom" not in tech_names  # depth Bloom.fx — MagicBloom is allowed
    assert "MXAO" not in tech_names
    assert "DOF" not in tech_names

    detail = texts[GraphicsLevel.DETAIL_AA]
    detail_techniques = next(
        line for line in detail.splitlines() if line.startswith("Techniques=")
    )
    assert "SMAA" in detail_techniques
    assert "ContrastAdaptiveSharpen" in detail_techniques
    assert "MagicBloom" not in detail

    ultimate = texts[GraphicsLevel.CINEMATIC_DETAIL_AA]
    ultimate_techniques = next(
        line for line in ultimate.splitlines() if line.startswith("Techniques=")
    )
    for technique in (
        "SMAA",
        "CuongCinematic",
        "ContrastAdaptiveSharpen",
    ):
        assert technique in ultimate_techniques
    assert "Mode1" not in ultimate_techniques
    assert "LevelsPlus" not in ultimate_techniques
    assert "FilmicPass" not in ultimate_techniques
    assert "Colourfulness" not in ultimate_techniques
    assert "AmbientLight" not in ultimate_techniques
    assert "MagicBloom" not in ultimate_techniques
    assert "FilmGrain2" not in ultimate_techniques
    assert "HighlightCompression=0.35" in ultimate
    assert "Saturation=1.14" in ultimate
    assert "Sharpening=0.52" in ultimate


def test_detail_aa_assets_are_color_only() -> None:
    root = pack_root() / "shaders"
    shader = (root / "Shaders" / "CuongSMAA.fx").read_text(encoding="utf-8")
    assert "GetLinearizedDepth" not in shader
    assert "LinearizeDepthPass" not in shader
    assert (root / "Shaders" / "SMAA.fxh").is_file()
    assert (root / "Shaders" / "CAS.fx").is_file()
    cinematic = (root / "Shaders" / "CuongCinematic.fx").read_text(encoding="utf-8")
    assert "ReShade::DepthBuffer" not in cinematic
    assert "CuongCinematicPass" in cinematic
    assert not (root / "Shaders" / "CuongWeather.fx").exists()
    assert (root / "Shaders" / "ReShade.fxh").is_file()
    assert (root / "Shaders" / "ReShadeUI.fxh").is_file()
    assert (root / "Textures" / "AreaTex.png").is_file()
    assert (root / "Textures" / "SearchTex.png").is_file()


def test_all_presets_use_valid_levelsplus_and_colourfulness_uniforms() -> None:
    vector_uniforms = (
        "InputBlackPoint",
        "InputWhitePoint",
        "InputGamma",
        "OutputBlackPoint",
        "OutputWhitePoint",
    )
    for level in GraphicsLevel:
        text = preset_path(level).read_text(encoding="utf-8")
        if "[LevelsPlus.fx]" in text:
            for uniform in vector_uniforms:
                line = next(
                    item for item in text.splitlines() if item.startswith(f"{uniform}=")
                )
                assert len(line.split("=", 1)[1].split(",")) == 3
        assert "\ncoeff=" not in text
        assert "\nenable_dithering=" not in text
        if "[Colourfulness.fx]" in text:
            assert "\ncolourfulness=" in text
            assert "\nenable_dither=" in text


def test_install_switch_uninstall(tmp_path: Path) -> None:
    install = _fake_game(tmp_path / "game")
    service = GraphicsService(_Game(install))

    status = service.install(GraphicsLevel.LIGHT).unwrap()
    assert status.installed
    assert status.level is GraphicsLevel.LIGHT
    assert (install.root_path / "d3d11.dll").is_file()
    assert not (install.root_path / "dxgi.dll").exists()
    assert (install.root_path / "reshade-shaders" / "Shaders").is_dir()
    assert not (install.root_path / "reshade-shaders" / "Shaders" / "Bloom.fx").exists()
    assert not (install.root_path / "reshade-shaders" / "Shaders" / "DOF.fx").exists()
    assert (install.root_path / "reshade-shaders" / "Shaders" / "CuongSMAA.fx").is_file()
    assert (install.root_path / "reshade-shaders" / "Shaders" / "CAS.fx").is_file()
    assert (install.root_path / "reshade-shaders" / "Textures" / "AreaTex.png").is_file()
    assert (install.root_path / "reshade-shaders" / "Textures" / "SearchTex.png").is_file()
    active = (install.root_path / "CuongVision" / "active.ini").read_text(encoding="utf-8")
    assert "MagicBloom" not in active

    status = service.set_level(GraphicsLevel.VERY_HIGH).unwrap()
    assert status.level is GraphicsLevel.VERY_HIGH
    active = (install.root_path / "CuongVision" / "active.ini").read_text(encoding="utf-8")
    assert "FilmGrain2" in active

    status = service.set_level(GraphicsLevel.DETAIL_AA).unwrap()
    assert status.level is GraphicsLevel.DETAIL_AA
    active = (install.root_path / "CuongVision" / "active.ini").read_text(encoding="utf-8")
    assert "SMAA" in active
    assert "ContrastAdaptiveSharpen" in active

    status = service.set_level(GraphicsLevel.CINEMATIC_DETAIL_AA).unwrap()
    assert status.level is GraphicsLevel.CINEMATIC_DETAIL_AA
    active = (install.root_path / "CuongVision" / "active.ini").read_text(encoding="utf-8")
    assert "SMAA" in active
    assert "CuongCinematic" in active
    assert "ContrastAdaptiveSharpen" in active
    assert "Mode1" not in active
    assert "LevelsPlus" not in active
    assert "FilmicPass" not in active
    assert "Colourfulness" not in active
    assert "AmbientLight" not in active
    assert "MagicBloom" not in active

    status = service.uninstall().unwrap()
    assert not status.installed
    assert not (install.root_path / "d3d11.dll").exists()
    assert not (install.root_path / "CuongVision").exists()


def test_enb_conflict_blocks_install(tmp_path: Path) -> None:
    install = _fake_game(tmp_path / "game")
    (install.root_path / "enbseries.ini").write_text("[GLOBAL]\n", encoding="utf-8")
    (install.root_path / "d3d11.dll").write_bytes(b"enb")
    service = GraphicsService(_Game(install))
    result = service.install(GraphicsLevel.MEDIUM)
    assert result.is_error
    assert result.code == "graphics.enb_conflict"


def test_install_uses_asi_when_loader_is_present(tmp_path: Path) -> None:
    install = _fake_game(tmp_path / "game")
    (install.root_path / "dinput8.dll").write_bytes(b"asi-loader")
    service = GraphicsService(_Game(install))

    status = service.install(GraphicsLevel.CINEMATIC_DETAIL_AA).unwrap()

    assert status.installed
    assert (install.root_path / "ReShade.asi").is_file()
    assert not (install.root_path / "d3d11.dll").exists()
    assert not (install.root_path / "dxgi.dll").exists()
    manifest = (
        install.root_path / "CuongVision" / "manager_manifest.json"
    ).read_text(encoding="utf-8")
    assert '"injector": "ReShade.asi"' in manifest


def test_selective_2k_roads_install_and_restore(
    tmp_path: Path, monkeypatch
) -> None:
    install = _fake_game(tmp_path / "game")
    stock = install.root_path / "x64g.rpf"
    with RpfArchive.empty("x64g") as outer:
        _entry, nested = outer.add_nested_archive("levels/gta5/generic/gtxd.rpf")
        nested.add("beverlyhillsrd.ytd", b"VANILLA_ROAD")
        nested.add("beverlyhillsrd+hi.ytd", b"VANILLA_ROAD_HI")
        outer.encryption = OPEN_ENCRYPTION
        outer.save(str(stock))

    paths = AppPaths(tmp_path / "app").ensure()
    dummy_archive = paths.downloads / "Betaroad2k.rar"
    dummy_archive.write_bytes(b"fixture")
    service = GraphicsService(_Game(install), paths=paths)
    monkeypatch.setattr(service, "_road_2k_archive", lambda: dummy_archive)

    def fake_extract(_self, _archive: Path, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "beverlyhillsrd.ytd").write_bytes(b"ROAD_2K")
        (destination / "beverlyhillsrd+hi.ytd").write_bytes(b"ROAD_2K_HI")

    monkeypatch.setattr(
        "gta_mod_manager.services.graphics_service.RarExtractor.extract",
        fake_extract,
    )

    result = service.install_road_2k()
    assert result.is_ok
    assert service.road_2k_installed()
    mods = install.mods_path / "x64g.rpf"
    with RpfArchive.from_path(str(mods)) as outer:
        nested = outer.load_nested_archive(
            outer.find_entry("levels/gta5/generic/gtxd.rpf")
        )
        assert nested is not None
        road = next(item for item in nested.iter_entries() if item.name == "beverlyhillsrd.ytd")
        assert nested.read_entry_bytes(road) == b"ROAD_2K"

    result = service.uninstall_road_2k()
    assert result.is_ok
    assert not service.road_2k_installed()
    with RpfArchive.from_path(str(mods)) as outer:
        nested = outer.load_nested_archive(
            outer.find_entry("levels/gta5/generic/gtxd.rpf")
        )
        assert nested is not None
        road = next(item for item in nested.iter_entries() if item.name == "beverlyhillsrd.ytd")
        assert nested.read_entry_bytes(road) == b"VANILLA_ROAD"
