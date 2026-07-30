"""Rules recognising graphics mods: ReShade, ENB, timecycle and VisualSettings."""

from __future__ import annotations

from typing import Iterable

from gta_mod_manager.analyzer.context import AnalysisContext
from gta_mod_manager.analyzer.rule_base import AnalyzerRule, KeywordRule, RuleHit
from gta_mod_manager.models.enums import ModKind


class ReShadeRule(AnalyzerRule):
    """Votes for a graphics mod when ReShade artefacts are present."""

    rule_id = "graphics.reshade"
    display_name = "ReShade preset"

    _MARKER_FILES = ("reshade.ini", "reshade64.dll", "reshade32.dll")

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return votes for ReShade presets, shaders or binaries."""
        hits: list[RuleHit] = []
        if context.has_file(*self._MARKER_FILES) or context.has_directory(
            "reshade-shaders", "reshade-presets"
        ):
            hits.append(
                RuleHit(
                    kind=ModKind.GRAPHICS,
                    weight=0.85,
                    reason="Contains ReShade configuration or shaders",
                    tags=frozenset({"reshade", "root_install"}),
                )
            )
        if context.count_suffix(".fx", ".fxh"):
            hits.append(
                RuleHit(
                    kind=ModKind.GRAPHICS,
                    weight=0.5,
                    reason="Contains post-processing shader source files",
                    tags=frozenset({"reshade"}),
                )
            )
        preset_files = [
            item
            for item in context.files_with_suffix(".ini")
            if item.lower_name.startswith("reshadepreset")
        ]
        if preset_files:
            hits.append(
                RuleHit(
                    kind=ModKind.GRAPHICS,
                    weight=0.6,
                    reason=f"Contains {len(preset_files)} ReShade preset(s)",
                    tags=frozenset({"reshade", "root_install"}),
                )
            )
        return tuple(hits)


class EnbRule(AnalyzerRule):
    """Votes for a graphics mod when ENBSeries artefacts are present."""

    rule_id = "graphics.enb"
    display_name = "ENBSeries preset"

    _MARKER_FILES = ("enbseries.ini", "enblocal.ini", "enbhost.exe", "enbeffect.fx")

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return votes for ENB configuration files or folders."""
        markers = [name for name in self._MARKER_FILES if context.has_file(name)]
        hits: list[RuleHit] = []
        if markers:
            hits.append(
                RuleHit(
                    kind=ModKind.GRAPHICS,
                    weight=0.85,
                    reason="Contains ENBSeries configuration: " + ", ".join(markers),
                    tags=frozenset({"enb", "root_install"}),
                )
            )
        if context.has_directory("enbseries"):
            hits.append(
                RuleHit(
                    kind=ModKind.GRAPHICS,
                    weight=0.4,
                    reason="Uses the enbseries folder layout",
                    tags=frozenset({"enb", "root_install"}),
                )
            )
        return tuple(hits)


class TimecycleRule(AnalyzerRule):
    """Votes for a graphics mod when the game's visual data is replaced."""

    rule_id = "graphics.timecycle"
    display_name = "Timecycle / visual settings"

    _MARKER_FILES = (
        "visualsettings.dat",
        "timecycle_mods_1.xml",
        "timecycle_mods_2.xml",
        "w_clear.xml",
        "gta5.grass.sps",
    )

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return votes for timecycle or visual settings replacements."""
        markers = [name for name in self._MARKER_FILES if context.has_file(name)]
        if not markers and not context.has_directory("timecycle"):
            return ()
        return (
            RuleHit(
                kind=ModKind.GRAPHICS,
                weight=0.8,
                reason="Replaces the game's visual/timecycle data: "
                + (", ".join(markers) or "timecycle folder"),
                tags=frozenset({"graphics"}),
            ),
        )


class GraphicsKeywordRule(KeywordRule):
    """Reinforces a graphics verdict from well known preset names."""

    rule_id = "graphics.keywords"
    display_name = "Graphics naming"
    kind = ModKind.GRAPHICS
    base_weight = 0.2
    keywords = (
        "graphics",
        "visualv",
        "naturalvision",
        "quantv",
        "redux",
        "photorealistic",
        "gvm",
        "toolkit graphics",
        "enb",
        "reshade",
    )
