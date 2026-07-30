"""Reads OpenIV packages (``.oiv``) and decides what can be done natively.

An ``.oiv`` is a zip containing ``assembly.xml`` (OpenIV 2.x) or the older
``package.xml`` plus a ``content`` folder. The descriptor lists commands such
as *copy this file into that archive*.

Commands that target a real folder can be executed by this manager. Commands
that write inside an ``.rpf`` archive, or that patch XML inside one, cannot -
those are reported as manual OpenIV steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from gta_mod_manager.core import constants
from gta_mod_manager.core.exceptions import ValidationError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.mod_file import FileInventory
from gta_mod_manager.utils import xml_tools

_LOGGER = get_logger("plugins.gta_v.oiv")


@dataclass(frozen=True, slots=True)
class OivCommand:
    """One installation instruction taken from the OIV descriptor.

    Attributes:
        source: Path inside the package's ``content`` folder.
        destination: Game-relative destination declared by the package.
        is_archive_target: Whether the destination points inside an ``.rpf``.
        kind: ``add``, ``delete`` or ``xml`` depending on the descriptor node.
    """

    source: PurePosixPath | None
    destination: PurePosixPath
    is_archive_target: bool
    kind: str = "add"

    @property
    def is_installable(self) -> bool:
        """Return whether this manager can execute the command itself."""
        return self.kind == "add" and self.source is not None and not self.is_archive_target


@dataclass(frozen=True, slots=True)
class OivPackage:
    """An OpenIV package descriptor reduced to what the installer needs."""

    descriptor: Path
    name: str = ""
    version: str = ""
    author: str = ""
    description: str = ""
    content_root: Path | None = None
    commands: tuple[OivCommand, ...] = field(default_factory=tuple)
    repairs: tuple[str, ...] = field(default_factory=tuple)

    @property
    def installable_commands(self) -> tuple[OivCommand, ...]:
        """Return the commands this manager can execute natively."""
        return tuple(command for command in self.commands if command.is_installable)

    @property
    def archive_commands(self) -> tuple[OivCommand, ...]:
        """Return the commands that require OpenIV itself."""
        return tuple(command for command in self.commands if not command.is_installable)

    @property
    def requires_openiv(self) -> bool:
        """Return whether any command needs OpenIV."""
        return bool(self.archive_commands)

    @property
    def display_name(self) -> str:
        """Return the package name, falling back to the descriptor folder."""
        return self.name or self.descriptor.parent.name


class OivPackageParser:
    """Parses ``assembly.xml`` / ``package.xml`` descriptors."""

    def find_descriptor(self, inventory: FileInventory) -> Path | None:
        """Return the OIV descriptor inside ``inventory``, if there is one."""
        for name in (constants.ASSEMBLY_XML, constants.PACKAGE_XML):
            matches = inventory.by_name(name)
            if matches:
                return min(matches, key=lambda item: len(item.relative_path.parts)).absolute_path
        return None

    def parse(self, descriptor: Path) -> OivPackage:
        """Parse ``descriptor`` into an :class:`OivPackage`.

        Raises:
            ValidationError: When the descriptor cannot be parsed at all.
        """
        result = xml_tools.load_xml(descriptor)
        root = result.root
        metadata = root.find("metadata")
        content_root = descriptor.parent / "content"

        package = OivPackage(
            descriptor=descriptor,
            name=self._metadata_text(metadata, "name"),
            version=self._version(metadata),
            author=self._metadata_text(metadata, "author"),
            description=self._metadata_text(metadata, "description"),
            content_root=content_root if content_root.is_dir() else None,
            commands=self._parse_commands(root),
            repairs=result.repairs,
        )
        _LOGGER.info(
            "Parsed OIV package '%s': %d installable, %d OpenIV-only command(s)",
            package.display_name,
            len(package.installable_commands),
            len(package.archive_commands),
        )
        return package

    def try_parse(self, inventory: FileInventory) -> OivPackage | None:
        """Return the parsed package, or ``None`` when there is none/broken."""
        descriptor = self.find_descriptor(inventory)
        if descriptor is None:
            return None
        try:
            return self.parse(descriptor)
        except ValidationError as error:
            _LOGGER.warning("Could not read OIV descriptor %s: %s", descriptor, error)
            return None

    def _parse_commands(self, root: ElementTree.Element) -> tuple[OivCommand, ...]:
        """Return every command declared in the descriptor."""
        commands: list[OivCommand] = []
        for node in xml_tools.iter_elements(root, "add", "delete"):
            destination = node.get("source") if node.tag.lower() == "delete" else node.text
            declared = (destination or node.get("source") or "").strip()
            if not declared:
                continue
            target = PurePosixPath(declared.replace("\\", "/"))
            source_attribute = node.get("source")
            source = (
                PurePosixPath(source_attribute.replace("\\", "/"))
                if source_attribute and node.tag.lower() == "add"
                else None
            )
            commands.append(
                OivCommand(
                    source=source,
                    destination=target,
                    is_archive_target=self._targets_archive(target),
                    kind=node.tag.lower(),
                )
            )

        for node in xml_tools.iter_elements(root, "text", "xml"):
            declared = (node.get("path") or "").strip()
            if declared:
                target = PurePosixPath(declared.replace("\\", "/"))
                commands.append(
                    OivCommand(
                        source=None,
                        destination=target,
                        is_archive_target=self._targets_archive(target),
                        kind="xml",
                    )
                )
        return tuple(commands)

    @staticmethod
    def _targets_archive(destination: PurePosixPath) -> bool:
        """Return whether ``destination`` points inside an ``.rpf`` archive."""
        return any(
            part.lower().endswith(constants.PROTECTED_ARCHIVE_SUFFIX)
            for part in destination.parts
        )

    @staticmethod
    def _metadata_text(metadata: ElementTree.Element | None, tag: str) -> str:
        """Return a metadata field, tolerating localised ``<en>`` wrappers."""
        if metadata is None:
            return ""
        node = metadata.find(tag)
        if node is None:
            return ""
        english = node.find("en")
        if english is not None and (english.text or "").strip():
            return (english.text or "").strip()
        return (node.text or "").strip()

    @staticmethod
    def _version(metadata: ElementTree.Element | None) -> str:
        """Return the package version as ``major.minor``."""
        if metadata is None:
            return ""
        node = metadata.find("version")
        if node is None:
            return ""
        major = xml_tools.find_attribute(node, "major", "value") or xml_tools.find_text(
            node, "major"
        )
        minor = xml_tools.find_attribute(node, "minor", "value") or xml_tools.find_text(
            node, "minor"
        )
        if major and minor:
            return f"{major}.{minor}"
        return major or ""
