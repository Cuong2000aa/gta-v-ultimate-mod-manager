"""Rules recognising maps, weapons, peds, sounds and loose textures."""

from __future__ import annotations

from collections.abc import Iterable

from gta_mod_manager.analyzer.context import AnalysisContext
from gta_mod_manager.analyzer.rule_base import AnalyzerRule, RuleHit
from gta_mod_manager.core import constants
from gta_mod_manager.core.ped_assets import PED_META_FILES, ped_model_stems
from gta_mod_manager.models.enums import ModKind


class MapRule(AnalyzerRule):
    """Votes for a map mod based on map asset types and folder names."""

    rule_id = "world.map"
    display_name = "Map content"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return votes for ``.ymap``/``.ytyp`` content or map folders."""
        hits: list[RuleHit] = []
        ymap_count = context.count_suffix(".ymap")
        ytyp_count = context.count_suffix(".ytyp")

        if ymap_count:
            hits.append(
                RuleHit(
                    kind=ModKind.MAP,
                    weight=min(0.85, 0.5 + 0.05 * ymap_count),
                    reason=f"Contains {ymap_count} map placement file(s)",
                    tags=frozenset({"map"}),
                )
            )
        if ytyp_count:
            hits.append(
                RuleHit(
                    kind=ModKind.MAP,
                    weight=0.4,
                    reason=f"Contains {ytyp_count} archetype definition file(s)",
                )
            )
        if context.has_directory("dlc_mpmap", "custom_maps", "mapfiles"):
            hits.append(
                RuleHit(
                    kind=ModKind.MAP,
                    weight=0.3,
                    reason="Uses a map-specific folder layout",
                )
            )
        return tuple(hits)


class WeaponRule(AnalyzerRule):
    """Votes for a weapon mod based on weapon meta files and model names."""

    rule_id = "world.weapon"
    display_name = "Weapon content"

    _META_FILES = (
        "weapons.meta",
        "weaponcomponents.meta",
        "weaponarchetypes.meta",
        "weaponanimations.meta",
        "pedpersonality.meta",
    )

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return votes for weapon metadata or ``w_*`` model files."""
        hits: list[RuleHit] = []
        present = [name for name in self._META_FILES if context.has_file(name)]
        if present:
            hits.append(
                RuleHit(
                    kind=ModKind.WEAPON,
                    weight=0.8,
                    reason="Contains " + ", ".join(present),
                    tags=frozenset({"weapon"}),
                )
            )

        weapon_models = [
            item
            for item in context.files_with_suffix(".ydr", ".ytd")
            if item.lower_name.startswith("w_")
        ]
        if weapon_models:
            hits.append(
                RuleHit(
                    kind=ModKind.WEAPON,
                    weight=0.5,
                    reason=f"Contains {len(weapon_models)} weapon asset(s)",
                )
            )
        return tuple(hits)


class PedRule(AnalyzerRule):
    """Votes for a ped or character mod.

    A ped ships a ``.ydd`` drawable dictionary, which vehicles never use. When
    one is present the package is a character mod even if it also carries the
    ``.yft`` / ``.ytd`` files that normally point at a car.
    """

    rule_id = "world.ped"
    display_name = "Ped content"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return votes for ped metadata or character drawable files."""
        hits: list[RuleHit] = []
        present = sorted(name for name in PED_META_FILES if context.has_file(name))
        if present:
            hits.append(
                RuleHit(
                    kind=ModKind.PED,
                    weight=0.75,
                    reason="Contains " + ", ".join(present),
                    tags=frozenset({"ped"}),
                )
            )

        stems = ped_model_stems(item.lower_name for item in context.files)
        if not stems:
            return tuple(hits)

        names = ", ".join(sorted(stems)[:4])
        hits.append(
            RuleHit(
                kind=ModKind.PED,
                weight=min(0.8, 0.35 + 0.15 * len(stems)),
                reason=f"Contains {len(stems)} character model set(s): {names}",
                tags=frozenset({"ped"}),
            )
        )
        if not context.has_file(*constants.VEHICLE_META_FILES):
            hits.append(
                RuleHit(
                    kind=ModKind.VEHICLE_REPLACE,
                    weight=-0.6,
                    reason="Character drawables present and no vehicle metadata",
                )
            )
        return tuple(hits)


class SoundRule(AnalyzerRule):
    """Votes for an audio mod based on audio containers and folders."""

    rule_id = "world.sound"
    display_name = "Audio content"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return votes for ``.awc`` packs, ``dat54`` files or audio folders."""
        hits: list[RuleHit] = []
        awc_count = context.count_suffix(".awc")
        if awc_count:
            hits.append(
                RuleHit(
                    kind=ModKind.SOUND,
                    weight=min(0.85, 0.55 + 0.05 * awc_count),
                    reason=f"Contains {awc_count} audio wave container(s)",
                    tags=frozenset({"audio"}),
                )
            )
        if context.contains_keyword(".dat54", ".dat10", "sfx/", "audio/sfx"):
            hits.append(
                RuleHit(
                    kind=ModKind.SOUND,
                    weight=0.5,
                    reason="Contains game audio metadata",
                )
            )
        if context.has_directory("audio", "sfx"):
            hits.append(
                RuleHit(kind=ModKind.SOUND, weight=0.25, reason="Uses an audio folder layout")
            )
        return tuple(hits)


class TextureOnlyRule(AnalyzerRule):
    """Votes for a texture pack when the package holds only ``.ytd`` files.

    This is the fallback that keeps retexture packs out of ``UNKNOWN``.
    """

    rule_id = "world.texture_only"
    display_name = "Texture pack"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return a vote when texture dictionaries dominate the package."""
        textures = context.count_suffix(".ytd")
        if textures == 0:
            return ()
        other_assets = context.game_asset_count - textures
        if other_assets > 0:
            return ()
        return (
            RuleHit(
                kind=ModKind.TEXTURE,
                weight=0.6,
                reason=f"Contains only texture dictionaries ({textures} file(s))",
                tags=frozenset({"texture"}),
            ),
        )
