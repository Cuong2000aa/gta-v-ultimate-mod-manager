"""Rules recognising vehicle mods and telling replace from add-on apart."""

from __future__ import annotations

from collections.abc import Iterable

from gta_mod_manager.analyzer.context import AnalysisContext
from gta_mod_manager.analyzer.rule_base import AnalyzerRule, RuleHit
from gta_mod_manager.core import constants
from gta_mod_manager.core.ped_assets import is_ped_asset, ped_model_stems
from gta_mod_manager.models.enums import ModKind

#: Model prefixes GTA V uses for vehicle assets.
_VEHICLE_ASSET_SUFFIXES = (".yft", ".ytd")


class VehicleMetaRule(AnalyzerRule):
    """Votes for a vehicle mod when vehicle meta files are present."""

    rule_id = "vehicle.meta"
    display_name = "Vehicle metadata"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return votes based on which vehicle meta files exist."""
        hits: list[RuleHit] = []
        present = [name for name in constants.VEHICLE_META_FILES if context.has_file(name)]
        if not present:
            return ()

        weight = 0.55 if constants.VEHICLES_META in present else 0.35
        hits.append(
            RuleHit(
                kind=ModKind.VEHICLE_REPLACE,
                weight=weight,
                reason="Contains " + ", ".join(sorted(present)),
                tags=frozenset({"vehicle"}),
            )
        )

        if context.has_file(constants.HANDLING_META):
            hits.append(
                RuleHit(
                    kind=ModKind.VEHICLE_REPLACE,
                    weight=0.2,
                    reason="Ships custom handling data",
                )
            )
        return tuple(hits)


class VehicleAssetRule(AnalyzerRule):
    """Votes for a vehicle mod when ``.yft`` model files are present."""

    rule_id = "vehicle.assets"
    display_name = "Vehicle model files"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return a vote proportional to the number of vehicle assets."""
        ped_stems = ped_model_stems(item.lower_name for item in context.files)
        model_count = sum(
            1
            for item in context.files_with_suffix(".yft")
            if not is_ped_asset(item.lower_name, ped_stems)
        )
        if model_count == 0:
            return ()
        weight = min(0.45, 0.15 + 0.05 * model_count)
        return (
            RuleHit(
                kind=ModKind.VEHICLE_REPLACE,
                weight=weight,
                reason=f"Contains {model_count} vehicle model file(s)",
                tags=frozenset({"vehicle"}),
            ),
        )


class AddonVehicleRule(AnalyzerRule):
    """Distinguishes an add-on DLC pack from a plain replacement.

    An add-on ships its own ``dlc.rpf`` layout: ``content.xml`` plus
    ``setup2.xml``. Those two files are the definitive signal, so this rule
    votes strongly for :attr:`ModKind.VEHICLE_ADDON` and vetoes
    :attr:`ModKind.VEHICLE_REPLACE` — unless the archive also ships a
    ``Replace`` folder, in which case Replace wins.
    """

    rule_id = "vehicle.addon"
    display_name = "Add-on DLC pack"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return add-on votes when DLC pack descriptors are present."""
        has_content = context.has_file(constants.CONTENT_XML)
        has_setup = context.has_file(constants.SETUP2_XML)
        has_dlc_rpf = context.has_file("dlc.rpf") or context.has_directory("dlcpacks")
        has_replace_folder = context.has_directory(
            "replace", "replacement", "repace", "rep"
        )
        has_addon_folder = context.has_directory("addon", "add-on", "add_on", "add on")

        if not (has_content or has_setup or has_dlc_rpf):
            return ()

        signals = [
            name
            for name, present in (
                (constants.CONTENT_XML, has_content),
                (constants.SETUP2_XML, has_setup),
                ("dlc.rpf / dlcpacks", has_dlc_rpf),
            )
            if present
        ]
        weight = {1: 0.35, 2: 0.7, 3: 0.9}[len(signals)]

        hits = [
            RuleHit(
                kind=ModKind.VEHICLE_ADDON,
                weight=weight,
                reason="Add-on DLC pack detected: " + ", ".join(signals),
                tags=frozenset({"addon", "requires_dlclist"}),
            )
        ]
        if has_addon_folder and has_replace_folder:
            hits.append(
                RuleHit(
                    kind=ModKind.VEHICLE_REPLACE,
                    weight=0.55,
                    reason="Package also ships a Replace folder; Replace is preferred",
                    tags=frozenset({"prefer_replace"}),
                )
            )
            hits.append(
                RuleHit(
                    kind=ModKind.VEHICLE_ADDON,
                    weight=-0.45,
                    reason="Replace folder present; Add-On half is secondary",
                )
            )
        elif has_content and has_setup:
            hits.append(
                RuleHit(
                    kind=ModKind.VEHICLE_REPLACE,
                    weight=-0.6,
                    reason="Ships its own DLC pack, so it is not a replacement",
                )
            )
        return tuple(hits)


class ReplaceLayoutRule(AnalyzerRule):
    """Votes for a replacement when the package mirrors ``mods/update``."""

    rule_id = "vehicle.replace_layout"
    display_name = "Replacement folder layout"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return a vote when the package uses the vanilla folder structure."""
        if not context.is_mods_folder_layout:
            return ()
        ped_stems = ped_model_stems(item.lower_name for item in context.files)
        if not any(
            not is_ped_asset(item.lower_name, ped_stems)
            for item in context.files_with_suffix(*_VEHICLE_ASSET_SUFFIXES)
        ):
            return ()
        return (
            RuleHit(
                kind=ModKind.VEHICLE_REPLACE,
                weight=0.3,
                reason="Folder layout mirrors the game's own vehicle paths",
                tags=frozenset({"mods_layout"}),
            ),
        )
