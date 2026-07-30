"""Install / switch / remove the bundled CuongVision ReShade pack.

Designed for FPS-safe cinematic grades (no MXAO / DOF / ENB). Uses ReShade via
``ReShade.asi`` when an ASI loader exists, otherwise ``d3d11.dll``; legacy
``dxgi.dll`` is removed on deploy.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.result import Result
from gta_mod_manager.graphics import pack as pack_files
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.graphics import GraphicsLevel, GraphicsStatus
from gta_mod_manager.models.install_plan import ArchiveMemberImport
from gta_mod_manager.net import http_client
from gta_mod_manager.plugins.gta_v.rpf_archive import import_members, restore_stock_members
from gta_mod_manager.scanner.extractors import RarExtractor
from gta_mod_manager.services.game_service import GameService
from gta_mod_manager.utils import hashing

_LOGGER = get_logger("services.graphics")

#: Use ASI loading when GTA's ASI loader is present. Some current Legacy builds
#: ignore both DXGI and D3D11 proxy names while still loading every ``*.asi``.
_INJECTOR_NAME = "d3d11.dll"
_ASI_INJECTOR = "ReShade.asi"
_LEGACY_INJECTOR = "dxgi.dll"
_SHADER_DIR = "reshade-shaders"
_OWNED_FILES = (
    _INJECTOR_NAME,
    _ASI_INJECTOR,
    _LEGACY_INJECTOR,
    "ReShade.ini",
    "ReShadePreset.ini",
)
_OWNED_DIRS = (_SHADER_DIR, pack_files.INSTALL_MARKER_DIR)
_ENB_SERIES_MARKERS = ("enbseries.ini", "enblocal.ini")
_ROAD_2K_URL = (
    "https://files.gta5-mods.com/uploads/roads-textures-2k/"
    "a48986-Betaroad2k.rar"
)
_ROAD_2K_ARCHIVE = "Betaroad2k.rar"
_ROAD_2K_SHA256 = "d7650417fc94ba88b5624d41885675ea78ba06184cb45347272c7d6dda8d597d"
_ROAD_2K_RPF = "x64g.rpf"
_ROAD_2K_NESTED = "levels/gta5/generic/gtxd.rpf"
_ROAD_2K_MEMBERS = ("beverlyhillsrd.ytd", "beverlyhillsrd+hi.ytd")
_ROAD_2K_MARKER = "cuongvision-road-2k.json"


class GraphicsService:
    """Manage the CuongVision cinematic pack on the active GTA V install."""

    def __init__(self, game: GameService, paths: AppPaths | None = None) -> None:
        self._game = game
        self._paths = paths

    def status(self, install: GameInstall | None = None) -> Result[GraphicsStatus]:
        """Return whether CuongVision is installed and at which level."""
        target = self._resolve(install)
        if target.is_error:
            return Result.fail(target.error or "No game", code=target.code)
        root = target.unwrap().root_path
        manifest = self._read_manifest(root)
        injector = any(
            (root / name).is_file()
            for name in (_ASI_INJECTOR, _INJECTOR_NAME, _LEGACY_INJECTOR)
        )
        shaders = (root / _SHADER_DIR / "Shaders").is_dir()
        installed = bool(manifest) or (
            injector and shaders and (root / pack_files.INSTALL_MARKER_DIR).is_dir()
        )
        level: GraphicsLevel | None = None
        if manifest and manifest.get("level"):
            try:
                level = GraphicsLevel(str(manifest["level"]))
            except ValueError:
                level = None
        conflict = self._has_enb_proxy(root)
        message = ""
        if conflict:
            message = "ENB proxy DLL detected — disable ENB before using CuongVision"
        elif installed and level is not None:
            message = f"CuongVision active ({level.value})"
        elif installed:
            message = "CuongVision files present"
        else:
            message = "CuongVision not installed"
        return Result.ok(
            GraphicsStatus(
                pack_id=pack_files.PACK_ID,
                installed=installed,
                level=level,
                injector_present=injector,
                shaders_present=shaders,
                preset_path=(
                    root / pack_files.INSTALL_MARKER_DIR / "active.ini"
                    if (root / pack_files.INSTALL_MARKER_DIR / "active.ini").is_file()
                    else None
                ),
                conflict_enb=conflict,
                message=message,
            )
        )

    def install(
        self,
        level: GraphicsLevel,
        install: GameInstall | None = None,
    ) -> Result[GraphicsStatus]:
        """Install or re-apply CuongVision at ``level``."""
        target = self._resolve(install)
        if target.is_error:
            return Result.fail(target.error or "No game", code=target.code)
        root = target.unwrap().root_path
        if self._has_enb_proxy(root):
            return Result.fail(
                "ENB (enbseries.ini / enblocal.ini) is present. Remove ENB first — "
                "ENB + ReShade together often crashes GTA V.",
                code="graphics.enb_conflict",
            )
        try:
            self._deploy(root, level)
        except OSError as error:
            return Result.fail(str(error), code="graphics.install_failed")
        except FileNotFoundError as error:
            return Result.fail(str(error), code="graphics.pack_missing")
        _LOGGER.info("Installed CuongVision level=%s at %s", level.value, root)
        return self.status(target.unwrap())

    def set_level(
        self,
        level: GraphicsLevel,
        install: GameInstall | None = None,
    ) -> Result[GraphicsStatus]:
        """Switch cinematic level without re-copying the injector when possible."""
        current = self.status(install)
        if current.is_error:
            return current
        state = current.unwrap()
        if not state.installed:
            return self.install(level, install)
        target = self._resolve(install)
        if target.is_error:
            return Result.fail(target.error or "No game", code=target.code)
        root = target.unwrap().root_path
        try:
            self._write_preset(root, level)
            self._write_manifest(root, level)
        except OSError as error:
            return Result.fail(str(error), code="graphics.level_failed")
        _LOGGER.info("Switched CuongVision to %s", level.value)
        return self.status(target.unwrap())

    def uninstall(self, install: GameInstall | None = None) -> Result[GraphicsStatus]:
        """Remove CuongVision files owned by this manager."""
        target = self._resolve(install)
        if target.is_error:
            return Result.fail(target.error or "No game", code=target.code)
        root = target.unwrap().root_path
        manifest = self._read_manifest(root)
        # Only delete injector if we installed it (manifest) or marker exists.
        owned = bool(manifest) or (root / pack_files.INSTALL_MARKER_DIR).is_dir()
        if not owned:
            return Result.fail(
                "CuongVision is not installed by this manager",
                code="graphics.not_installed",
            )
        try:
            for name in _OWNED_FILES:
                path = root / name
                if path.is_file():
                    path.unlink()
            for name in _OWNED_DIRS:
                path = root / name
                if path.is_dir():
                    shutil.rmtree(path)
            log = root / "ReShade.log"
            if log.is_file():
                log.unlink()
        except OSError as error:
            return Result.fail(str(error), code="graphics.uninstall_failed")
        _LOGGER.info("Uninstalled CuongVision from %s", root)
        return self.status(target.unwrap())

    def road_2k_installed(self, install: GameInstall | None = None) -> bool:
        """Return whether the optional pinned 2K road texture add-on is installed."""
        target = self._resolve(install)
        if target.is_error:
            return False
        return (target.unwrap().mods_path / _ROAD_2K_MARKER).is_file()

    def install_road_2k(self, install: GameInstall | None = None) -> Result[str]:
        """Download and install the selective 2K road textures into ``mods/x64g.rpf``."""
        target = self._resolve(install)
        if target.is_error:
            return Result.fail(target.error or "No game", code=target.code)
        if self._paths is None:
            return Result.fail(
                "Application data paths are unavailable",
                code="graphics.road_2k_paths_missing",
            )

        game = target.unwrap()
        stock = game.root_path / _ROAD_2K_RPF
        mods_archive = game.mods_path / _ROAD_2K_RPF
        if not stock.is_file():
            return Result.fail(
                "x64g.rpf was not found. This add-on supports GTA V Legacy only.",
                code="graphics.road_2k_legacy_only",
            )

        created_copy = False
        workspace = self._paths.temp / "cuongvision-road-2k"
        try:
            archive = self._road_2k_archive()
            if workspace.exists():
                shutil.rmtree(workspace)
            RarExtractor().extract(archive, workspace)

            sources = tuple(workspace / name for name in _ROAD_2K_MEMBERS)
            missing = [path.name for path in sources if not path.is_file()]
            if missing:
                return Result.fail(
                    f"The official texture archive is missing: {', '.join(missing)}",
                    code="graphics.road_2k_payload_invalid",
                )

            if not mods_archive.is_file():
                mods_archive.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(stock, mods_archive)
                created_copy = True

            imports = tuple(
                ArchiveMemberImport(
                    source_path=source,
                    member_path=f"{_ROAD_2K_NESTED}/{source.name}",
                )
                for source in sources
            )
            import_members(mods_archive, imports)
            marker = game.mods_path / _ROAD_2K_MARKER
            marker.write_text(
                json.dumps(
                    {
                        "pack": "CuongVision Selective 2K Roads",
                        "version": "1.0",
                        "source": _ROAD_2K_URL,
                        "sha256": _ROAD_2K_SHA256,
                        "archive": _ROAD_2K_RPF,
                        "members": [
                            f"{_ROAD_2K_NESTED}/{name}" for name in _ROAD_2K_MEMBERS
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as error:  # noqa: BLE001 - convert archive/RPF errors to Result
            if created_copy and mods_archive.is_file():
                mods_archive.unlink(missing_ok=True)
            return Result.fail(str(error), code="graphics.road_2k_install_failed")
        finally:
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)

        _LOGGER.info("Installed selective 2K roads into %s", mods_archive)
        return Result.ok(
            "Đã cài đường 2K chọn lọc vào mods/x64g.rpf; file game gốc không bị sửa."
        )

    def uninstall_road_2k(self, install: GameInstall | None = None) -> Result[str]:
        """Restore the two stock road dictionaries and remove the add-on marker."""
        target = self._resolve(install)
        if target.is_error:
            return Result.fail(target.error or "No game", code=target.code)
        game = target.unwrap()
        marker = game.mods_path / _ROAD_2K_MARKER
        if not marker.is_file():
            return Result.fail(
                "The selective 2K road add-on is not installed",
                code="graphics.road_2k_not_installed",
            )

        stock = game.root_path / _ROAD_2K_RPF
        mods_archive = game.mods_path / _ROAD_2K_RPF
        members = tuple(f"{_ROAD_2K_NESTED}/{name}" for name in _ROAD_2K_MEMBERS)
        try:
            outcome = restore_stock_members(
                mods_archive,
                stock,
                members,
                game_root=game.root_path,
            )
            marker.unlink(missing_ok=True)
        except Exception as error:  # noqa: BLE001 - convert RPF errors to Result
            return Result.fail(str(error), code="graphics.road_2k_uninstall_failed")

        _LOGGER.info("Uninstalled selective 2K roads from %s", mods_archive)
        return Result.ok(
            f"Đã gỡ đường 2K và khôi phục {outcome.restored} texture gốc."
        )

    def _road_2k_archive(self) -> Path:
        """Return the verified official archive, downloading it when absent."""
        assert self._paths is not None
        archive = self._paths.downloads / _ROAD_2K_ARCHIVE
        if archive.is_file() and hashing.sha256_file(archive) == _ROAD_2K_SHA256:
            return archive
        archive.unlink(missing_ok=True)
        http_client.download_file(_ROAD_2K_URL, archive)
        actual = hashing.sha256_file(archive)
        if actual != _ROAD_2K_SHA256:
            archive.unlink(missing_ok=True)
            raise OSError(
                "The downloaded texture archive failed its SHA-256 safety check"
            )
        return archive

    def _deploy(self, root: Path, level: GraphicsLevel) -> None:
        injector = pack_files.injector_dll()
        shaders = pack_files.shaders_root()
        # Never leave two copies of ReShade: that double-hooks the swap chain.
        injector_name = (
            _ASI_INJECTOR if (root / "dinput8.dll").is_file() else _INJECTOR_NAME
        )
        for name in (_ASI_INJECTOR, _INJECTOR_NAME, _LEGACY_INJECTOR):
            path = root / name
            if path.is_file():
                path.unlink()
        shutil.copy2(injector, root / injector_name)

        shader_dst = root / _SHADER_DIR
        if shader_dst.exists():
            shutil.rmtree(shader_dst)
        # Only ship color/lighting shaders — skip depth-heavy ones (DOF, Bloom depth path).
        shader_dst.mkdir(parents=True)
        src_shaders = shaders / "Shaders"
        src_textures = shaders / "Textures"
        dst_shaders = shader_dst / "Shaders"
        dst_textures = shader_dst / "Textures"
        dst_shaders.mkdir(parents=True)
        if src_textures.is_dir():
            shutil.copytree(src_textures, dst_textures)
        else:
            dst_textures.mkdir(parents=True)
        skip = {
            "dof.fx",
            "lightdof.fx",
            "bloom.fx",  # samples DepthBuffer — unstable on GTA V
            "reflectivebumpmapping.fx",
            "nightvision.fx",
            "glitch.fx",
            "fakemotionblur.fx",
            "hq4x.fx",
        }
        for item in src_shaders.iterdir():
            if not item.is_file():
                continue
            if item.name.lower() in skip:
                continue
            shutil.copy2(item, dst_shaders / item.name)

        marker = root / pack_files.INSTALL_MARKER_DIR
        marker.mkdir(parents=True, exist_ok=True)
        self._write_preset(root, level)
        self._write_reshade_ini(root)
        self._write_manifest(root, level)

    def _write_preset(self, root: Path, level: GraphicsLevel) -> None:
        source = pack_files.preset_path(level)
        marker = root / pack_files.INSTALL_MARKER_DIR
        marker.mkdir(parents=True, exist_ok=True)
        for old_preset in marker.glob("*.ini"):
            old_preset.unlink()
        active = marker / "active.ini"
        shutil.copy2(source, active)
        # Also keep named copy for browsing in ReShade menu.
        shutil.copy2(source, marker / level.preset_filename)
        # ReShade default companion file some builds read.
        shutil.copy2(source, root / "ReShadePreset.ini")

    def _write_reshade_ini(self, root: Path) -> None:
        content = (
            "[GENERAL]\n"
            f"EffectSearchPaths=.\\{_SHADER_DIR}\\Shaders\n"
            f"TextureSearchPaths=.\\{_SHADER_DIR}\\Textures\n"
            f"PresetPath=.\\{pack_files.INSTALL_MARKER_DIR}\\active.ini\n"
            "PerformanceMode=1\n"
            "TutorialProgress=4\n"
            "\n"
            "[INPUT]\n"
            "KeyMenu=36,0,0,0\n"
            "KeyEffects=145,0,0,0\n"
        )
        (root / "ReShade.ini").write_text(content, encoding="utf-8")

    def _write_manifest(self, root: Path, level: GraphicsLevel) -> None:
        injector_name = (
            _ASI_INJECTOR if (root / _ASI_INJECTOR).is_file() else _INJECTOR_NAME
        )
        payload = {
            "pack_id": pack_files.PACK_ID,
            "level": level.value,
            "owned_files": list(_OWNED_FILES),
            "owned_dirs": list(_OWNED_DIRS),
            "fps_safe": True,
            "pack_version": "3.0-ultimate",
            "injector": injector_name,
            "avoided_effects": ["MXAO", "DOF", "SSR", "ENB", "DepthBloom"],
            "detail_aa": {
                "anti_aliasing": "SMAA color-edge only",
                "sharpening": "AMD FidelityFX CAS",
                "color_grade": "CuongCinematic highlight-safe rich color",
                "depth_access": False,
            },
        }
        path = root / pack_files.INSTALL_MARKER_DIR / pack_files.MANIFEST_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _read_manifest(self, root: Path) -> dict[str, object] | None:
        path = root / pack_files.INSTALL_MARKER_DIR / pack_files.MANIFEST_NAME
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _has_enb_proxy(root: Path) -> bool:
        """Return whether a real ENB install is present (not our ReShade d3d11)."""
        if any((root / name).is_file() for name in _ENB_SERIES_MARKERS):
            return True
        # Foreign d3d10/d3d9 proxies without our manifest are treated as ENB-like.
        manifest = root / pack_files.INSTALL_MARKER_DIR / pack_files.MANIFEST_NAME
        if manifest.is_file():
            return False
        return (root / "d3d10.dll").is_file() or (
            (root / "d3d9.dll").is_file() and (root / "enbseries").is_dir()
        )

    def _resolve(self, install: GameInstall | None) -> Result[GameInstall]:
        if install is not None:
            return Result.ok(install)
        if self._game.active is not None:
            return Result.ok(self._game.active)
        return self._game.resolve_active()
