"""Conversion between domain entities and their JSON representation.

Serialisation lives in the repository layer on purpose: the domain model stays
free of persistence concerns, and the on-disk format can change without
touching a single entity.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gta_mod_manager.models.backup_snapshot import BackupEntry, BackupSnapshot, OperationRecord
from gta_mod_manager.models.enums import ModStatus, OperationKind, OperationStatus
from gta_mod_manager.models.mod_package import InstalledFileRecord, InstalledMod
from gta_mod_manager.models.vehicle import VehicleDefinition
from gta_mod_manager.models.settings import AppSettings


def encode_path(value: Path | None) -> str | None:
    """Return ``value`` as a string, or ``None``."""
    return str(value) if value is not None else None


def decode_path(value: Any) -> Path | None:
    """Return ``value`` as a :class:`~pathlib.Path`, or ``None``."""
    return Path(str(value)) if value else None


def encode_datetime(value: datetime | None) -> str | None:
    """Return ``value`` as an ISO-8601 string, or ``None``."""
    return value.isoformat() if value is not None else None


def decode_datetime(value: Any) -> datetime:
    """Return ``value`` parsed as a datetime, defaulting to now (UTC)."""
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# InstalledMod
# --------------------------------------------------------------------------
def encode_installed_mod(mod: InstalledMod) -> dict[str, Any]:
    """Return the JSON representation of ``mod``."""
    return {
        "mod_id": mod.mod_id,
        "display_name": mod.display_name,
        "game_root": encode_path(mod.game_root),
        "kind": mod.kind,
        "version": mod.version,
        "status": mod.status.value,
        "installed_at": encode_datetime(mod.installed_at),
        "installed_files": [
            {
                "target_path": encode_path(record.target_path),
                "sha256": record.sha256,
                "replaced_existing": record.replaced_existing,
                "shared_archive": record.shared_archive,
                "archive_members": list(record.archive_members),
            }
            for record in mod.installed_files
        ],
        "created_directories": [encode_path(item) for item in mod.created_directories],
        "backup_id": mod.backup_id,
        "source_archive": encode_path(mod.source_archive),
        "preview_image": encode_path(mod.preview_image),
        "spawn_codes": list(mod.spawn_codes),
        "dlc_packs": list(mod.dlc_packs),
        "vehicle_definitions": [
            {
                "model_name": vehicle.model_name,
                "handling_id": vehicle.handling_id,
                "txd_name": vehicle.txd_name,
                "manufacturer": vehicle.manufacturer,
                "vehicle_class": vehicle.vehicle_class,
            }
            for vehicle in mod.vehicle_definitions
        ],
        "notes": mod.notes,
    }


def decode_installed_mod(payload: dict[str, Any]) -> InstalledMod:
    """Return the :class:`InstalledMod` described by ``payload``."""
    files = tuple(
        InstalledFileRecord(
            target_path=Path(str(item.get("target_path"))),
            sha256=item.get("sha256"),
            replaced_existing=bool(item.get("replaced_existing", False)),
            shared_archive=bool(item.get("shared_archive", False)),
            archive_members=tuple(
                str(member) for member in item.get("archive_members", []) if member
            ),
        )
        for item in payload.get("installed_files", [])
        if item.get("target_path")
    )
    return InstalledMod(
        mod_id=str(payload["mod_id"]),
        display_name=str(payload.get("display_name", payload["mod_id"])),
        game_root=Path(str(payload.get("game_root", "."))),
        kind=str(payload.get("kind", "unknown")),
        version=str(payload.get("version", "1.0.0")),
        status=_decode_enum(ModStatus, payload.get("status"), ModStatus.INSTALLED),
        installed_at=decode_datetime(payload.get("installed_at")),
        installed_files=files,
        created_directories=tuple(
            Path(str(item)) for item in payload.get("created_directories", []) if item
        ),
        backup_id=payload.get("backup_id"),
        source_archive=decode_path(payload.get("source_archive")),
        preview_image=decode_path(payload.get("preview_image")),
        spawn_codes=tuple(str(item) for item in payload.get("spawn_codes", [])),
        dlc_packs=tuple(str(item) for item in payload.get("dlc_packs", [])),
        vehicle_definitions=tuple(
            VehicleDefinition(
                model_name=str(item.get("model_name", "")),
                handling_id=item.get("handling_id"),
                txd_name=item.get("txd_name"),
                manufacturer=item.get("manufacturer"),
                vehicle_class=item.get("vehicle_class"),
            )
            for item in payload.get("vehicle_definitions", [])
            if item.get("model_name")
        ),
        notes=str(payload.get("notes", "")),
    )


# --------------------------------------------------------------------------
# BackupSnapshot
# --------------------------------------------------------------------------
def encode_snapshot(snapshot: BackupSnapshot) -> dict[str, Any]:
    """Return the JSON representation of ``snapshot``."""
    return {
        "snapshot_id": snapshot.snapshot_id,
        "game_root": encode_path(snapshot.game_root),
        "reason": snapshot.reason,
        "created_at": encode_datetime(snapshot.created_at),
        "mod_id": snapshot.mod_id,
        "operation_id": snapshot.operation_id,
        "label": snapshot.label,
        "entries": [
            {
                "original_path": encode_path(entry.original_path),
                "stored_path": encode_path(entry.stored_path),
                "sha256": entry.sha256,
                "existed": entry.existed,
                "size_bytes": entry.size_bytes,
            }
            for entry in snapshot.entries
        ],
    }


def decode_snapshot(payload: dict[str, Any]) -> BackupSnapshot:
    """Return the :class:`BackupSnapshot` described by ``payload``."""
    entries = tuple(
        BackupEntry(
            original_path=Path(str(item.get("original_path"))),
            stored_path=decode_path(item.get("stored_path")),
            sha256=item.get("sha256"),
            existed=bool(item.get("existed", True)),
            size_bytes=int(item.get("size_bytes", 0) or 0),
        )
        for item in payload.get("entries", [])
        if item.get("original_path")
    )
    return BackupSnapshot(
        snapshot_id=str(payload["snapshot_id"]),
        game_root=Path(str(payload.get("game_root", "."))),
        reason=str(payload.get("reason", "")),
        created_at=decode_datetime(payload.get("created_at")),
        entries=entries,
        mod_id=payload.get("mod_id"),
        operation_id=payload.get("operation_id"),
        label=str(payload.get("label", "")),
    )


# --------------------------------------------------------------------------
# OperationRecord
# --------------------------------------------------------------------------
def encode_operation(record: OperationRecord) -> dict[str, Any]:
    """Return the JSON representation of ``record``."""
    return {
        "operation_id": record.operation_id,
        "kind": record.kind.value,
        "status": record.status.value,
        "description": record.description,
        "started_at": encode_datetime(record.started_at),
        "finished_at": encode_datetime(record.finished_at),
        "mod_id": record.mod_id,
        "snapshot_id": record.snapshot_id,
        "error": record.error,
    }


def decode_operation(payload: dict[str, Any]) -> OperationRecord:
    """Return the :class:`OperationRecord` described by ``payload``."""
    finished = payload.get("finished_at")
    return OperationRecord(
        operation_id=str(payload["operation_id"]),
        kind=_decode_enum(OperationKind, payload.get("kind"), OperationKind.INSTALL),
        status=_decode_enum(OperationStatus, payload.get("status"), OperationStatus.PENDING),
        description=str(payload.get("description", "")),
        started_at=decode_datetime(payload.get("started_at")),
        finished_at=decode_datetime(finished) if finished else None,
        mod_id=payload.get("mod_id"),
        snapshot_id=payload.get("snapshot_id"),
        error=payload.get("error"),
    )


# --------------------------------------------------------------------------
# AppSettings
# --------------------------------------------------------------------------
def encode_settings(settings: AppSettings) -> dict[str, Any]:
    """Return the JSON representation of ``settings``."""
    return {
        "game_root": encode_path(settings.game_root),
        "auto_backup": settings.auto_backup,
        "confirm_root_installs": settings.confirm_root_installs,
        "keep_extracted_temp": settings.keep_extracted_temp,
        "max_backup_generations": settings.max_backup_generations,
        "theme": settings.theme,
        "language": settings.language,
        "crash_monitor_enabled": settings.crash_monitor_enabled,
        "seven_zip_path": encode_path(settings.seven_zip_path),
        "unrar_path": encode_path(settings.unrar_path),
        "nexus_api_key": settings.nexus_api_key,
        "recent_sources": [encode_path(item) for item in settings.recent_sources],
    }


def decode_settings(payload: dict[str, Any]) -> AppSettings:
    """Return the :class:`AppSettings` described by ``payload``."""
    defaults = AppSettings()
    return AppSettings(
        game_root=decode_path(payload.get("game_root")),
        auto_backup=bool(payload.get("auto_backup", defaults.auto_backup)),
        confirm_root_installs=bool(
            payload.get("confirm_root_installs", defaults.confirm_root_installs)
        ),
        keep_extracted_temp=bool(
            payload.get("keep_extracted_temp", defaults.keep_extracted_temp)
        ),
        max_backup_generations=int(
            payload.get("max_backup_generations", defaults.max_backup_generations)
        ),
        theme=str(payload.get("theme", defaults.theme)),
        language=str(payload.get("language", defaults.language)),
        crash_monitor_enabled=bool(
            payload.get("crash_monitor_enabled", defaults.crash_monitor_enabled)
        ),
        seven_zip_path=decode_path(payload.get("seven_zip_path")),
        unrar_path=decode_path(payload.get("unrar_path")),
        nexus_api_key=str(payload.get("nexus_api_key", defaults.nexus_api_key) or ""),
        recent_sources=tuple(
            Path(str(item)) for item in payload.get("recent_sources", []) if item
        ),
    )


def _decode_enum(enum_type: Any, value: Any, fallback: Any) -> Any:
    """Return ``value`` as a member of ``enum_type``, or ``fallback``."""
    try:
        return enum_type(str(value))
    except ValueError:
        return fallback
