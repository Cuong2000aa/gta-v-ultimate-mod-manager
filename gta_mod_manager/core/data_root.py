"""Machine-local selection of the application's writable data directory."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from gta_mod_manager.core import constants


def pointer_file() -> Path:
    """Return the stable bootstrap file used before the data root is known."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
    parent = Path(base) if base else Path(tempfile.gettempdir())
    return parent / constants.DATA_ROOT_POINTER_FILE


def configured_data_root(path: Path | None = None) -> Path | None:
    """Read the selected data root, returning ``None`` for a stale pointer."""
    payload = _read_pointer(path or pointer_file())
    value = payload.get("data_dir")
    if not value:
        return None
    root = Path(str(value)).expanduser()
    return root if root.is_dir() else None


def write_data_root(
    root: Path,
    *,
    previous_root: Path | None = None,
    path: Path | None = None,
) -> None:
    """Atomically select ``root`` and optionally schedule old-data cleanup."""
    target = path or pointer_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, str | int] = {
        "version": 1,
        "data_dir": str(root.resolve()),
    }
    if previous_root is not None:
        payload["pending_cleanup"] = str(previous_root.resolve())
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    temporary.replace(target)


def finalize_pending_cleanup(active_root: Path, path: Path | None = None) -> bool:
    """Delete the old data copy after the migrated root starts successfully.

    Cleanup only runs when the pointer selects ``active_root`` and the
    destination contains the migration marker. Failures are retained for a
    later startup rather than preventing the app from opening.
    """
    target = path or pointer_file()
    payload = _read_pointer(target)
    pending = payload.get("pending_cleanup")
    selected = payload.get("data_dir")
    if not pending or not selected:
        return False

    active = active_root.resolve()
    destination = Path(str(selected)).resolve()
    source = Path(str(pending)).resolve()
    marker = destination / constants.DATA_MIGRATION_MARKER_FILE
    if active != destination or source == destination or not marker.is_file():
        return False
    if _contains(source, destination) or _contains(destination, source):
        return False

    try:
        if source.exists():
            shutil.rmtree(source)
        marker.unlink(missing_ok=True)
        write_data_root(destination, path=target)
    except OSError:
        return False
    return True


def _read_pointer(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True
