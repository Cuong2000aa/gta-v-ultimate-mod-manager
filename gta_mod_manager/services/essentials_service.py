"""Install verified Story Mode essentials (SHVDN, NativeUI) and guide the rest."""

from __future__ import annotations

import shutil
import webbrowser
import zipfile
from pathlib import Path, PurePosixPath

from gta_mod_manager.core import constants
from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.result import Result
from gta_mod_manager.detector.component_detector import ComponentDetector
from gta_mod_manager.models.component import DetectedComponent
from gta_mod_manager.models.essentials import EssentialAction, EssentialItem, EssentialsStatus
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.net import http_client
from gta_mod_manager.services.game_service import GameService
from gta_mod_manager.utils import hashing

_LOGGER = get_logger("services.essentials")

_SHVDN_VERSION = "v3.7.0-nightly.188"
_SHVDN_ARCHIVE = f"ScriptHookVDotNet-{_SHVDN_VERSION}.zip"
_SHVDN_URL = (
    "https://github.com/scripthookvdotnet/scripthookvdotnet-nightly/releases/download/"
    f"{_SHVDN_VERSION}/{_SHVDN_ARCHIVE}"
)
_SHVDN_SHA256 = "a9df84396363f040f40d6635e4f81951cac45f024be64d8d323ae24f4eceed19"
_SHVDN_FILES = (
    "ScriptHookVDotNet.asi",
    "ScriptHookVDotNet2.dll",
    "ScriptHookVDotNet3.dll",
)

_NATIVEUI_VERSION = "1.9.1"
_NATIVEUI_ARCHIVE = f"NativeUI-{_NATIVEUI_VERSION}.zip"
_NATIVEUI_URL = "https://github.com/Guad/NativeUI/releases/download/1.9.1/Release.zip"
_NATIVEUI_SHA256 = "690aae3de0e4bc177658425d76f90bea48ff2305e39b174ff4adec2a2a34cf6e"

_SCRIPT_HOOK_HOME = "http://www.dev-c.com/gtav/scripthookv/"
_OPENIV_HOME = "https://openiv.com/"


class EssentialsService:
    """Detect missing essentials and install the redistributable ones."""

    def __init__(
        self,
        game: GameService,
        components: ComponentDetector,
        paths: AppPaths,
    ) -> None:
        self._game = game
        self._components = components
        self._paths = paths

    def status(self, install: GameInstall | None = None) -> Result[EssentialsStatus]:
        """Return presence and next-step actions for each essential."""
        target = self._resolve(install)
        if target.is_error:
            return Result.fail(target.error or "No game", code=target.code)
        game = target.unwrap()
        root = game.root_path
        report = self._components.detect(game)
        by_id = {item.component_id: item for item in report.components}

        items = (
            self._item(
                by_id,
                constants.COMPONENT_MODS_FOLDER,
                "mods folder",
                installed=(root / constants.MODS_FOLDER_NAME).is_dir(),
                action=EssentialAction.CREATE_FOLDER,
                detail="Created under the game folder for safe OpenIV installs.",
            ),
            self._item(
                by_id,
                constants.COMPONENT_SCRIPT_HOOK_V,
                "ScriptHookV",
                installed=(root / "ScriptHookV.dll").is_file(),
                action=EssentialAction.OPEN_BROWSER,
                detail="Download from Alexander Blade; version must match your game build.",
                homepage=_SCRIPT_HOOK_HOME,
            ),
            self._item(
                by_id,
                constants.COMPONENT_ASI_LOADER,
                "ASI Loader (dinput8.dll)",
                installed=(root / "dinput8.dll").is_file(),
                action=EssentialAction.OPEN_BROWSER,
                detail="Bundled with ScriptHookV — copy dinput8.dll into the game root.",
                homepage=_SCRIPT_HOOK_HOME,
            ),
            self._item(
                by_id,
                constants.COMPONENT_OPENIV_ASI,
                "OpenIV.asi",
                installed=(root / "OpenIV.asi").is_file(),
                action=EssentialAction.OPEN_BROWSER,
                detail="Install OpenIV, then use ASI Manager to drop OpenIV.asi.",
                homepage=_OPENIV_HOME,
            ),
            self._item(
                by_id,
                constants.COMPONENT_SCRIPT_HOOK_V_DOTNET,
                "ScriptHookVDotNet",
                installed=all((root / name).is_file() for name in _SHVDN_FILES),
                action=EssentialAction.AUTO_INSTALL,
                detail=f"Pinned {_SHVDN_VERSION} from the official nightly releases.",
                homepage=(
                    "https://github.com/scripthookvdotnet/scripthookvdotnet-nightly/releases"
                ),
            ),
            self._item(
                by_id,
                constants.COMPONENT_NATIVE_UI,
                "NativeUI",
                installed=(root / "scripts" / "NativeUI.dll").is_file()
                or (root / "NativeUI.dll").is_file(),
                action=EssentialAction.AUTO_INSTALL,
                detail=f"Pinned Guad NativeUI {_NATIVEUI_VERSION} into scripts/.",
                homepage="https://github.com/Guad/NativeUI/releases/tag/1.9.1",
            ),
            self._item(
                by_id,
                constants.COMPONENT_PACKFILE_LIMIT_ADJUSTER,
                "Packfile Limit Adjuster",
                installed=(root / "PackfileLimitAdjuster.asi").is_file(),
                action=EssentialAction.OPEN_BROWSER,
                detail="Needed for large add-on / map packs — copy the .asi into the game root.",
            ),
            self._item(
                by_id,
                constants.COMPONENT_HEAP_ADJUSTER,
                "Heap Adjuster",
                installed=(root / "GTAVHeapAdjuster.asi").is_file()
                or (root / "HeapAdjuster.asi").is_file(),
                action=EssentialAction.OPEN_BROWSER,
                detail="Raises memory ceiling for big Story Mode collections.",
            ),
            self._item(
                by_id,
                constants.COMPONENT_GAMECONFIG,
                "Custom gameconfig.xml",
                installed=self._gameconfig_installed(game),
                action=EssentialAction.OPEN_BROWSER,
                detail=(
                    "Use a gameconfig matching your GTA build; install via OpenIV into "
                    "mods/update/update.rpf (common/data/gameconfig.xml)."
                ),
            ),
        )

        auto = tuple(
            item.display_name
            for item in items
            if not item.installed and item.action is EssentialAction.AUTO_INSTALL
        )
        browser = tuple(
            item.display_name
            for item in items
            if not item.installed and item.action is EssentialAction.OPEN_BROWSER
        )
        folder_missing = any(
            not item.installed and item.action is EssentialAction.CREATE_FOLDER
            for item in items
        )
        ready = all(item.installed for item in items)
        if ready:
            message = "All Story Mode essentials and stability tools are present."
        else:
            parts: list[str] = []
            if folder_missing:
                parts.append("create mods folder")
            if auto:
                parts.append("auto-install " + ", ".join(auto))
            if browser:
                parts.append("download manually " + ", ".join(browser))
            message = "Missing essentials / stability tools — " + "; ".join(parts) + "."
        return Result.ok(
            EssentialsStatus(
                items=items,
                ready=ready,
                message=message,
                auto_installable=auto,
                browser_needed=browser,
            )
        )

    def install_auto(self, install: GameInstall | None = None) -> Result[EssentialsStatus]:
        """Create mods folder and install pinned SHVDN + NativeUI when missing."""
        target = self._resolve(install)
        if target.is_error:
            return Result.fail(target.error or "No game", code=target.code)
        game = target.unwrap()
        root = game.root_path
        try:
            if not (root / constants.MODS_FOLDER_NAME).is_dir():
                self._game.ensure_mods_folder(game)
            if not all((root / name).is_file() for name in _SHVDN_FILES):
                self._install_shvdn(root)
            if not (
                (root / "scripts" / "NativeUI.dll").is_file()
                or (root / "NativeUI.dll").is_file()
            ):
                self._install_nativeui(root)
        except Exception as error:  # noqa: BLE001 - service boundary returns Result
            return Result.fail(str(error), code="essentials.install_failed")
        return self.status(game)

    def open_manual_pages(self, install: GameInstall | None = None) -> Result[EssentialsStatus]:
        """Open browser tabs for essentials / stability tools we cannot redistribute."""
        status = self.status(install)
        if status.is_error:
            return status
        current = status.unwrap()
        opened: set[str] = set()
        for item in current.items:
            if item.installed or item.action is not EssentialAction.OPEN_BROWSER:
                continue
            if not item.homepage or item.homepage in opened:
                continue
            webbrowser.open(item.homepage)
            opened.add(item.homepage)
        if not opened:
            return Result.ok(current)
        return Result(
            value=current,
            warnings=(f"Opened {len(opened)} download page(s) in your browser.",),
        )

    @staticmethod
    def _gameconfig_installed(game: GameInstall) -> bool:
        """Return whether a custom gameconfig is present under mods/."""
        loose = (
            game.mods_path
            / "update"
            / "update.rpf"
            / "common"
            / "data"
            / constants.GAMECONFIG_XML
        )
        if loose.is_file():
            return True
        # Also treat a library-tracked gameconfig install as present.
        tracked = game.mods_path / "update" / "common" / "data" / constants.GAMECONFIG_XML
        return tracked.is_file()

    def _install_shvdn(self, root: Path) -> None:
        archive = self._cached_archive(
            _SHVDN_ARCHIVE, _SHVDN_URL, _SHVDN_SHA256, "ScriptHookVDotNet"
        )
        workspace = self._paths.temp / "essentials-shvdn"
        try:
            if workspace.exists():
                shutil.rmtree(workspace)
            workspace.mkdir(parents=True)
            self._safe_extract(archive, workspace)
            for name in _SHVDN_FILES:
                source = self._find_member(workspace, name)
                if source is None:
                    raise OSError(f"SHVDN archive is missing {name}")
                shutil.copy2(source, root / name)
            ini = self._find_member(workspace, "ScriptHookVDotNet.ini")
            if ini is not None:
                shutil.copy2(ini, root / "ScriptHookVDotNet.ini")
        finally:
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)
        _LOGGER.info("Installed ScriptHookVDotNet %s into %s", _SHVDN_VERSION, root)

    def _install_nativeui(self, root: Path) -> None:
        archive = self._cached_archive(
            _NATIVEUI_ARCHIVE, _NATIVEUI_URL, _NATIVEUI_SHA256, "NativeUI"
        )
        workspace = self._paths.temp / "essentials-nativeui"
        try:
            if workspace.exists():
                shutil.rmtree(workspace)
            workspace.mkdir(parents=True)
            self._safe_extract(archive, workspace)
            dll = self._find_member(workspace, "NativeUI.dll")
            if dll is None:
                raise OSError("NativeUI archive is missing NativeUI.dll")
            scripts = root / "scripts"
            scripts.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dll, scripts / "NativeUI.dll")
            xml = self._find_member(workspace, "NativeUI.xml")
            if xml is not None:
                shutil.copy2(xml, scripts / "NativeUI.xml")
        finally:
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)
        _LOGGER.info("Installed NativeUI %s into %s/scripts", _NATIVEUI_VERSION, root)

    def _cached_archive(
        self, name: str, url: str, sha256: str, label: str
    ) -> Path:
        archive = self._paths.downloads / name
        if archive.is_file() and hashing.sha256_file(archive) == sha256:
            return archive
        archive.unlink(missing_ok=True)
        http_client.download_file(url, archive)
        actual = hashing.sha256_file(archive)
        if actual != sha256:
            archive.unlink(missing_ok=True)
            raise OSError(f"{label} download failed SHA-256 verification.")
        return archive

    @staticmethod
    def _safe_extract(archive: Path, destination: Path) -> None:
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                relative = PurePosixPath(member.filename)
                if relative.is_absolute() or ".." in relative.parts:
                    raise OSError(f"Unsafe path in archive: {member.filename}")
            bundle.extractall(destination)

    @staticmethod
    def _find_member(workspace: Path, name: str) -> Path | None:
        direct = workspace / name
        if direct.is_file():
            return direct
        matches = [path for path in workspace.rglob(name) if path.is_file()]
        return matches[0] if matches else None

    @staticmethod
    def _item(
        by_id: dict[str, DetectedComponent],
        component_id: str,
        fallback_name: str,
        *,
        installed: bool,
        action: EssentialAction,
        detail: str,
        homepage: str = "",
    ) -> EssentialItem:
        detected = by_id.get(component_id)
        display = detected.display_name if detected is not None else fallback_name
        home = homepage or (
            detected.spec.homepage if detected is not None else ""
        )
        return EssentialItem(
            component_id=component_id,
            display_name=display,
            installed=installed,
            action=EssentialAction.INSTALLED if installed else action,
            detail=detail,
            homepage=home,
        )

    def _resolve(self, install: GameInstall | None) -> Result[GameInstall]:
        if install is not None:
            return Result.ok(install)
        if self._game.active is not None:
            return Result.ok(self._game.active)
        return self._game.resolve_active()
