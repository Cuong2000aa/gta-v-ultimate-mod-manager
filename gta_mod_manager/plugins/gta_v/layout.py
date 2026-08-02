"""Recognises the folder layout a GTA V mod archive uses.

Mod authors package their work in half a dozen conventions. Detecting the
layout once, up front, lets the path mapper stay a simple lookup instead of a
pile of special cases.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath

from gta_mod_manager.core import constants
from gta_mod_manager.core.ped_assets import is_ped_asset, ped_model_stems
from gta_mod_manager.core.script_assets import script_assembly_paths
from gta_mod_manager.models.mod_file import FileInventory
from gta_mod_manager.models.variant_selection import VariantSelection
from gta_mod_manager.plugins.gta_v.replace_targets import (
    ReplaceTarget,
    discover_readme_replace_targets,
)
from gta_mod_manager.utils import fs

#: Path segments that mean "everything from here on mirrors the game folder".
GAME_ANCHOR_SEGMENTS: tuple[str, ...] = (
    constants.MODS_FOLDER_NAME,
    constants.UPDATE_FOLDER_NAME,
    "x64",
    "dlcpacks",
)

#: Folder names authors use for the add-on half of a dual-variant package.
ADDON_VARIANT_NAMES: frozenset[str] = frozenset(
    {"addon", "add-on", "add_on", "add on", "dlc"}
)

#: Folder names authors use for the replacement half (``repace`` is a
#: frequent typo in community packs).
REPLACE_VARIANT_NAMES: frozenset[str] = frozenset(
    {"replace", "replacement", "repace", "rep"}
)

#: Folder names for the GTA V Enhanced edition half of a dual-edition pack.
ENHANCED_EDITION_NAMES: frozenset[str] = frozenset(
    {"enhanced", "gta5enhanced", "gta enhanced"}
)

#: Folder names for the Legacy / classic edition half.
LEGACY_EDITION_NAMES: frozenset[str] = frozenset({"legacy", "classic"})


def path_under_named_folders(path: PurePosixPath, names: frozenset[str]) -> bool:
    """Return whether any parent folder of ``path`` matches ``names``."""
    return any(part.lower() in names for part in path.parts[:-1])


@dataclass(frozen=True, slots=True)
class DlcPackLayout:
    """One add-on DLC pack found inside the package.

    Attributes:
        pack_name: Folder name the pack must get inside ``dlcpacks``.
        root: Package-relative folder that is the root of the pack.
    """

    pack_name: str
    root: PurePosixPath

    def relative_within_pack(self, path: PurePosixPath) -> PurePosixPath | None:
        """Return ``path`` relative to the pack root, or ``None`` if outside."""
        pack_parts = self.root.parts
        if pack_parts and path.parts[: len(pack_parts)] != pack_parts:
            return None
        return PurePosixPath(*path.parts[len(pack_parts) :])


@dataclass(frozen=True, slots=True)
class PackageLayout:
    """The structural facts the path mapper needs.

    Attributes:
        dlc_packs: Add-on DLC packs shipped by the package.
        has_game_anchor: Whether any path mirrors the game folder structure.
        fallback_pack_name: Pack name used when a bare ``dlc.rpf`` is found.
        has_addon_variant: Whether an ``Add-On`` / ``Addon`` folder exists.
        has_replace_variant: Whether a ``Replace`` folder exists.
        has_enhanced_edition: Whether an ``Enhanced`` folder exists.
        has_legacy_edition: Whether a ``Legacy`` folder exists.
        selection: Which Add-On / Replace halves the user wants installed.
        ped_model_names: Character models the package ships (``.ydd`` owners).
        script_assemblies: Package-relative paths of ScriptHookVDotNet scripts.
    """

    dlc_packs: tuple[DlcPackLayout, ...] = field(default_factory=tuple)
    has_game_anchor: bool = False
    fallback_pack_name: str = "custom_pack"
    has_addon_variant: bool = False
    has_replace_variant: bool = False
    has_enhanced_edition: bool = False
    has_legacy_edition: bool = False
    selection: VariantSelection = field(
        default_factory=lambda: VariantSelection(addon=True, replace=True)
    )
    ped_model_names: frozenset[str] = field(default_factory=frozenset)
    script_assemblies: frozenset[PurePosixPath] = field(default_factory=frozenset)
    #: Filename / ``*`` → DLC replace home from ReadMe OpenIV paths.
    dlc_replace_hints: dict[str, ReplaceTarget] = field(default_factory=dict)

    @property
    def is_dual_variant(self) -> bool:
        """Return whether the package ships both Add-On and Replace halves."""
        return self.has_addon_variant and self.has_replace_variant

    @property
    def prefer_legacy_edition(self) -> bool:
        """Return whether Enhanced paths should be skipped in favour of Legacy."""
        return self.has_enhanced_edition and self.has_legacy_edition

    @property
    def prefer_replace(self) -> bool:
        """Return whether only the Replace half is selected on a dual package."""
        return (
            self.is_dual_variant
            and self.selection.replace
            and not self.selection.addon
        )

    @property
    def active_dlc_packs(self) -> tuple[DlcPackLayout, ...]:
        """Return the DLC packs that should still be installed."""
        if self.is_dual_variant and not self.selection.addon:
            return ()
        return tuple(
            pack
            for pack in self.dlc_packs
            if not self.is_skipped_edition_path(pack.root / "dlc.rpf")
        )

    def with_selection(self, selection: VariantSelection) -> PackageLayout:
        """Return a copy of this layout using ``selection``."""
        return replace(self, selection=selection)

    def is_ped_asset(self, path: PurePosixPath) -> bool:
        """Return whether ``path`` is part of a character model this pack ships.

        Ped meshes and textures share the ``.yft`` / ``.ytd`` extensions with
        vehicles, so they must be recognised before the vehicle importer claims
        them.
        """
        return is_ped_asset(path.name, self.ped_model_names)

    def is_skipped_edition_path(self, path: PurePosixPath) -> bool:
        """Return whether ``path`` belongs to the Enhanced half we are ignoring."""
        if not self.prefer_legacy_edition:
            return False
        return path_under_named_folders(path, ENHANCED_EDITION_NAMES)

    def is_skipped_addon_path(self, path: PurePosixPath) -> bool:
        """Return whether ``path`` belongs to an Add-On half we are ignoring."""
        if not self.is_dual_variant or self.selection.addon:
            return False
        return path_under_named_folders(path, ADDON_VARIANT_NAMES)

    def is_skipped_replace_path(self, path: PurePosixPath) -> bool:
        """Return whether ``path`` belongs to a Replace half we are ignoring."""
        if not self.is_dual_variant or self.selection.replace:
            return False
        return path_under_named_folders(path, REPLACE_VARIANT_NAMES)

    def is_skipped_variant_path(self, path: PurePosixPath) -> bool:
        """Return whether ``path`` is excluded by edition or Add-On/Replace choice."""
        return (
            self.is_skipped_edition_path(path)
            or self.is_skipped_addon_path(path)
            or self.is_skipped_replace_path(path)
        )

    def pack_for(self, path: PurePosixPath) -> DlcPackLayout | None:
        """Return the DLC pack ``path`` belongs to, if any."""
        if self.is_skipped_variant_path(path):
            return None
        best: DlcPackLayout | None = None
        for pack in self.active_dlc_packs:
            if pack.relative_within_pack(path) is None:
                continue
            if best is None or len(pack.root.parts) > len(best.root.parts):
                best = pack
        return best

    @classmethod
    def detect(
        cls,
        inventory: FileInventory,
        display_name: str,
        selection: VariantSelection | None = None,
    ) -> PackageLayout:
        """Infer the layout of ``inventory``."""
        anchors = {segment.lower() for segment in GAME_ANCHOR_SEGMENTS}
        has_anchor = any(
            part in anchors for item in inventory.files for part in item.parts_lower[:-1]
        )
        folder_names = {
            part for item in inventory.files for part in item.parts_lower[:-1]
        }
        has_addon = bool(folder_names & ADDON_VARIANT_NAMES)
        has_replace = bool(folder_names & REPLACE_VARIANT_NAMES)
        fallback = fs.sanitise_name(display_name, "custom_pack").replace(" ", "_").lower()
        chosen = selection or VariantSelection.for_package(
            has_addon=has_addon, has_replace=has_replace
        )
        return cls(
            dlc_packs=cls._detect_dlc_packs(inventory, fallback),
            has_game_anchor=has_anchor,
            fallback_pack_name=fallback,
            has_addon_variant=has_addon,
            has_replace_variant=has_replace,
            has_enhanced_edition=bool(folder_names & ENHANCED_EDITION_NAMES),
            has_legacy_edition=bool(folder_names & LEGACY_EDITION_NAMES),
            selection=chosen,
            ped_model_names=ped_model_stems(item.lower_name for item in inventory.files),
            script_assemblies=script_assembly_paths(
                (item.absolute_path, item.relative_path) for item in inventory.files
            ),
            dlc_replace_hints=discover_readme_replace_targets(inventory),
        )

    @staticmethod
    def _detect_dlc_packs(
        inventory: FileInventory, fallback_pack_name: str
    ) -> tuple[DlcPackLayout, ...]:
        """Return every add-on DLC pack root inside the package.

        A pack root is either the folder holding ``dlc.rpf`` or the folder
        holding both ``content.xml`` and ``setup2.xml``.
        """
        roots: dict[PurePosixPath, str] = {}

        for item in inventory.by_name("dlc.rpf"):
            root = item.relative_path.parent
            roots.setdefault(root, PackageLayout._pack_name(root, fallback_pack_name))

        content_dirs = {
            item.relative_path.parent for item in inventory.by_name(constants.CONTENT_XML)
        }
        setup_dirs = {
            item.relative_path.parent for item in inventory.by_name(constants.SETUP2_XML)
        }
        for root in content_dirs & setup_dirs:
            roots.setdefault(root, PackageLayout._pack_name(root, fallback_pack_name))

        return tuple(
            DlcPackLayout(pack_name=name, root=root) for root, name in sorted(roots.items())
        )

    @staticmethod
    def _pack_name(root: PurePosixPath, fallback: str) -> str:
        """Return the DLC pack folder name derived from ``root``."""
        name = root.name
        if not name or name in (".", "/"):
            return fallback
        if name.lower() in ("dlcpacks", constants.MODS_FOLDER_NAME, "x64"):
            return fallback
        return fs.sanitise_name(name, fallback).replace(" ", "_").lower()


def strip_to_game_anchor(path: PurePosixPath) -> PurePosixPath | None:
    """Return ``path`` rebased on the first game-structure anchor it contains.

    ``MyMod v2/mods/update/x64/dlcpacks/x/dlc.rpf`` becomes
    ``update/x64/dlcpacks/x/dlc.rpf``: the leading wrapper folders and the
    ``mods`` anchor itself are removed, because the installer already knows the
    destination is the ``mods`` folder.
    """
    parts = list(path.parts)
    lowered = [part.lower() for part in parts]

    if constants.MODS_FOLDER_NAME in lowered:
        index = lowered.index(constants.MODS_FOLDER_NAME)
        remainder = parts[index + 1 :]
        return PurePosixPath(*remainder) if remainder else None

    for anchor in (constants.UPDATE_FOLDER_NAME, "x64"):
        if anchor in lowered:
            index = lowered.index(anchor)
            return PurePosixPath(*parts[index:])

    if "dlcpacks" in lowered:
        index = lowered.index("dlcpacks")
        return PurePosixPath(constants.UPDATE_FOLDER_NAME, "x64", *parts[index:])

    return None
