"""Validates and repairs the XML documents a mod package ships."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.exceptions import ValidationError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.mod_file import FileInventory
from gta_mod_manager.utils import xml_tools

_LOGGER = get_logger("validator.xml")

#: Documents whose structure the validator understands well enough to check.
_KNOWN_ROOTS: dict[str, tuple[str, ...]] = {
    constants.VEHICLES_META: ("CVehicleModelInfo__InitDataList",),
    constants.HANDLING_META: ("CHandlingDataMgr",),
    constants.CARVARIATIONS_META: ("CVehicleModelInfoVariation",),
    constants.CARCOLS_META: ("CVehicleModelInfoVarGlobal",),
    constants.CONTENT_XML: ("CDataFileMgr__ContentsOfDataFileXml", "SMandatoryPacksData"),
    constants.SETUP2_XML: ("SSetupData",),
}


@dataclass(frozen=True, slots=True)
class XmlFileReport:
    """Validation outcome for one XML document."""

    path: Path
    is_parseable: bool
    repairs: tuple[str, ...] = field(default_factory=tuple)
    error: str | None = None
    unexpected_root: str | None = None

    @property
    def needs_repair(self) -> bool:
        """Return whether the document had to be repaired to parse."""
        return bool(self.repairs)


@dataclass(frozen=True, slots=True)
class XmlValidationReport:
    """Aggregated XML validation outcome for one package."""

    files: tuple[XmlFileReport, ...] = field(default_factory=tuple)

    @property
    def broken(self) -> tuple[XmlFileReport, ...]:
        """Return the documents that could not be parsed at all."""
        return tuple(item for item in self.files if not item.is_parseable)

    @property
    def repaired(self) -> tuple[XmlFileReport, ...]:
        """Return the documents that needed repairs."""
        return tuple(item for item in self.files if item.needs_repair)

    @property
    def is_clean(self) -> bool:
        """Return whether every document parsed without repairs."""
        return not self.broken and not self.repaired


class XmlValidator:
    """Parses every XML/meta document of a package and reports its state."""

    def validate(self, inventory: FileInventory) -> XmlValidationReport:
        """Return the validation report for every XML document in ``inventory``."""
        reports: list[XmlFileReport] = []
        for file in inventory.by_suffix(".xml", ".meta"):
            reports.append(self._validate_file(file.absolute_path))
        report = XmlValidationReport(files=tuple(reports))
        if report.broken:
            _LOGGER.warning(
                "%d XML document(s) could not be parsed", len(report.broken)
            )
        return report

    def repair_in_place(self, inventory: FileInventory) -> tuple[Path, ...]:
        """Rewrite every repairable document and return the repaired paths.

        Repairs happen inside the temporary extraction workspace, never in the
        game folder, so a bad repair can be thrown away by deleting the
        workspace.
        """
        repaired: list[Path] = []
        for file in inventory.by_suffix(".xml", ".meta"):
            try:
                result = xml_tools.load_xml(file.absolute_path)
            except ValidationError:
                continue
            if not result.was_repaired:
                continue
            xml_tools.save_xml(file.absolute_path, result.root)
            repaired.append(file.absolute_path)
        if repaired:
            _LOGGER.info("Repaired %d XML document(s) in the workspace", len(repaired))
        return tuple(repaired)

    @staticmethod
    def _validate_file(path: Path) -> XmlFileReport:
        """Validate one document."""
        try:
            result = xml_tools.load_xml(path)
        except ValidationError as error:
            return XmlFileReport(path=path, is_parseable=False, error=str(error))

        expected = _KNOWN_ROOTS.get(path.name.lower())
        unexpected = None
        if expected and result.root.tag not in expected:
            unexpected = result.root.tag
        return XmlFileReport(
            path=path,
            is_parseable=True,
            repairs=result.repairs,
            unexpected_root=unexpected,
        )
