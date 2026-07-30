"""Model for backup snapshots and the operation audit trail."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from gta_mod_manager.models.enums import OperationKind, OperationStatus


@dataclass(frozen=True, slots=True)
class BackupEntry:
    """One file preserved inside a snapshot.

    Attributes:
        original_path: Where the file lived inside the game installation.
        stored_path: Where the copy lives inside the backup store.
        sha256: Hash of the original content.
        existed: ``False`` when the plan creates a brand new file; restoring
            such an entry means deleting the file again.
    """

    original_path: Path
    stored_path: Path | None
    sha256: str | None = None
    existed: bool = True
    size_bytes: int = 0


@dataclass(frozen=True, slots=True)
class BackupSnapshot:
    """A restorable point-in-time copy of the files an operation touches."""

    snapshot_id: str
    game_root: Path
    reason: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    entries: tuple[BackupEntry, ...] = field(default_factory=tuple)
    mod_id: str | None = None
    operation_id: str | None = None
    label: str = ""

    @property
    def file_count(self) -> int:
        """Return the number of preserved files."""
        return len(self.entries)

    @property
    def total_size(self) -> int:
        """Return the total size of the preserved data in bytes."""
        return sum(entry.size_bytes for entry in self.entries)

    @property
    def display_label(self) -> str:
        """Return the label shown in the backup list."""
        return self.label or f"{self.reason} - {self.created_at:%Y-%m-%d %H:%M:%S}"


@dataclass(frozen=True, slots=True)
class OperationRecord:
    """Audit entry describing one mutating operation."""

    operation_id: str
    kind: OperationKind
    status: OperationStatus
    description: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    mod_id: str | None = None
    snapshot_id: str | None = None
    error: str | None = None

    @property
    def duration_seconds(self) -> float:
        """Return how long the operation took, or ``0.0`` when still running."""
        if self.finished_at is None:
            return 0.0
        return (self.finished_at - self.started_at).total_seconds()

    def completed(self, status: OperationStatus, error: str | None = None) -> "OperationRecord":
        """Return a finished copy of this record."""
        return OperationRecord(
            operation_id=self.operation_id,
            kind=self.kind,
            status=status,
            description=self.description,
            started_at=self.started_at,
            finished_at=datetime.now(timezone.utc),
            mod_id=self.mod_id,
            snapshot_id=self.snapshot_id,
            error=error,
        )
