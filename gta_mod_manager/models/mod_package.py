"""Aggregate describing a mod the user wants to install."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from gta_mod_manager.models.classification import ModClassification
from gta_mod_manager.models.enums import ModStatus
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.models.vehicle import VehicleDefinition, VehicleManifest


@dataclass(frozen=True, slots=True)
class DependencyRef:
    """A component or mod that must be present for this package to work."""

    component_id: str
    display_name: str
    optional: bool = False
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ReadmeExcerpt:
    """A snippet of documentation shipped with the package."""

    source: Path
    text: str


@dataclass(frozen=True, slots=True)
class ModPackage:
    """An analyzed, not yet installed mod.

    Attributes:
        package_id: Stable identifier derived from the source archive.
        display_name: Name shown in the UI.
        source_path: Original archive or folder the user supplied.
        extracted_root: Temporary folder holding the extracted content.
        inventory: Every file found under :attr:`extracted_root`.
        classification: Verdict of the analyzer.
        vehicles: Vehicle metadata when the package contains vehicles.
        dependencies: Components required for the mod to work.
        readmes: Documentation excerpts surfaced in the preview dialog.
        preview_image: Best picture found inside the package.
    """

    package_id: str
    display_name: str
    source_path: Path
    extracted_root: Path
    inventory: FileInventory
    classification: ModClassification = field(default_factory=ModClassification.unknown)
    vehicles: VehicleManifest = field(default_factory=VehicleManifest)
    dependencies: tuple[DependencyRef, ...] = field(default_factory=tuple)
    readmes: tuple[ReadmeExcerpt, ...] = field(default_factory=tuple)
    preview_image: Path | None = None
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def files(self) -> tuple[ModFile, ...]:
        """Return the package files."""
        return self.inventory.files

    @property
    def total_size(self) -> int:
        """Return the total size of the package content in bytes."""
        return self.inventory.total_size

    @property
    def required_dependencies(self) -> tuple[DependencyRef, ...]:
        """Return only the mandatory dependencies."""
        return tuple(item for item in self.dependencies if not item.optional)


@dataclass(frozen=True, slots=True)
class CachedArchiveMember:
    """Payload cached under the app library so enable can re-import RPF members."""

    member_path: str
    library_relative: str


@dataclass(frozen=True, slots=True)
class InstalledFileRecord:
    """One file written by an installation, used for exact uninstallation.

    Attributes:
        target_path: Absolute path written on disk.
        sha256: Content hash at install time.
        replaced_existing: Whether a previous file was overwritten.
        shared_archive: When ``True``, the path is a shared mods-folder
            ``.rpf`` that other mods may also own. Uninstall restores it from
            the install-time backup when this mod is the sole owner; otherwise
            it is left in place.
        archive_members: Member paths imported into a shared archive.
        member_payloads: Cached source bytes for re-enable after a physical disable.
    """

    target_path: Path
    sha256: str | None = None
    replaced_existing: bool = False
    shared_archive: bool = False
    archive_members: tuple[str, ...] = ()
    member_payloads: tuple[CachedArchiveMember, ...] = ()


@dataclass(frozen=True, slots=True)
class InstalledMod:
    """A mod currently tracked by the library.

    Attributes:
        mod_id: Stable identifier, matching :attr:`ModPackage.package_id`.
        installed_files: Everything written by the installation.
        backup_id: Snapshot taken right before the installation.
        game_root: Installation the mod belongs to.
    """

    mod_id: str
    display_name: str
    game_root: Path
    kind: str
    version: str = "1.0.0"
    status: ModStatus = ModStatus.INSTALLED
    installed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    installed_files: tuple[InstalledFileRecord, ...] = field(default_factory=tuple)
    created_directories: tuple[Path, ...] = field(default_factory=tuple)
    backup_id: str | None = None
    source_archive: Path | None = None
    preview_image: Path | None = None
    spawn_codes: tuple[str, ...] = field(default_factory=tuple)
    dlc_packs: tuple[str, ...] = field(default_factory=tuple)
    vehicle_definitions: tuple[VehicleDefinition, ...] = field(default_factory=tuple)
    notes: str = ""

    @property
    def file_count(self) -> int:
        """Return the number of files this mod owns."""
        return len(self.installed_files)

    def with_status(self, status: ModStatus) -> "InstalledMod":
        """Return a copy of this record carrying a new status."""
        return InstalledMod(
            mod_id=self.mod_id,
            display_name=self.display_name,
            game_root=self.game_root,
            kind=self.kind,
            version=self.version,
            status=status,
            installed_at=self.installed_at,
            installed_files=self.installed_files,
            created_directories=self.created_directories,
            backup_id=self.backup_id,
            source_archive=self.source_archive,
            preview_image=self.preview_image,
            spawn_codes=self.spawn_codes,
            dlc_packs=self.dlc_packs,
            vehicle_definitions=self.vehicle_definitions,
            notes=self.notes,
        )
