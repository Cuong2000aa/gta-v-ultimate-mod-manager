"""Extract trainer spawn codes from the documentation a vehicle mod ships.

Authors almost always write the spawn name somewhere in a ``ReadMe``,
``INSTRUCTION`` or ``INSTALL`` text file. Those lines are more trustworthy
than model names scraped from a ``dlc.rpf``, because the RPF also contains
tuning parts and leftover template cars.
"""

from __future__ import annotations

import re
from pathlib import Path

from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.utils import xml_tools

_LOGGER = get_logger("plugins.gta_v.readme_spawn")

#: How much of each document is inspected for spawn phrases.
_MAX_DOCUMENT_CHARS = 12_000

#: File-name fragments that mark an instruction / readme document.
_DOC_NAME_HINTS: tuple[str, ...] = (
    "readme",
    "read me",
    "read_me",
    "instruction",
    "instalation",  # common misspelling in community packs
    "installation",
    "install",
    "how to",
    "howto",
    "spawn",
    "info",
    "说明",
)

#: Exact lower-cased names that always count as documentation.
_DOC_EXACT_NAMES: frozenset[str] = frozenset(
    {
        "readme.txt",
        "readme.md",
        "read me.txt",
        "install.txt",
        "installation.txt",
        "instructions.txt",
        "instruction.txt",
        "info.txt",
        "说明.txt",
    }
)

#: Phrases authors use to tell the player which name to type in a trainer.
#: Ordered from most specific to most general so the first match for a line
#: wins when several patterns could fire.
_SPAWN_PATTERNS: tuple[re.Pattern[str], ...] = (
    # [spawncode] = amrevu23mg
    re.compile(
        r"\[\s*spawn\s*code\s*\]\s*[=:]\s*[`'\"]?([a-zA-Z0-9][a-zA-Z0-9_]{1,39})",
        re.IGNORECASE,
    ),
    # Spawn name is LP580 / spawn code: hellcat
    re.compile(
        r"spawn\s*(?:name|code)\s*(?:is|=|:)\s*[`'\"]?([a-zA-Z0-9][a-zA-Z0-9_]{1,39})",
        re.IGNORECASE,
    ),
    # spawn it by name: hellcat / Spawn it with name: sesto /
    # spawn the car by name 570s2 / Use ... Spawn it by name AST
    re.compile(
        r"spawn(?:ing)?(?:\s+(?:it|the\s+(?:car|vehicle)|them))?\s+"
        r"(?:with|by)\s+name\s*[=:]?\s*[`'\"]?([a-zA-Z0-9][a-zA-Z0-9_]{1,39})",
        re.IGNORECASE,
    ),
    # Type this name: 10ram
    re.compile(
        r"type\s+this\s+name\s*:\s*[`'\"]?([a-zA-Z0-9][a-zA-Z0-9_]{1,39})",
        re.IGNORECASE,
    ),
    # and type "fpino" / type 'ben17'
    re.compile(
        r"\btype\s+[\"'`]([a-zA-Z0-9][a-zA-Z0-9_]{1,39})[\"'`]",
        re.IGNORECASE,
    ),
    # use the name - ben17 / use the name: AST
    re.compile(
        r"(?:use|using)\s+(?:the\s+)?name\s*[-:=]\s*[`'\"]?([a-zA-Z0-9][a-zA-Z0-9_]{1,39})",
        re.IGNORECASE,
    ),
    # 刷车 "AST" / 输入 "fpino" (Chinese community packs)
    re.compile(
        r"(?:刷车|刷出|输入|召唤)\s*[\"'`]([a-zA-Z0-9][a-zA-Z0-9_]{1,39})[\"'`]",
    ),
    re.compile(
        r"[\"'`]([a-zA-Z0-9][a-zA-Z0-9_]{1,39})[\"'`]\s*(?:刷车|刷出)",
    ),
)

#: Words that look like spawn codes but never are.
_SPAWN_STOPWORDS: frozenset[str] = frozenset(
    {
        "name",
        "spawn",
        "spawncode",
        "code",
        "car",
        "vehicle",
        "trainer",
        "simple",
        "menyoo",
        "native",
        "addon",
        "add",
        "on",
        "replace",
        "openiv",
        "dlcpacks",
        "update",
        "folder",
        "game",
        "mods",
        "true",
        "false",
        "null",
        "item",
        "path",
        "type",
        "value",
        "here",
        "this",
        "that",
        "with",
        "from",
        "into",
        "your",
        "the",
        "and",
        "for",
        "use",
        "using",
        "open",
        "save",
        "edit",
        "file",
        "files",
        "line",
        "new",
        "xml",
        "meta",
        "yft",
        "ytd",
        "rpf",
    }
)


def iter_documentation(inventory: FileInventory) -> tuple[ModFile, ...]:
    """Return the instruction / readme files inside ``inventory``."""
    matches: list[ModFile] = []
    for file in inventory.files:
        if file.suffix not in {".txt", ".md", ".nfo", ".rtf"}:
            continue
        if _is_documentation(file):
            matches.append(file)
    # Prefer short root-level docs, then ones whose name mentions spawn/readme.
    matches.sort(
        key=lambda item: (
            0 if "spawn" in item.lower_name else 1,
            0 if "readme" in item.lower_name else 1,
            0 if "instruction" in item.lower_name or "install" in item.lower_name else 1,
            len(item.relative_path.parts),
            item.lower_name,
        )
    )
    return tuple(matches)


def extract_spawn_codes(inventory: FileInventory) -> tuple[tuple[str, Path], ...]:
    """Return ``(spawn_code, source_file)`` pairs found in documentation.

    Codes are returned in the order they appear across documents, with
    duplicates removed. Empty when no documentation names a spawn code.
    """
    found: dict[str, Path] = {}
    for file in iter_documentation(inventory):
        try:
            text = xml_tools.read_text(file.absolute_path)[:_MAX_DOCUMENT_CHARS]
        except OSError as error:
            _LOGGER.debug("Could not read %s: %s", file.name, error)
            continue
        for code in _codes_in_text(text):
            found.setdefault(code, file.absolute_path)
    if found:
        _LOGGER.info(
            "Readme spawn code(s): %s",
            ", ".join(sorted(found)),
        )
    return tuple((code, source) for code, source in found.items())


def _is_documentation(file: ModFile) -> bool:
    """Return whether ``file`` looks like an instruction document."""
    name = file.lower_name
    if name in _DOC_EXACT_NAMES:
        return True
    stem = Path(name).stem
    return any(hint in stem for hint in _DOC_NAME_HINTS)


def _codes_in_text(text: str) -> list[str]:
    """Return every spawn code a document text declares."""
    codes: list[str] = []
    seen: set[str] = set()
    for pattern in _SPAWN_PATTERNS:
        for match in pattern.finditer(text):
            if _is_search_prompt(text, match.start()):
                continue
            code = match.group(1).lower()
            if code in seen or not _is_plausible_spawn(code):
                continue
            seen.add(code)
            codes.append(code)
    return codes


def _is_search_prompt(text: str, index: int) -> bool:
    """Return whether the match sits in an OpenIV "Search and type" sentence.

    Those lines name a *vanilla* car to find in ``vehicles.meta``, not the
    spawn code of the mod, so they must not become trainer names.
    """
    window = text[max(0, index - 48) : index].lower()
    return "search" in window


def _is_plausible_spawn(code: str) -> bool:
    """Return whether ``code`` looks like something a trainer would accept."""
    if len(code) < 2 or len(code) > 40:
        return False
    if code in _SPAWN_STOPWORDS:
        return False
    if not code[0].isalnum():
        return False
    # Pure numbers are line numbers / version crumbs, never spawn codes.
    return not code.isdigit()
