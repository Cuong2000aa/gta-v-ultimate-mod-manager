"""Content hashing helpers used by the scanner, installer and backup engine."""

from __future__ import annotations

import hashlib
from pathlib import Path

from gta_mod_manager.core import constants


def sha256_file(path: Path, chunk_size: int = constants.HASH_CHUNK_SIZE) -> str:
    """Return the hexadecimal SHA-256 digest of ``path``.

    Args:
        path: File to hash.
        chunk_size: Read buffer size, tuned for large ``.rpf`` archives.

    Returns:
        The lowercase hexadecimal digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    """Return the SHA-256 digest of ``text`` encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short_id(text: str, length: int = 12) -> str:
    """Return a short, stable identifier derived from ``text``."""
    return sha256_text(text)[:length]


def files_are_identical(left: Path, right: Path) -> bool:
    """Return whether two files have the same size and content hash."""
    if not left.is_file() or not right.is_file():
        return False
    if left.stat().st_size != right.stat().st_size:
        return False
    return sha256_file(left) == sha256_file(right)
