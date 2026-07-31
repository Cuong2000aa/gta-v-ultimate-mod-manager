"""Install and manage the pinned Simple Zombies Reborn game mode."""

from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.result import Result
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.zombie import ZombieModeStatus
from gta_mod_manager.net import http_client
from gta_mod_manager.services.game_service import GameService
from gta_mod_manager.utils import hashing

_LOGGER = get_logger("services.zombie_mode")

_VERSION = "1.0.5f"
_ARCHIVE_NAME = f"SimpleZombiesReborn-{_VERSION}.zip"
_ARCHIVE_URL = (
    "https://files.gta5-mods.com/uploads/simple-zombies-reborn-v1-0-5b/"
    "b40783-ZombiesMod%20Reborn%20%281.0.5f%29.zip"
)
_ARCHIVE_SHA256 = "dae0ecce4a98fa7bf87d6882211af5454054d0ee2892a6b016c7330b14902079"
_OWNED_FILES = (
    "SimpleZombiesReborn.dll",
    "SimpleZombiesReborn.pdb",
    "SimpleZombiesReborn.PhoneBridge.dll",
    "SimpleZombiesReborn.PhoneBridge.pdb",
    "SimpleZombiesReborn.ini",
)
_OWNED_DIR = "SimpleZombiesReborn"
_REQUIRED_DEPENDENCIES = {
    "ScriptHookV": ("ScriptHookV.dll", "dinput8.dll"),
    "ScriptHookVDotNet v2": ("ScriptHookVDotNet.asi", "ScriptHookVDotNet2.dll"),
    "NativeUI": ("scripts/NativeUI.dll",),
}


class ZombieModeService:
    """Manage a verified, reversible Simple Zombies Reborn installation."""

    def __init__(self, game: GameService, paths: AppPaths) -> None:
        self._game = game
        self._paths = paths

    def status(self, install: GameInstall | None = None) -> Result[ZombieModeStatus]:
        """Return install readiness and missing dependencies."""
        target = self._resolve(install)
        if target.is_error:
            return Result.fail(target.error or "No game", code=target.code)
        root = target.unwrap().root_path
        scripts = root / "scripts"
        installed = (scripts / "SimpleZombiesReborn.dll").is_file() and (
            scripts / _OWNED_DIR
        ).is_dir()
        missing = tuple(
            label
            for label, members in _REQUIRED_DEPENDENCIES.items()
            if not all((root / member).is_file() for member in members)
        )
        phone_support = (scripts / "iFruitAddon2.dll").is_file()
        ready = installed and not missing
        if ready:
            message = (
                f"Simple Zombies Reborn {_VERSION} sẵn sàng. Vào game nhấn F10, "
                "bật Infection Mode; nhấn I mở túi đồ."
            )
        elif installed:
            message = "Đã cài mod nhưng còn thiếu: " + ", ".join(missing)
        else:
            message = "Chưa cài Simple Zombies Reborn."
        return Result.ok(
            ZombieModeStatus(
                installed=installed,
                ready=ready,
                version=_VERSION if installed else None,
                missing_dependencies=missing,
                phone_support=phone_support,
                message=message,
            )
        )

    def install(self, install: GameInstall | None = None) -> Result[ZombieModeStatus]:
        """Download, verify, back up and install the pinned release."""
        target = self._resolve(install)
        if target.is_error:
            return Result.fail(target.error or "No game", code=target.code)
        root = target.unwrap().root_path
        scripts = root / "scripts"
        workspace = self._paths.temp / "simple-zombies-reborn"
        try:
            archive = self._archive()
            if workspace.exists():
                shutil.rmtree(workspace)
            workspace.mkdir(parents=True)
            self._safe_extract(archive, workspace)
            self._validate_payload(workspace)
            scripts.mkdir(parents=True, exist_ok=True)
            self._backup_existing(scripts)
            for name in _OWNED_FILES:
                shutil.copy2(workspace / name, scripts / name)
            destination = scripts / _OWNED_DIR
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(workspace / _OWNED_DIR, destination)
        except Exception as error:  # noqa: BLE001 - service boundary returns Result
            return Result.fail(str(error), code="zombie.install_failed")
        finally:
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)
        _LOGGER.info("Installed Simple Zombies Reborn %s at %s", _VERSION, scripts)
        return self.status(target.unwrap())

    def uninstall(self, install: GameInstall | None = None) -> Result[ZombieModeStatus]:
        """Back up saves and remove only files owned by this game mode."""
        target = self._resolve(install)
        if target.is_error:
            return Result.fail(target.error or "No game", code=target.code)
        scripts = target.unwrap().root_path / "scripts"
        if not (scripts / "SimpleZombiesReborn.dll").is_file():
            return Result.fail(
                "Simple Zombies Reborn chưa được cài.",
                code="zombie.not_installed",
            )
        try:
            self._backup_existing(scripts)
            for name in _OWNED_FILES:
                (scripts / name).unlink(missing_ok=True)
            owned_dir = scripts / _OWNED_DIR
            if owned_dir.is_dir():
                shutil.rmtree(owned_dir)
        except OSError as error:
            return Result.fail(str(error), code="zombie.uninstall_failed")
        _LOGGER.info("Uninstalled Simple Zombies Reborn from %s", scripts)
        return self.status(target.unwrap())

    def _archive(self) -> Path:
        archive = self._paths.downloads / _ARCHIVE_NAME
        if archive.is_file() and hashing.sha256_file(archive) == _ARCHIVE_SHA256:
            return archive
        archive.unlink(missing_ok=True)
        http_client.download_file(_ARCHIVE_URL, archive)
        actual = hashing.sha256_file(archive)
        if actual != _ARCHIVE_SHA256:
            archive.unlink(missing_ok=True)
            raise OSError("Gói zombie tải về không vượt qua kiểm tra SHA-256.")
        return archive

    @staticmethod
    def _safe_extract(archive: Path, destination: Path) -> None:
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                relative = PurePosixPath(member.filename)
                if relative.is_absolute() or ".." in relative.parts:
                    raise OSError(f"Đường dẫn không an toàn trong gói: {member.filename}")
            bundle.extractall(destination)

    @staticmethod
    def _validate_payload(workspace: Path) -> None:
        expected = (*_OWNED_FILES, f"{_OWNED_DIR}/builtin-languages.xml")
        missing = [name for name in expected if not (workspace / name).is_file()]
        if missing:
            raise OSError("Gói zombie thiếu file: " + ", ".join(missing))

    def _backup_existing(self, scripts: Path) -> None:
        candidates = tuple(
            path
            for path in (
                *(scripts / name for name in _OWNED_FILES),
                scripts / _OWNED_DIR,
            )
            if path.exists()
        )
        if not candidates:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = self._paths.backup / "zombie-mode" / stamp
        backup.mkdir(parents=True, exist_ok=True)
        for source in candidates:
            destination = backup / source.name
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)

    def _resolve(self, install: GameInstall | None) -> Result[GameInstall]:
        if install is not None:
            return Result.ok(install)
        if self._game.active is not None:
            return Result.ok(self._game.active)
        return self._game.resolve_active()
