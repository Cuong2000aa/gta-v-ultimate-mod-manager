"""Maps every packaged file onto a safe destination inside the installation.

This is where the safety rule becomes concrete. The mapper answers one
question per file: *may this be written, and where?* Answers are:

1. A path inside ``<game>/mods`` - always preferred.
2. A whitelisted path in the game root (``scripts/``, ``*.asi``, ENB, ...).
3. An automatic import into a *mods-folder copy* of an ``.rpf`` (vehicle
   stream assets such as ``.yft`` / ``.ytd``).
4. Nothing: the file belongs inside an original archive the manager cannot
   map, so the plan raises a manual OpenIV step instead.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from gta_mod_manager.core import constants
from gta_mod_manager.core.script_assets import SCRIPT_SIDECAR_SUFFIXES
from gta_mod_manager.models.enums import InstallTarget
from gta_mod_manager.plugins.contracts import TargetDecision
from gta_mod_manager.plugins.gta_v.layout import PackageLayout, strip_to_game_anchor
from gta_mod_manager.plugins.gta_v.replace_targets import resolve_replace_target
from gta_mod_manager.plugins.gta_v.root_policy import RootInstallPolicy

#: Files that carry no installable payload and are skipped silently.
_DOCUMENTATION_SUFFIXES = frozenset(constants.DOCUMENT_EXTENSIONS | constants.IMAGE_EXTENSIONS)

#: Root folders that keep their own name when installed (ReShade, ENB, Menyoo).
_SELF_CONTAINED_ROOT_DIRECTORIES = frozenset(
    {"reshade-shaders", "reshade-presets", "enbseries", "enbcache", "menyoostuff", "openivscripts"}
)

#: Assets that only exist inside ``.rpf`` archives in a stock installation.
_ARCHIVE_ONLY_SUFFIXES = frozenset(
    constants.GAME_ASSET_EXTENSIONS - {".rpf"} | {".meta", ".dat"}
)

#: Folder names that hold stock/backup copies and must never enter an install plan.
_BACKUP_FOLDER_NAMES = frozenset({"backup", "original", "stock"})


class GtaVPathMapper:
    """Decides the destination of each file in a GTA V mod package."""

    def __init__(self, policy: RootInstallPolicy | None = None) -> None:
        self._policy = policy or RootInstallPolicy()

    @property
    def policy(self) -> RootInstallPolicy:
        """Return the root-installation policy in use."""
        return self._policy

    def decide(self, layout: PackageLayout, relative_path: PurePosixPath) -> TargetDecision:
        """Return where ``relative_path`` may be installed.

        Args:
            layout: Structural facts detected for the whole package.
            relative_path: Package-relative path of one file.
        """
        for resolver in (
            self._as_documentation,
            self._as_backup_folder_skip,
            self._as_dlc_vehicle_replace,
            self._as_dlc_pack_member,
            self._as_game_structure,
            self._as_ped_armor_ini,
            self._as_script_assembly,
            self._as_root_install,
            self._as_ped_component_asset,
            self._as_vehicle_stream_import,
            self._as_archive_only_asset,
        ):
            decision = resolver(layout, relative_path)
            if decision is not None:
                return decision

        return TargetDecision(
            target=InstallTarget.MODS_FOLDER,
            relative_target=Path(*relative_path.parts),
            reason="Unrecognised file, installed inside the mods folder to stay safe",
        )

    # ------------------------------------------------------------------
    # Individual resolvers, tried in order
    # ------------------------------------------------------------------
    @staticmethod
    def _as_documentation(
        _layout: PackageLayout, relative_path: PurePosixPath
    ) -> TargetDecision | None:
        """Skip readmes and preview pictures."""
        if relative_path.suffix.lower() in _DOCUMENTATION_SUFFIXES:
            return TargetDecision(
                target=None, reason="Documentation or preview image, nothing to install"
            )
        return None

    @staticmethod
    def _as_backup_folder_skip(
        _layout: PackageLayout, relative_path: PurePosixPath
    ) -> TargetDecision | None:
        """Skip stream assets living under backup / original / stock folders.

        Hellcat-class packages often ship ``Backup/`` or ``__(Backup*)`` copies of
        stock ``.yft``/``.ytd`` next to ``Replace/``. Those must never be imported.
        """
        if relative_path.suffix.lower() not in constants.VEHICLE_STREAM_EXTENSIONS:
            return None
        if not path_looks_like_backup_folder(relative_path):
            return None
        return TargetDecision(
            target=None,
            reason=(
                f"Skipped {relative_path.name} from backup/original/stock folder "
                f"({relative_path.parent.as_posix() or '.'})"
            ),
        )

    @staticmethod
    def _as_dlc_vehicle_replace(
        layout: PackageLayout, relative_path: PurePosixPath
    ) -> TargetDecision | None:
        """Import DLC-home replaces into ``mods/update/x64/dlcpacks/<pack>/dlc.rpf``.

        Runs before ``_as_game_structure`` so paths like
        ``x64w.rpf/dlcpacks/mpbusiness/dlc.rpf/.../turismor.yft`` are not copied
        as loose files under ``mods/``.
        """
        if relative_path.suffix.lower() not in constants.VEHICLE_STREAM_EXTENSIONS:
            return None
        target = resolve_replace_target(
            relative_path, readme_targets=layout.dlc_replace_hints
        )
        if target is None:
            return None
        member = target.member_path(relative_path.name)
        return TargetDecision(
            target=InstallTarget.MODS_FOLDER,
            relative_target=target.relative_archive,
            archive_member_path=member,
            reason=(
                f"Replace {relative_path.name} inside the mods copy of "
                f"{target.relative_archive.as_posix()} ({target.nested_rpf}); "
                "original untouched"
            ),
        )

    @staticmethod
    def _as_dlc_pack_member(
        layout: PackageLayout, relative_path: PurePosixPath
    ) -> TargetDecision | None:
        """Route add-on DLC pack content into ``mods/update/x64/dlcpacks``."""
        pack = layout.pack_for(relative_path)
        if pack is None:
            return None
        within = pack.relative_within_pack(relative_path)
        if within is None:  # pragma: no cover - pack_for already checked this
            return None
        target = Path(
            *constants.DLC_PACKS_RELATIVE.split("/"), pack.pack_name, *within.parts
        )
        return TargetDecision(
            target=InstallTarget.DLC_PACKS,
            relative_target=target,
            reason=f"Add-on DLC pack '{pack.pack_name}' installs into dlcpacks",
        )

    @staticmethod
    def _as_game_structure(
        _layout: PackageLayout, relative_path: PurePosixPath
    ) -> TargetDecision | None:
        """Honour packages that already mirror the game folder structure."""
        rebased = strip_to_game_anchor(relative_path)
        if rebased is None:
            return None
        return TargetDecision(
            target=InstallTarget.MODS_FOLDER,
            relative_target=Path(*rebased.parts),
            reason="Package mirrors the game folder layout",
        )

    @staticmethod
    def _as_ped_armor_ini(
        layout: PackageLayout, relative_path: PurePosixPath
    ) -> TargetDecision | None:
        """Route Iron Man-style ``*_armor.ini`` next to JulioNIB's script files.

        These look like ordinary root ``.ini`` files, so without this check they
        land in the game root and the IronmanV script never finds them.
        """
        if not layout.ped_model_names:
            return None
        name = relative_path.name
        if not name.lower().endswith("_armor.ini"):
            return None
        target = Path(*constants.IRONMAN_ARMOR_RELATIVE.split("/")) / name
        return TargetDecision(
            target=InstallTarget.SCRIPTS_FOLDER,
            relative_target=target,
            reason=(
                f"{name} belongs with the IronmanV script under "
                f"{constants.IRONMAN_ARMOR_RELATIVE}/"
            ),
        )

    @staticmethod
    def _as_script_assembly(
        layout: PackageLayout, relative_path: PurePosixPath
    ) -> TargetDecision | None:
        """Route a loose ScriptHookVDotNet assembly into ``scripts/``.

        Script mods are routinely published as a bare ``.dll`` at the archive
        root. Such a file matches no whitelist, so it would otherwise land in
        ``mods`` and never be loaded. Debug symbols follow their assembly.
        """
        is_assembly = relative_path in layout.script_assemblies
        is_sidecar = (
            relative_path.suffix.lower() in SCRIPT_SIDECAR_SUFFIXES
            and relative_path.with_suffix(".dll") in layout.script_assemblies
        )
        if not is_assembly and not is_sidecar:
            return None
        if constants.SCRIPTS_FOLDER_NAME in (part.lower() for part in relative_path.parts[:-1]):
            return None
        reason = (
            f"{relative_path.name} is a ScriptHookVDotNet assembly and "
            f"belongs in {constants.SCRIPTS_FOLDER_NAME}/"
            if is_assembly
            else f"{relative_path.name} holds debug symbols for the script next to it"
        )
        return TargetDecision(
            target=InstallTarget.SCRIPTS_FOLDER,
            relative_target=Path(constants.SCRIPTS_FOLDER_NAME, relative_path.name),
            reason=reason,
        )

    def _as_root_install(
        self, _layout: PackageLayout, relative_path: PurePosixPath
    ) -> TargetDecision | None:
        """Apply the root whitelist to loose files and known root folders."""
        if self._policy.is_protected(relative_path):
            return TargetDecision(
                target=None,
                reason=f"{relative_path.name} is an original game file and is never modified",
                needs_archive_editor=relative_path.suffix.lower()
                == constants.PROTECTED_ARCHIVE_SUFFIX,
            )

        anchored = self._rebase_on_root_directory(relative_path)
        if anchored is not None:
            verdict = self._policy.evaluate(anchored)
            if verdict.allowed and verdict.target is not None:
                return TargetDecision(
                    target=verdict.target,
                    relative_target=Path(*anchored.parts),
                    reason=verdict.reason,
                )

        if self._policy.allows_file(relative_path.name):
            return TargetDecision(
                target=InstallTarget.GAME_ROOT,
                relative_target=Path(relative_path.name),
                reason=f"{relative_path.name} matches the root install whitelist",
            )
        return None

    @staticmethod
    def _as_ped_component_asset(
        layout: PackageLayout, relative_path: PurePosixPath
    ) -> TargetDecision | None:
        """Keep character models out of the vehicle archive.

        A ped ships ``.yft`` and ``.ytd`` files just like a car, so without this
        check an Iron Man suit would be imported into ``vehicles.rpf`` and break
        the vehicle stream.
        """
        if not layout.is_ped_asset(relative_path):
            return None
        return TargetDecision(
            target=None,
            reason=(
                f"{relative_path.name} is a character (ped) asset, not a vehicle; "
                "it must be imported into the archive holding the original model"
            ),
            needs_archive_editor=True,
        )

    @staticmethod
    def _as_vehicle_stream_import(
        _layout: PackageLayout, relative_path: PurePosixPath
    ) -> TargetDecision | None:
        """Auto-import vehicle mesh/texture assets into mods/x64e.rpf."""
        suffix = relative_path.suffix.lower()
        if suffix not in constants.VEHICLE_STREAM_EXTENSIONS:
            return None
        member = f"{constants.VEHICLE_STREAM_NESTED_RPF}/{relative_path.name}"
        return TargetDecision(
            target=InstallTarget.MODS_FOLDER,
            relative_target=Path(constants.VEHICLE_STREAM_ARCHIVE),
            archive_member_path=member,
            reason=(
                f"Replace {relative_path.name} inside the mods copy of "
                f"{constants.VEHICLE_STREAM_ARCHIVE} "
                f"({constants.VEHICLE_STREAM_NESTED_RPF}); original untouched"
            ),
        )

    @staticmethod
    def _as_archive_only_asset(
        _layout: PackageLayout, relative_path: PurePosixPath
    ) -> TargetDecision | None:
        """Refuse assets whose real home is inside an original ``.rpf``."""
        if relative_path.suffix.lower() not in _ARCHIVE_ONLY_SUFFIXES:
            return None
        return TargetDecision(
            target=None,
            reason=f"{relative_path.name} belongs inside a game archive; "
            "the manager will not edit original .rpf files",
            needs_archive_editor=True,
        )

    @staticmethod
    def _rebase_on_root_directory(relative_path: PurePosixPath) -> PurePosixPath | None:
        """Rebase a path on the whitelisted root folder it contains.

        ``Cool Script v3/scripts/foo.dll`` becomes ``scripts/foo.dll``.
        """
        lowered = [part.lower() for part in relative_path.parts[:-1]]
        wanted = set(constants.ALLOWED_ROOT_DIRECTORIES) | _SELF_CONTAINED_ROOT_DIRECTORIES
        for index, part in enumerate(lowered):
            if part in wanted:
                return PurePosixPath(*relative_path.parts[index:])
        return None


def path_looks_like_backup_folder(relative_path: PurePosixPath) -> bool:
    """Return whether any parent folder looks like a stock/backup copy tree.

    Matches ``backup``, ``original``, ``stock``, and names such as
    ``__(Backup)`` / ``__(Backup_gauntlet)``.
    """
    for part in relative_path.parts[:-1]:
        lower = part.lower()
        if lower in _BACKUP_FOLDER_NAMES:
            return True
        if "backup" in lower and (
            lower.startswith("__") or lower.startswith("(") or lower.startswith("backup")
        ):
            return True
    return False
