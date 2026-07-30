"""Tests for the analyzer engine and the GTA V rule set."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Iterable

from gta_mod_manager.analyzer.context import AnalysisContext
from gta_mod_manager.analyzer.engine import ModAnalyzer
from gta_mod_manager.analyzer.rule_base import AnalyzerRule, RuleHit
from gta_mod_manager.models.enums import ModKind
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.plugins.gta_v.plugin import GtaVPlugin


def _inventory(tmp_path: Path, files: dict[str, str | bytes]) -> FileInventory:
    """Materialise ``files`` on disk and return their inventory."""
    entries: list[ModFile] = []
    for relative, content in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
        entries.append(
            ModFile(
                absolute_path=target,
                relative_path=PurePosixPath(relative),
                size_bytes=target.stat().st_size,
            )
        )
    return FileInventory(root=tmp_path, files=tuple(entries))


def _analyzer() -> ModAnalyzer:
    """Return an analyzer using the GTA V rule set."""
    return ModAnalyzer(GtaVPlugin().analyzer_rules())


class BrokenRule(AnalyzerRule):
    """A rule that raises, to prove failures are contained."""

    rule_id = "test.broken"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Always fail."""
        raise RuntimeError("rule exploded")


def test_an_addon_pack_is_recognised(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "adder2/setup2.xml": "<SSetupData><deviceName>dlc_adder2</deviceName></SSetupData>",
            "adder2/content.xml": "<CDataFileMgr__ContentsOfDataFileXml/>",
            "adder2/dlc.rpf": b"payload",
        },
    )

    classification = _analyzer().analyze(inventory, "Adder2 Addon.zip")

    assert classification.primary is ModKind.VEHICLE_ADDON
    assert classification.is_reliable


def test_a_replacement_vehicle_is_recognised(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "adder.yft": b"asset",
            "adder_hi.yft": b"asset",
            "adder.ytd": b"asset",
            "vehicles.meta": "<CVehicleModelInfo__InitDataList/>",
            "handling.meta": "<CHandlingDataMgr/>",
        },
    )

    classification = _analyzer().analyze(inventory, "Adder Retextured.zip")

    assert classification.primary is ModKind.VEHICLE_REPLACE


def test_an_asi_plugin_is_recognised(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path, {"SuperPlugin.asi": b"MZ", "SuperPlugin.ini": "[Keys]\nMenu=F4\n"}
    )

    classification = _analyzer().analyze(inventory, "SuperPlugin.zip")

    assert classification.primary in (ModKind.ASI, ModKind.TRAINER)


def test_a_dotnet_script_is_recognised(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "scripts/Cool.dll": b"MZ",
            "scripts/Cool.cs": "using GTA;\npublic class Cool : Script {}\n",
        },
    )

    classification = _analyzer().analyze(inventory, "Cool Script.zip")

    assert classification.primary is ModKind.SCRIPT_HOOK_DOTNET
    assert "requires_shvdn" in classification.tags


def test_an_openiv_package_wins_over_its_content(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        {
            "assembly.xml": "<package><content><add source='x'/></content></package>",
            "content/adder.yft": b"asset",
            "content/vehicles.meta": "<CVehicleModelInfo__InitDataList/>",
        },
    )

    classification = _analyzer().analyze(inventory, "Vehicle.oiv")

    assert classification.primary is ModKind.OPENIV_PACKAGE


def test_an_empty_package_stays_unknown(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, {"notes.bin": b"\x00\x01"})

    classification = _analyzer().analyze(inventory, "Mystery.zip")

    assert classification.primary is ModKind.UNKNOWN
    assert not classification.is_reliable


def test_a_broken_rule_does_not_abort_the_analysis(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, {"SuperPlugin.asi": b"MZ"})
    analyzer = ModAnalyzer((BrokenRule(), *GtaVPlugin().analyzer_rules()))

    classification = analyzer.analyze(inventory, "SuperPlugin.zip")

    assert classification.primary is not ModKind.UNKNOWN


def test_detailed_analysis_exposes_every_vote(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path, {"adder2/setup2.xml": "<SSetupData/>", "adder2/dlc.rpf": b"payload"}
    )

    result = _analyzer().analyze_detailed(inventory, "Adder2.zip")

    assert result.hits
    assert all(hit.rule_id for hit in result.hits)


def test_the_context_caches_text_reads(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, {"readme.txt": "Requires ScriptHookVDotNet"})
    context = AnalysisContext(inventory=inventory, source_name="Mod.zip")
    file = inventory.files[0]

    first = context.read_text(file)
    file.absolute_path.write_text("changed", encoding="utf-8")

    assert context.read_text(file) == first
    assert "scripthookvdotnet" in first
