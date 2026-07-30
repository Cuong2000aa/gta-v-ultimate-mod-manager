"""JSON-backed index of backup snapshots and the operation audit trail."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.backup_snapshot import BackupSnapshot, OperationRecord
from gta_mod_manager.repository import codecs
from gta_mod_manager.repository.json_store import JsonStore

_LOGGER = get_logger("repository.backups")

_SCHEMA_VERSION = 1
_MAX_OPERATIONS = 500


class JsonBackupRepository:
    """Stores snapshot metadata and every mutating operation performed."""

    def __init__(self, store: JsonStore) -> None:
        self._store = store

    @classmethod
    def at(cls, path: Path) -> "JsonBackupRepository":
        """Build a repository backed by the document at ``path``."""
        return cls(
            JsonStore(
                path, default={"version": _SCHEMA_VERSION, "snapshots": {}, "operations": []}
            )
        )

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------
    def add_snapshot(self, snapshot: BackupSnapshot) -> None:
        """Insert or replace ``snapshot``."""

        def mutate(payload: dict[str, Any]) -> dict[str, Any]:
            snapshots = dict(payload.get("snapshots", {}))
            snapshots[snapshot.snapshot_id] = codecs.encode_snapshot(snapshot)
            payload["snapshots"] = snapshots
            payload["version"] = _SCHEMA_VERSION
            return payload

        self._store.update(mutate)
        _LOGGER.info(
            "Indexed snapshot %s (%d file(s))", snapshot.snapshot_id, snapshot.file_count
        )

    def remove_snapshot(self, snapshot_id: str) -> None:
        """Remove the index entry of ``snapshot_id``."""

        def mutate(payload: dict[str, Any]) -> dict[str, Any]:
            snapshots = dict(payload.get("snapshots", {}))
            snapshots.pop(snapshot_id, None)
            payload["snapshots"] = snapshots
            return payload

        self._store.update(mutate)

    def get_snapshot(self, snapshot_id: str) -> BackupSnapshot | None:
        """Return the snapshot identified by ``snapshot_id``, or ``None``."""
        payload = self._store.read().get("snapshots", {}).get(snapshot_id)
        return codecs.decode_snapshot(payload) if payload else None

    def list_snapshots(self) -> tuple[BackupSnapshot, ...]:
        """Return every snapshot, newest first."""
        snapshots = [
            codecs.decode_snapshot(item)
            for item in self._store.read().get("snapshots", {}).values()
        ]
        snapshots.sort(key=lambda item: item.created_at, reverse=True)
        return tuple(snapshots)

    def list_for_mod(self, mod_id: str) -> tuple[BackupSnapshot, ...]:
        """Return the version history of one mod, newest first."""
        return tuple(item for item in self.list_snapshots() if item.mod_id == mod_id)

    # ------------------------------------------------------------------
    # Operation audit trail
    # ------------------------------------------------------------------
    def add_operation(self, record: OperationRecord) -> None:
        """Append ``record``, replacing an earlier entry with the same id."""

        def mutate(payload: dict[str, Any]) -> dict[str, Any]:
            operations = [
                item
                for item in payload.get("operations", [])
                if item.get("operation_id") != record.operation_id
            ]
            operations.append(codecs.encode_operation(record))
            payload["operations"] = operations[-_MAX_OPERATIONS:]
            return payload

        self._store.update(mutate)

    def list_operations(self) -> tuple[OperationRecord, ...]:
        """Return the audit trail, newest first."""
        records = [
            codecs.decode_operation(item)
            for item in self._store.read().get("operations", [])
            if item.get("operation_id")
        ]
        records.sort(key=lambda item: item.started_at, reverse=True)
        return tuple(records)
