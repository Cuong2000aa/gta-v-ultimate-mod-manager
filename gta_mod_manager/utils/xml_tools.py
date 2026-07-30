"""Tolerant XML reading plus the repair routines GTA V meta files need.

Community meta files are frequently malformed: BOM markers, stray ``&``
characters, duplicated root elements, Windows-1252 bytes in a file declared as
UTF-8. ``ElementTree`` refuses all of those, so this module repairs the common
cases before parsing and reports what it had to change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from gta_mod_manager.core.exceptions import ValidationError
from gta_mod_manager.core.logging_setup import get_logger

_LOGGER = get_logger("utils.xml")

_BOM = "\ufeff"
_BARE_AMPERSAND = re.compile(r"&(?!(?:[a-zA-Z][a-zA-Z0-9]*|#[0-9]+|#x[0-9a-fA-F]+);)")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_TRAILING_GARBAGE = re.compile(r">\s*[^<\s][^<]*$")


@dataclass(frozen=True, slots=True)
class XmlRepairResult:
    """Outcome of :func:`load_xml`.

    Attributes:
        root: Parsed document root.
        repairs: Human readable description of each applied fix.
        source: File the document was read from, when applicable.
    """

    root: ElementTree.Element
    repairs: tuple[str, ...] = field(default_factory=tuple)
    source: Path | None = None

    @property
    def was_repaired(self) -> bool:
        """Return whether any fix had to be applied."""
        return bool(self.repairs)


def read_text(path: Path) -> str:
    """Read ``path`` as text, trying the encodings GTA V meta files use."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")  # pragma: no cover - safety net


def repair_xml_text(text: str) -> tuple[str, tuple[str, ...]]:
    """Apply the standard fixes to an XML document.

    Returns:
        The repaired text and a tuple describing each change.
    """
    repairs: list[str] = []

    if text.startswith(_BOM):
        text = text.lstrip(_BOM)
        repairs.append("Removed byte order mark")

    if _CONTROL_CHARS.search(text):
        text = _CONTROL_CHARS.sub("", text)
        repairs.append("Removed illegal control characters")

    escaped, count = _BARE_AMPERSAND.subn("&amp;", text)
    if count:
        text = escaped
        repairs.append(f"Escaped {count} bare ampersand(s)")

    stripped = text.strip()
    if stripped and not stripped.startswith("<"):
        index = stripped.find("<")
        if index > 0:
            stripped = stripped[index:]
            repairs.append("Removed junk before the first element")

    if _TRAILING_GARBAGE.search(stripped):
        last = stripped.rfind(">")
        if last != -1:
            stripped = stripped[: last + 1]
            repairs.append("Removed junk after the last element")

    return stripped, tuple(repairs)


def parse_xml_text(text: str, *, source: Path | None = None) -> XmlRepairResult:
    """Parse ``text``, repairing it when the first attempt fails.

    Raises:
        ValidationError: When the document is broken beyond repair.
    """
    try:
        return XmlRepairResult(root=ElementTree.fromstring(text), source=source)
    except ElementTree.ParseError as first_error:
        repaired, repairs = repair_xml_text(text)
        try:
            root = ElementTree.fromstring(repaired)
        except ElementTree.ParseError as second_error:
            raise ValidationError(
                "XML document could not be parsed",
                source=str(source) if source else "<memory>",
                original_error=str(first_error),
                repair_error=str(second_error),
            ) from second_error
        if repairs:
            _LOGGER.info("Repaired XML %s: %s", source or "<memory>", "; ".join(repairs))
        return XmlRepairResult(root=root, repairs=repairs, source=source)


def load_xml(path: Path) -> XmlRepairResult:
    """Read and parse ``path``, applying repairs when necessary."""
    return parse_xml_text(read_text(path), source=path)


def save_xml(path: Path, root: ElementTree.Element) -> None:
    """Write ``root`` to ``path`` as UTF-8 with an XML declaration."""
    tree = ElementTree.ElementTree(root)
    _indent(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _indent(element: ElementTree.Element, level: int = 0) -> None:
    """Pretty-print ``element`` in place (``ElementTree.indent`` backport)."""
    pad = "\n" + "  " * level
    if len(element):
        if not (element.text or "").strip():
            element.text = pad + "  "
        for child in element:
            _indent(child, level + 1)
        if not (element[-1].tail or "").strip():
            element[-1].tail = pad
    if level and not (element.tail or "").strip():
        element.tail = pad


def find_text(element: ElementTree.Element, tag: str, default: str = "") -> str:
    """Return the stripped text of the first ``tag`` child, or ``default``."""
    child = element.find(tag)
    if child is None:
        return default
    return (child.text or "").strip() or default


def find_attribute(element: ElementTree.Element, tag: str, attribute: str) -> str | None:
    """Return an attribute of the first ``tag`` child, if present."""
    child = element.find(tag)
    if child is None:
        return None
    return child.get(attribute)


def iter_elements(root: ElementTree.Element, *tags: str) -> list[ElementTree.Element]:
    """Return every descendant whose tag matches one of ``tags``.

    Matching is case-insensitive because GTA V meta files are inconsistent
    (``Item`` versus ``item``).
    """
    wanted = {tag.lower() for tag in tags}
    return [element for element in root.iter() if element.tag.lower() in wanted]
