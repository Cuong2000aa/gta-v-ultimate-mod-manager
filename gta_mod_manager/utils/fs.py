"""Filesystem helpers with the safety checks the mod manager relies on."""

from __future__ import annotations

import errno
import os
import shutil
import stat
import unicodedata
from collections.abc import Callable, Iterator
from pathlib import Path, PurePosixPath

from gta_mod_manager.core.exceptions import SafetyViolationError
from gta_mod_manager.core.logging_setup import get_logger

_LOGGER = get_logger("utils.fs")

_INVALID_NAME_CHARS = '<>:"|?*'

#: Chunk used when a copy has to report progress; multi-gigabyte archives make
#: a silent :func:`shutil.copy2` look like a hang.
_COPY_CHUNK_BYTES = 8 * 1024 * 1024


def normalise(path: Path) -> Path:
    r"""Return an absolute, symlink-free, case-normalised path.

    Windows paths are compared case-insensitively; using this helper for every
    comparison avoids ``C:\\Games`` and ``c:\\games`` being treated as
    different locations.
    """
    resolved = Path(os.path.normpath(str(path.expanduser())))
    try:
        resolved = resolved.resolve()
    except (OSError, RuntimeError):
        resolved = resolved.absolute()
    return resolved


def is_relative_to(child: Path, parent: Path) -> bool:
    """Return whether ``child`` lives inside ``parent``.

    Comparison is case-insensitive on Windows and tolerant of unresolved
    paths, unlike :meth:`pathlib.Path.is_relative_to`.
    """
    child_parts = _comparable_parts(normalise(child))
    parent_parts = _comparable_parts(normalise(parent))
    if len(child_parts) < len(parent_parts):
        return False
    return child_parts[: len(parent_parts)] == parent_parts


def _comparable_parts(path: Path) -> tuple[str, ...]:
    """Return path components normalised for case-insensitive comparison."""
    fold = os.name == "nt"
    return tuple(
        unicodedata.normalize("NFC", part).lower() if fold else part for part in path.parts
    )


def ensure_directory(path: Path) -> Path:
    """Create ``path`` (including parents) and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_join(base: Path, relative: str | PurePosixPath) -> Path:
    """Join ``relative`` onto ``base`` while blocking path traversal.

    Archive members are attacker-controlled input: an entry named
    ``../../Windows/System32/x.dll`` must never escape the destination.

    Raises:
        SafetyViolationError: When the result would leave ``base``.
    """
    candidate = (base / str(relative)).resolve() if base.is_absolute() else base / str(relative)
    resolved_base = normalise(base)
    resolved_candidate = normalise(candidate)
    if not is_relative_to(resolved_candidate, resolved_base):
        raise SafetyViolationError(
            "Refusing to write outside the destination directory",
            base=str(resolved_base),
            member=str(relative),
        )
    return resolved_candidate


def iter_files(root: Path, max_depth: int | None = None) -> Iterator[Path]:
    """Yield every file under ``root``, skipping unreadable directories.

    Args:
        root: Directory to walk.
        max_depth: Optional limit relative to ``root``; ``None`` means no limit.
    """
    if not root.exists():
        return
    root_depth = len(root.parts)
    for current_dir, dir_names, file_names in os.walk(root, onerror=_on_walk_error):
        current = Path(current_dir)
        if max_depth is not None and len(current.parts) - root_depth >= max_depth:
            dir_names[:] = []
        for name in file_names:
            yield current / name


def _on_walk_error(error: OSError) -> None:
    """Log directories that could not be traversed instead of failing."""
    _LOGGER.warning("Skipping unreadable directory: %s", error)


def copy_file(
    source: Path,
    destination: Path,
    *,
    overwrite: bool = True,
    on_bytes: Callable[[int], None] | None = None,
) -> Path:
    """Copy ``source`` to ``destination`` preserving timestamps.

    Parent directories are created automatically.

    Args:
        source: File to read.
        destination: File to write.
        overwrite: Whether an existing destination may be replaced.
        on_bytes: Called with the number of bytes copied so far, once per
            chunk. Passing it switches to a chunked copy.

    Raises:
        FileExistsError: When ``destination`` exists and ``overwrite`` is off.
    """
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists: {destination}")
    ensure_directory(destination.parent)
    if destination.exists():
        make_writable(destination)
    if on_bytes is None:
        shutil.copy2(source, destination)
        return destination

    copied = 0
    with source.open("rb") as reader, destination.open("wb") as writer:
        while chunk := reader.read(_COPY_CHUNK_BYTES):
            writer.write(chunk)
            copied += len(chunk)
            on_bytes(copied)
    shutil.copystat(source, destination)
    return destination


def move_file(source: Path, destination: Path) -> Path:
    """Move ``source`` to ``destination``, falling back to copy+delete."""
    ensure_directory(destination.parent)
    try:
        source.replace(destination)
    except OSError as error:
        if error.errno not in (errno.EXDEV, errno.EACCES):
            raise
        shutil.copy2(source, destination)
        source.unlink(missing_ok=True)
    return destination


def make_writable(path: Path) -> None:
    """Clear the read-only flag so the file can be replaced or removed."""
    try:
        path.chmod(path.stat().st_mode | stat.S_IWRITE)
    except OSError:  # pragma: no cover - best effort only
        _LOGGER.debug("Could not clear read-only flag on %s", path)


def delete_file(path: Path) -> bool:
    """Delete ``path`` if it exists and return whether something was removed."""
    if not path.exists():
        return False
    make_writable(path)
    path.unlink()
    return True


def delete_tree(path: Path) -> bool:
    """Recursively delete ``path`` and return whether it existed."""
    if not path.exists():
        return False
    shutil.rmtree(path, onerror=_force_remove)
    return True


def _force_remove(func, path, _exc_info) -> None:  # type: ignore[no-untyped-def]  # noqa: ANN001
    """``shutil.rmtree`` error handler that clears read-only flags."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:  # pragma: no cover - nothing else we can do
        _LOGGER.warning("Could not delete %s", path)


def remove_empty_directories(root: Path, stop_at: Path) -> int:
    """Delete empty directories from ``root`` upwards, stopping at ``stop_at``.

    Returns:
        The number of directories that were removed.
    """
    removed = 0
    current = root
    while current != stop_at and is_relative_to(current, stop_at):
        if not current.is_dir() or any(current.iterdir()):
            break
        try:
            current.rmdir()
        except OSError:
            break
        removed += 1
        current = current.parent
    return removed


def directory_size(root: Path) -> int:
    """Return the total size in bytes of every file under ``root``."""
    return sum(item.stat().st_size for item in iter_files(root) if item.is_file())


def sanitise_name(name: str, fallback: str = "unnamed") -> str:
    """Return a file-system safe version of ``name``."""
    cleaned = "".join("_" if char in _INVALID_NAME_CHARS else char for char in name)
    cleaned = cleaned.strip(" .")
    return cleaned or fallback


def unique_path(candidate: Path) -> Path:
    """Return ``candidate`` or the first free ``name (n)`` variant."""
    if not candidate.exists():
        return candidate
    stem, suffix, parent = candidate.stem, candidate.suffix, candidate.parent
    index = 2
    while True:
        alternative = parent / f"{stem} ({index}){suffix}"
        if not alternative.exists():
            return alternative
        index += 1


def human_size(num_bytes: int) -> str:
    """Format a byte count using binary units, e.g. ``1.4 MB``."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            precision = 0 if unit == "B" else 1
            return f"{size:.{precision}f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"  # pragma: no cover - unreachable
