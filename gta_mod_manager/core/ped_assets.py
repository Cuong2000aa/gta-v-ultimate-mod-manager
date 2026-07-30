"""Recognises GTA V ped (character) model sets by file naming.

Vehicles ship a ``.yft`` mesh plus a ``.ytd`` texture dictionary. Peds add a
``.ydd`` drawable dictionary, which vehicles never use. That single marker is
enough to tell an Iron Man suit apart from a car, and it is what keeps
character models out of ``levels/gta5/vehicles.rpf``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath

#: Drawable dictionary: shipped by peds and props, never by vehicles.
PED_DRAWABLE_SUFFIX = ".ydd"

#: Extensions a ped component set may ship next to its ``.ydd``.
PED_SET_SUFFIXES: frozenset[str] = frozenset({".ydd", ".ymt", ".yft", ".ytd"})

#: Meta files that only ever ship with a ped package.
PED_META_FILES: frozenset[str] = frozenset(
    {
        "peds.meta",
        "pedmodelinfo.meta",
        "pedalternatevariations.meta",
        "pedpersonality.meta",
    }
)

#: Suffix GTA V appends to high-detail texture dictionaries.
_HIGH_DETAIL_MARKER = "+hi"


def model_stem(name: str) -> str:
    """Return the lowercase model name of ``name`` without ``+hi``."""
    stem = PurePosixPath(name).stem.lower()
    if stem.endswith(_HIGH_DETAIL_MARKER):
        return stem[: -len(_HIGH_DETAIL_MARKER)]
    return stem


def _model_stem(name: str) -> str:
    """Backward-compatible alias for :func:`model_stem`."""
    return model_stem(name)


def ped_model_stems(names: Iterable[str]) -> frozenset[str]:
    """Return the model names that ship a ``.ydd`` drawable.

    Args:
        names: File names or package-relative paths, in any case.
    """
    return frozenset(
        model_stem(name)
        for name in names
        if PurePosixPath(name).suffix.lower() == PED_DRAWABLE_SUFFIX
    )


def is_ped_asset(name: str, stems: frozenset[str]) -> bool:
    """Return whether ``name`` belongs to one of the detected ped models."""
    if not stems:
        return False
    if PurePosixPath(name).suffix.lower() not in PED_SET_SUFFIXES:
        return False
    return model_stem(name) in stems
