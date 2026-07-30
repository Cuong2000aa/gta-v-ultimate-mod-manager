"""Crash-safe JSON document storage.

Writes go to a temporary file that is then atomically replaced, so an
interrupted save can never truncate the installed-mods database.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

from gta_mod_manager.core.exceptions import RepositoryError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.utils import fs

_LOGGER = get_logger("repository.json")


class JsonStore:
    """A single JSON document on disk, guarded by a lock.

    Args:
        path: Location of the document.
        default: Value returned when the document does not exist yet.
    """

    def __init__(self, path: Path, default: dict[str, Any] | None = None) -> None:
        self._path = path
        self._default: dict[str, Any] = default if default is not None else {}
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        """Return the document location."""
        return self._path

    def exists(self) -> bool:
        """Return whether the document has been written yet."""
        return self._path.is_file()

    def read(self) -> dict[str, Any]:
        """Return the document content, or the default when absent.

        A corrupted document is moved aside instead of crashing the app, so the
        user can still start the manager and re-scan their installation.
        """
        with self._lock:
            if not self._path.is_file():
                return dict(self._default)
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                backup = self._quarantine()
                _LOGGER.error(
                    "Corrupted database %s moved to %s: %s", self._path, backup, error
                )
                return dict(self._default)
            if not isinstance(payload, dict):
                return dict(self._default)
            return payload

    def write(self, payload: dict[str, Any]) -> None:
        """Atomically replace the document with ``payload``.

        Raises:
            RepositoryError: When the document could not be written.
        """
        with self._lock:
            fs.ensure_directory(self._path.parent)
            temporary = self._path.with_suffix(self._path.suffix + ".tmp")
            try:
                temporary.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                temporary.replace(self._path)
            except OSError as error:
                temporary.unlink(missing_ok=True)
                raise RepositoryError(
                    "Could not write the database", path=str(self._path), detail=str(error)
                ) from error

    def update(
        self, mutate: Callable[[dict[str, Any]], dict[str, Any]]
    ) -> dict[str, Any]:
        """Read, apply ``mutate`` and write back in one locked step.

        Args:
            mutate: Callable receiving the current payload and returning the
                payload to persist.

        Returns:
            The payload that was written.
        """
        with self._lock:
            payload = mutate(self.read())
            self.write(payload)
            return payload

    def _quarantine(self) -> Path:
        """Move a corrupted document aside and return the new location."""
        target = fs.unique_path(self._path.with_suffix(self._path.suffix + ".corrupt"))
        with suppress(OSError):  # pragma: no cover - best effort
            self._path.replace(target)
        return target
