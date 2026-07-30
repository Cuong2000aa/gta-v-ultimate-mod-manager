"""Ports (interfaces) that the application layer depends on.

Concrete adapters live in the infrastructure packages (``scanner``,
``detector``, ``installer``, ``backup``, ``repository``). Services only ever
see these protocols, which is what makes them unit-testable with fakes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable

from gta_mod_manager.models.backup_snapshot import BackupSnapshot, OperationRecord
from gta_mod_manager.models.classification import ModClassification
from gta_mod_manager.models.component import ComponentReport
from gta_mod_manager.models.conflict import ConflictReport
from gta_mod_manager.models.game_install import GameInstall, ValidationReport
from gta_mod_manager.models.install_plan import InstallPlan
from gta_mod_manager.models.mod_file import FileInventory
from gta_mod_manager.models.mod_package import InstalledMod, ModPackage
from gta_mod_manager.models.settings import AppSettings


@runtime_checkable
class ProgressReporter(Protocol):
    """Receives progress updates from long running operations."""

    def start(self, operation_id: str, label: str, total: int = 0) -> None:
        """Announce the beginning of an operation."""

    def advance(self, operation_id: str, current: int, label: str | None = None) -> None:
        """Report intermediate progress."""

    def finish(self, operation_id: str, label: str | None = None) -> None:
        """Announce that the operation completed."""


@runtime_checkable
class ArchiveExtractor(Protocol):
    """Extracts one archive format into a destination folder."""

    @property
    def supported_suffixes(self) -> frozenset[str]:
        """Return the lowercase extensions this extractor handles."""

    def can_handle(self, archive: Path) -> bool:
        """Return whether this extractor can open ``archive``."""

    def extract(self, archive: Path, destination: Path) -> None:
        """Extract ``archive`` into ``destination``."""


@runtime_checkable
class PackageScanner(Protocol):
    """Turns a user supplied file or folder into a file inventory."""

    def scan(self, source: Path, workspace: Path) -> FileInventory:
        """Extract (if needed) and inventory the content of ``source``."""


@runtime_checkable
class GameDetectorPort(Protocol):
    """Finds game installations on the machine."""

    def detect_all(self) -> tuple[GameInstall, ...]:
        """Return every installation that could be located."""

    def validate(self, root: Path) -> ValidationReport:
        """Check whether ``root`` is a usable installation."""

    def from_path(self, root: Path) -> GameInstall:
        """Build an installation entity from a manually chosen folder."""


@runtime_checkable
class ComponentDetectorPort(Protocol):
    """Detects third-party components inside an installation."""

    def detect(self, install: GameInstall) -> ComponentReport:
        """Return the state of every known component."""


@runtime_checkable
class ModAnalyzerPort(Protocol):
    """Classifies an extracted package."""

    def analyze(self, inventory: FileInventory) -> ModClassification:
        """Return the classification verdict for ``inventory``."""


@runtime_checkable
class ConflictDetectorPort(Protocol):
    """Compares a plan with the current game state."""

    def detect(
        self, plan: InstallPlan, install: GameInstall, installed: Iterable[InstalledMod]
    ) -> ConflictReport:
        """Return every conflict the plan would cause."""


@runtime_checkable
class InstallEnginePort(Protocol):
    """Applies and reverts install plans."""

    def apply(self, plan: InstallPlan, reporter: ProgressReporter | None = None) -> InstalledMod:
        """Execute ``plan`` transactionally and return the tracking record."""


@runtime_checkable
class BackupEnginePort(Protocol):
    """Creates and restores snapshots."""

    def create(
        self, game_root: Path, paths: Iterable[Path], reason: str, mod_id: str | None = None
    ) -> BackupSnapshot:
        """Copy ``paths`` into a new snapshot."""

    def restore(self, snapshot: BackupSnapshot) -> None:
        """Put every file of ``snapshot`` back where it came from."""

    def delete(self, snapshot: BackupSnapshot) -> None:
        """Remove the stored data of ``snapshot``."""


@runtime_checkable
class ModRepositoryPort(Protocol):
    """Persistence for installed mods."""

    def add(self, mod: InstalledMod) -> None:
        """Insert or replace ``mod``."""

    def remove(self, mod_id: str) -> None:
        """Delete the record identified by ``mod_id``."""

    def get(self, mod_id: str) -> InstalledMod | None:
        """Return the record identified by ``mod_id``, if any."""

    def list_all(self) -> tuple[InstalledMod, ...]:
        """Return every tracked mod."""


@runtime_checkable
class BackupRepositoryPort(Protocol):
    """Persistence for snapshots and the operation audit trail."""

    def add_snapshot(self, snapshot: BackupSnapshot) -> None:
        """Insert or replace ``snapshot``."""

    def remove_snapshot(self, snapshot_id: str) -> None:
        """Delete the snapshot index entry."""

    def get_snapshot(self, snapshot_id: str) -> BackupSnapshot | None:
        """Return the snapshot identified by ``snapshot_id``, if any."""

    def list_snapshots(self) -> tuple[BackupSnapshot, ...]:
        """Return every snapshot, newest first."""

    def add_operation(self, record: OperationRecord) -> None:
        """Append or update an audit entry."""

    def list_operations(self) -> tuple[OperationRecord, ...]:
        """Return the audit trail, newest first."""


@runtime_checkable
class SettingsRepositoryPort(Protocol):
    """Persistence for user preferences."""

    def load(self) -> AppSettings:
        """Return the stored settings, or defaults when absent."""

    def save(self, settings: AppSettings) -> None:
        """Persist ``settings``."""
