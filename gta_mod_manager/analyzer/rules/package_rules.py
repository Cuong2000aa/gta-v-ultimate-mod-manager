"""Rules recognising container formats: OpenIV packages and LML packages."""

from __future__ import annotations

from typing import Iterable

from gta_mod_manager.analyzer.context import AnalysisContext
from gta_mod_manager.analyzer.rule_base import AnalyzerRule, RuleHit
from gta_mod_manager.core import constants
from gta_mod_manager.models.enums import ModKind


class OpenIvPackageRule(AnalyzerRule):
    """Votes for an OpenIV package.

    An ``.oiv`` file is a zip containing ``assembly.xml`` (newer) or
    ``package.xml`` (older) plus a ``content`` folder. The scanner already
    unpacked it, so the descriptor is what identifies the package.
    """

    rule_id = "package.oiv"
    display_name = "OpenIV package"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return votes for OIV descriptors or a source ``.oiv`` archive."""
        hits: list[RuleHit] = []
        descriptors = [
            name
            for name in (constants.ASSEMBLY_XML, constants.PACKAGE_XML)
            if context.has_file(name)
        ]
        if descriptors:
            hits.append(
                RuleHit(
                    kind=ModKind.OPENIV_PACKAGE,
                    weight=0.9,
                    reason="Contains an OpenIV package descriptor: "
                    + ", ".join(descriptors),
                    tags=frozenset({"oiv", "requires_openiv_rules"}),
                )
            )
        if context.source_name.lower().endswith(constants.OIV_EXTENSION):
            hits.append(
                RuleHit(
                    kind=ModKind.OPENIV_PACKAGE,
                    weight=0.7,
                    reason="Source file is an .oiv package",
                    tags=frozenset({"oiv"}),
                )
            )
        return tuple(hits)


class LmlPackageRule(AnalyzerRule):
    """Votes for a Lenny's Mod Loader package."""

    rule_id = "package.lml"
    display_name = "LML package"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return votes for LML descriptors or the ``lml`` folder layout."""
        hits: list[RuleHit] = []
        if context.has_file("install.xml") and context.has_directory("lml"):
            hits.append(
                RuleHit(
                    kind=ModKind.LML,
                    weight=0.9,
                    reason="Contains an LML install.xml inside an lml folder",
                    tags=frozenset({"lml", "requires_lml"}),
                )
            )
        elif context.has_directory(constants.LML_FOLDER_NAME):
            hits.append(
                RuleHit(
                    kind=ModKind.LML,
                    weight=0.55,
                    reason="Uses the lml folder layout",
                    tags=frozenset({"lml", "requires_lml"}),
                )
            )
        if context.has_suffix(".lml"):
            hits.append(
                RuleHit(
                    kind=ModKind.LML,
                    weight=0.5,
                    reason="Contains .lml descriptor file(s)",
                    tags=frozenset({"lml"}),
                )
            )
        return tuple(hits)


class GameConfigRule(AnalyzerRule):
    """Detects a ``gameconfig.xml`` replacement, which conflicts easily."""

    rule_id = "package.gameconfig"
    display_name = "GameConfig replacement"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return a vote when the package replaces ``gameconfig.xml``."""
        if not context.has_file(constants.GAMECONFIG_XML):
            return ()
        return (
            RuleHit(
                kind=ModKind.UNKNOWN,
                weight=0.0,
                reason="Replaces gameconfig.xml",
                tags=frozenset({"gameconfig", "high_conflict_risk"}),
            ),
        )


class RpfArchiveRule(AnalyzerRule):
    """Flags packages that ship prebuilt ``.rpf`` archives.

    Such packages usually expect the user to drop the archive into ``mods``
    with OpenIV; the manager can do that safely, but the fact is worth
    surfacing in the preview.
    """

    rule_id = "package.rpf"
    display_name = "Prebuilt RPF archive"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return a neutral hit carrying the ``rpf_payload`` tag."""
        rpf_count = context.count_suffix(".rpf")
        if rpf_count == 0:
            return ()
        return (
            RuleHit(
                kind=ModKind.UNKNOWN,
                weight=0.0,
                reason=f"Ships {rpf_count} prebuilt .rpf archive(s)",
                tags=frozenset({"rpf_payload"}),
            ),
        )
