"""Resolve OpenIV-style DLC replace targets for vehicle stream assets.

Old replace packs (e.g. LaFerrari → ``turismor``) must land in a DLC
``dlc.rpf`` under ``mods/update/x64/dlcpacks/<pack>/``, not in root
``mods/x64e.rpf``. Authors usually document the path in a ReadMe; some zips
already embed the folder tree. Flat zips fall back to a small stock-model map.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.mod_file import FileInventory
from gta_mod_manager.plugins.gta_v import readme_spawn
from gta_mod_manager.utils import xml_tools

_LOGGER = get_logger("plugins.gta_v.replace_targets")

#: ``…/dlcpacks/<pack>/dlc.rpf/<member…>`` (optional ``x64w.rpf`` / ``update/x64`` prefix).
_DLC_MEMBER_PATH = re.compile(
    r"(?:^|[/\\])(?:x64w\.rpf[/\\])?(?:update[/\\])?(?:x64[/\\])?dlcpacks[/\\]"
    r"(?P<pack>[^/\\]+)[/\\]dlc\.rpf[/\\](?P<member>.+?)$",
    re.IGNORECASE,
)

#: Directory-only install lines (no leaf file): ends with ``something.rpf`` or ``.rpf\``.
_DLC_DIR_PATH = re.compile(
    r"(?:^|[/\\])(?:x64w\.rpf[/\\])?(?:update[/\\])?(?:x64[/\\])?dlcpacks[/\\]"
    r"(?P<pack>[^/\\]+)[/\\]dlc\.rpf[/\\](?P<member>.+?\.rpf)[/\\]?$",
    re.IGNORECASE,
)

#: How much of each document is scanned for OpenIV paths.
_MAX_DOCUMENT_CHARS = 12_000


@dataclass(frozen=True, slots=True)
class ReplaceTarget:
    """One vehicle replace destination under ``mods/update/x64/dlcpacks``."""

    pack_name: str
    #: Nested path inside the pack ``dlc.rpf`` through the inner ``*.rpf``.
    #: Example: ``x64/levels/gta5/vehicles/mpbusinessvehicles.rpf``.
    nested_rpf: str

    @property
    def relative_archive(self) -> Path:
        """Return the mods-relative outer archive path (the pack ``dlc.rpf``)."""
        return Path(
            *constants.DLC_PACKS_RELATIVE.split("/"),
            self.pack_name,
            "dlc.rpf",
        )

    def member_path(self, filename: str) -> str:
        """Return the full archive member path for ``filename``."""
        nested = self.nested_rpf.replace("\\", "/").strip("/")
        return f"{nested}/{Path(filename).name}"


#: Stock model stem → DLC home for flat replace zips without paths.
STOCK_DLC_HOMES: dict[str, ReplaceTarget] = {
    "turismor": ReplaceTarget(
        pack_name="mpbusiness",
        nested_rpf="x64/levels/gta5/vehicles/mpbusinessvehicles.rpf",
    ),
}


def model_stem_from_filename(name: str) -> str:
    """Return the spawn/model stem for a stream filename (strips ``_hi``)."""
    stem = Path(name).stem.lower()
    if stem.endswith("_hi"):
        stem = stem[: -len("_hi")]
    return stem


def parse_dlc_replace_path(path_text: str) -> tuple[str, str] | None:
    """Parse ``(pack_name, member_path)`` from an OpenIV-style path string.

    ``member_path`` may end at an inner ``.rpf`` (directory hint) or include a
    leaf filename.
    """
    cleaned = path_text.strip().strip("\"'").replace("\\", "/")
    while "//" in cleaned:
        cleaned = cleaned.replace("//", "/")
    match = _DLC_MEMBER_PATH.search(cleaned)
    if match is None:
        return None
    pack = match.group("pack").strip()
    member = match.group("member").replace("\\", "/").strip("/")
    if not pack or not member:
        return None
    return pack, member


def target_from_path_text(path_text: str) -> ReplaceTarget | None:
    """Build a :class:`ReplaceTarget` when ``path_text`` names a DLC replace home."""
    parsed = parse_dlc_replace_path(path_text)
    if parsed is None:
        return None
    pack, member = parsed
    # Directory hint: …/mpbusinessvehicles.rpf or …/turismor_mods.rpf
    if member.lower().endswith(".rpf"):
        return ReplaceTarget(pack_name=pack.lower(), nested_rpf=member)
    # File path: …/mpbusinessvehicles.rpf/turismor.yft
    nested, _sep, _leaf = member.rpartition("/")
    if not nested.lower().endswith(".rpf"):
        return None
    return ReplaceTarget(pack_name=pack.lower(), nested_rpf=nested)


def target_from_relative_path(relative_path: PurePosixPath) -> ReplaceTarget | None:
    """Return a DLC target when the packaged path embeds an OpenIV DLC tree."""
    return target_from_path_text(relative_path.as_posix())


def target_from_stock_home(filename: str) -> ReplaceTarget | None:
    """Return the known DLC home for a stock model filename, if any."""
    return STOCK_DLC_HOMES.get(model_stem_from_filename(filename))


def discover_readme_replace_targets(inventory: FileInventory) -> dict[str, ReplaceTarget]:
    """Map lowercase filenames (and ``*``) to DLC targets found in documentation.

    Directory-only ReadMe lines (no leaf file) are stored under ``*`` so every
    stream asset in the package can inherit that home when no per-file hint
    exists.
    """
    found: dict[str, ReplaceTarget] = {}
    for file in readme_spawn.iter_documentation(inventory):
        try:
            text = xml_tools.read_text(file.absolute_path)[:_MAX_DOCUMENT_CHARS]
        except OSError as error:
            _LOGGER.debug("Could not read %s: %s", file.name, error)
            continue
        for path_text in _candidate_path_strings(text):
            target = target_from_path_text(path_text)
            if target is None:
                continue
            leaf = Path(path_text.replace("\\", "/").rstrip("/")).name.lower()
            if leaf.endswith((".yft", ".ytd")):
                found.setdefault(leaf, target)
            else:
                found.setdefault("*", target)
    if found:
        _LOGGER.info(
            "Readme DLC replace target(s): %s",
            ", ".join(f"{name}→{target.pack_name}" for name, target in sorted(found.items())),
        )
    return found


def resolve_replace_target(
    relative_path: PurePosixPath,
    *,
    readme_targets: dict[str, ReplaceTarget] | None = None,
) -> ReplaceTarget | None:
    """Resolve the DLC replace home for one stream asset, if it is not x64e."""
    if relative_path.suffix.lower() not in constants.VEHICLE_STREAM_EXTENSIONS:
        return None

    embedded = target_from_relative_path(relative_path)
    if embedded is not None:
        return embedded

    name = relative_path.name.lower()
    hints = readme_targets or {}
    if name in hints:
        return hints[name]
    if "*" in hints:
        return hints["*"]

    return target_from_stock_home(relative_path.name)


def _candidate_path_strings(text: str) -> list[str]:
    """Pull OpenIV-looking path fragments out of a ReadMe body."""
    found: list[str] = []
    # Prefer explicit dlcpacks…dlc.rpf… spans.
    for match in re.finditer(
        r"(?:x64w\.rpf[/\\])?(?:update[/\\])?(?:x64[/\\])?dlcpacks[/\\]"
        r"[^\s\"'<>]+",
        text,
        re.IGNORECASE,
    ):
        found.append(match.group(0))
    return found
