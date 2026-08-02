"""Helpers that turn vehicle files / spawn codes into comparable keys."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

#: Stream assets that identify which stock vehicle a replace mod overwrites.
_REPLACE_EXTENSIONS = frozenset({".yft", ".ytd"})

#: Substrings that mark tuning / livery parts, not trainer spawn names.
#: Keep in sync with :mod:`gta_mod_manager.plugins.gta_v.vehicle_meta`.
_PART_LIKE_FRAGMENTS: tuple[str, ...] = (
    "_int_",
    "_ext_",
    "_bon",
    "_spoil",
    "_roll",
    "_wing",
    "_cage",
    "_roof",
    "_bumper",
    "_skirt",
    "_bumf",
    "_bumr",
    "_bum",
    "_hood",
    "_grill",
    "_exh",
    "_liv",
    "_arch",
    "_split",
    "_fend",
    "_door",
    "_mir",
    "_seat",
    "_steer",
)


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


def complete_model_stems_from_members(members: Iterable[str]) -> frozenset[str]:
    """Return stems that ship both a ``.yft`` and a ``.ytd`` in ``members``.

    Real cars almost always include both; tuning parts are usually ``.yft`` only.
    """
    models: set[str] = set()
    textures: set[str] = set()
    for member in members:
        leaf = member.replace("\\", "/").rsplit("/", 1)[-1]
        suffix = Path(leaf).suffix.lower()
        if suffix not in _REPLACE_EXTENSIONS:
            continue
        key = model_key_from_filename(leaf)
        if not key:
            continue
        (models if suffix == ".yft" else textures).add(key)
    return frozenset(models & textures)


def is_part_like_model(name: str) -> bool:
    """Return whether ``name`` looks like a tuning / livery part, not a car."""
    lowered = name.strip().lower()
    return any(fragment in lowered for fragment in _PART_LIKE_FRAGMENTS)


def refine_vehicle_spawn_codes(
    codes: Iterable[str],
    archive_members: Iterable[str] = (),
) -> tuple[str, ...]:
    """Drop tuning-part names so Spawn Center only lists real trainer codes.

    When archive members include at least one complete ``.yft`` + ``.ytd``
    pair, only those models are kept. Otherwise part-like names are removed.
    """
    ordered: list[str] = []
    seen: set[str] = set()
    for code in codes:
        cleaned = code.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    if len(ordered) <= 1:
        return tuple(ordered)

    complete = complete_model_stems_from_members(archive_members)
    if complete:
        matched = [code for code in ordered if code.lower() in complete]
        if matched:
            return tuple(matched)
        return tuple(sorted(complete))

    without_parts = [code for code in ordered if not is_part_like_model(code)]
    return tuple(without_parts or ordered)


def model_keys_for_installed_mod(
    spawn_codes: Iterable[str], archive_members: Iterable[str]
) -> frozenset[str]:
    """Union of refined spawn codes and keys inferred from RPF members."""
    keys = {
        code.strip().lower()
        for code in refine_vehicle_spawn_codes(spawn_codes, archive_members)
        if code and code.strip()
    }
    keys.update(model_keys_from_archive_members(archive_members))
    return frozenset(keys)
