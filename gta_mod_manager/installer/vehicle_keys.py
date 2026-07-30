"""Helpers that turn vehicle files / spawn codes into comparable keys."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

#: Stream assets that identify which stock vehicle a replace mod overwrites.
_REPLACE_EXTENSIONS = frozenset({".yft", ".ytd"})


def model_key_from_filename(name: str) -> str:
    """Return the spawn/model key for a stream filename.

    ``buffalo2.yft``, ``buffalo2.ytd`` and ``buffalo2_hi.yft`` all collapse to
    ``buffalo2``.
    """
    stem = Path(name).stem.lower()
    if stem.endswith("_hi"):
        stem = stem[: -len("_hi")]
    return stem


def model_keys_from_archive_members(members: Iterable[str]) -> frozenset[str]:
    """Return replace-model keys implied by nested RPF member paths."""
    keys: set[str] = set()
    for member in members:
        leaf = member.replace("\\", "/").rsplit("/", 1)[-1]
        if Path(leaf).suffix.lower() not in _REPLACE_EXTENSIONS:
            continue
        key = model_key_from_filename(leaf)
        if key:
            keys.add(key)
    return frozenset(keys)


def model_keys_for_installed_mod(
    spawn_codes: Iterable[str], archive_members: Iterable[str]
) -> frozenset[str]:
    """Union of declared spawn codes and keys inferred from RPF members."""
    keys = {code.strip().lower() for code in spawn_codes if code and code.strip()}
    keys.update(model_keys_from_archive_members(archive_members))
    return frozenset(keys)
