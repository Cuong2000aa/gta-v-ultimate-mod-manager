"""Temporary extraction workspaces with deterministic cleanup."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import TracebackType

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.utils import fs

_LOGGER = get_logger("scanner.workspace")


class TempWorkspace:
    """A disposable folder used while a package is being analysed.

    The workspace is a context manager, so an aborted analysis can never leave
    gigabytes of extracted vehicles behind::

        with TempWorkspace(paths) as workspace:
            inventory = scanner.scan(archive, workspace.root)
    """

    def __init__(self, paths: AppPaths, *, keep: bool = False, prefix: str = "pkg") -> None:
        self._paths = paths
        self._keep = keep
        self._root = paths.temp / f"{prefix}-{uuid.uuid4().hex[:10]}"
        self._disposed = False

    @property
    def root(self) -> Path:
        """Return the workspace directory, creating it on first access."""
        return fs.ensure_directory(self._root)

    @property
    def keep(self) -> bool:
        """Return whether the workspace survives :meth:`dispose`."""
        return self._keep

    def subdirectory(self, name: str) -> Path:
        """Return (and create) a named folder inside the workspace."""
        return fs.ensure_directory(self.root / fs.sanitise_name(name))

    def dispose(self) -> None:
        """Delete the workspace unless it was created with ``keep=True``."""
        if self._disposed or self._keep:
            return
        self._disposed = True
        if fs.delete_tree(self._root):
            _LOGGER.debug("Removed workspace %s", self._root)

    def __enter__(self) -> "TempWorkspace":
        """Create the workspace directory and return this instance."""
        self.root  # noqa: B018 - property has the side effect of creating it
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Dispose of the workspace when leaving the ``with`` block."""
        self.dispose()


def purge_stale_workspaces(paths: AppPaths) -> int:
    """Delete every leftover workspace from a previous run.

    Returns:
        The number of directories that were removed.
    """
    if not paths.temp.exists():
        return 0
    removed = 0
    for child in paths.temp.iterdir():
        if child.is_dir() and fs.delete_tree(child):
            removed += 1
    if removed:
        _LOGGER.info("Purged %d stale extraction workspace(s)", removed)
    return removed
