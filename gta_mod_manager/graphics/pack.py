"""Locate the bundled NCCVision graphics pack on disk."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.models.graphics import GraphicsLevel, GraphicsPackInfo

PACK_ID = "nccvision"
MANIFEST_NAME = "manager_manifest.json"
INSTALL_MARKER_DIR = "NCCVision"
#: Previous brand folder — still cleaned on uninstall / treated as installed.
LEGACY_MARKER_DIRS: tuple[str, ...] = ("CuongVision",)


def pack_info() -> GraphicsPackInfo:
    """Return metadata for the bundled pack."""
    return GraphicsPackInfo(
        pack_id=PACK_ID,
        display_name="NCCVision",
        description_key="graphics.pack.nccvision.desc",
        levels=(GraphicsLevel.CINEMATIC_DETAIL_AA,),
    )


def pack_root() -> Path:
    """Return the filesystem path of the bundled NCCVision pack."""
    root = Path(__file__).resolve().parents[1] / "resources" / "graphics" / "nccvision"
    if root.is_dir():
        return root
    raise FileNotFoundError("NCCVision graphics pack is missing from resources")


def injector_dll() -> Path:
    """Return the bundled ReShade injector (``d3d11.dll``; legacy ``dxgi.dll`` ok)."""
    root = pack_root() / "injector"
    for name in ("d3d11.dll", "dxgi.dll"):
        path = root / name
        if path.is_file():
            return path
    raise FileNotFoundError(f"Missing ReShade injector under: {root}")


def shaders_root() -> Path:
    """Return the folder containing ``Shaders`` / ``Textures``."""
    path = pack_root() / "shaders"
    if not (path / "Shaders").is_dir():
        raise FileNotFoundError(f"Missing shaders folder: {path}")
    return path


def preset_path(level: GraphicsLevel) -> Path:
    """Return the preset INI for ``level``."""
    path = pack_root() / "presets" / level.preset_filename
    if not path.is_file():
        raise FileNotFoundError(f"Missing preset: {path}")
    return path


def marker_dirs() -> tuple[str, ...]:
    """Return current and legacy install marker folder names."""
    return (INSTALL_MARKER_DIR, *LEGACY_MARKER_DIRS)
