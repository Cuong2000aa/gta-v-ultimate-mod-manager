"""Rules recognising scripts, ASI plugins, trainers and Menyoo content."""

from __future__ import annotations

from collections.abc import Iterable

from gta_mod_manager.analyzer.context import AnalysisContext
from gta_mod_manager.analyzer.rule_base import AnalyzerRule, KeywordRule, RuleHit
from gta_mod_manager.core import constants
from gta_mod_manager.core.script_assets import (
    LOADER_ASSEMBLY_NAMES,
    is_script_assembly,
    script_library_tags,
)
from gta_mod_manager.models.enums import ModKind

#: Symbols that only appear in ScriptHookVDotNet source files.
_SHVDN_MARKERS = ("using gta", "scripthookvdotnet", "gta.script", "gta.ui", "scriptsettings")

#: Binaries that must never be treated as user scripts. ``NativeUI`` is a
#: shared menu library, so on its own it does not make a package a script mod.
_LOADER_BINARIES = LOADER_ASSEMBLY_NAMES | {"nativeui.dll"}


class AsiPluginRule(AnalyzerRule):
    """Votes for an ASI plugin when ``.asi`` binaries are present."""

    rule_id = "script.asi"
    display_name = "ASI plugin"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return a vote for every ``.asi`` file that is not a known loader."""
        asi_files = [
            item for item in context.files_with_suffix(".asi")
            if item.lower_name not in _LOADER_BINARIES
        ]
        if not asi_files:
            return ()
        return (
            RuleHit(
                kind=ModKind.ASI,
                weight=0.75,
                reason=f"Contains ASI plugin(s): {', '.join(item.name for item in asi_files[:3])}",
                tags=frozenset({"requires_asi_loader", "root_install"}),
            ),
        )


class DotNetScriptRule(AnalyzerRule):
    """Votes for a ScriptHookVDotNet script.

    Source files (``.cs``/``.vb``) are decisive. A ``.dll`` only counts when it
    sits in a ``scripts`` folder, because plain managed assemblies are also
    shipped as dependencies.
    """

    rule_id = "script.shvdn"
    display_name = "ScriptHookVDotNet script"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return votes for .NET script content."""
        hits: list[RuleHit] = []
        sources = context.files_with_suffix(".cs", ".vb")
        if sources:
            hits.append(
                RuleHit(
                    kind=ModKind.SCRIPT_HOOK_DOTNET,
                    weight=0.8,
                    reason=f"Contains {len(sources)} C#/VB script source file(s)",
                    tags=frozenset({"requires_shvdn", "scripts_install"}),
                )
            )
        elif context.any_text_contains((".cs", ".vb"), *_SHVDN_MARKERS):
            hits.append(
                RuleHit(
                    kind=ModKind.SCRIPT_HOOK_DOTNET,
                    weight=0.6,
                    reason="Source code references the ScriptHookVDotNet API",
                    tags=frozenset({"requires_shvdn"}),
                )
            )

        candidates = [
            item
            for item in context.files_with_suffix(".dll")
            if item.lower_name not in _LOADER_BINARIES
        ]
        libraries: set[str] = set()
        for item in candidates:
            libraries |= script_library_tags(item.absolute_path, item.lower_name)

        in_scripts_folder = [
            item
            for item in candidates
            if constants.SCRIPTS_FOLDER_NAME in item.parts_lower[:-1]
        ]
        if in_scripts_folder:
            hits.append(
                RuleHit(
                    kind=ModKind.SCRIPT_HOOK_DOTNET,
                    weight=0.55,
                    reason="Ships compiled script assemblies in a scripts folder",
                    tags=frozenset({"requires_shvdn", "scripts_install"}) | libraries,
                )
            )
        else:
            # A bare .dll at the archive root is only a script when its
            # metadata references ScriptHookVDotNet.
            assemblies = [
                item
                for item in candidates
                if is_script_assembly(item.absolute_path, item.lower_name)
            ]
            if assemblies:
                names = ", ".join(item.name for item in assemblies[:3])
                hits.append(
                    RuleHit(
                        kind=ModKind.SCRIPT_HOOK_DOTNET,
                        weight=0.55,
                        reason=f"Ships ScriptHookVDotNet assembly(ies): {names}",
                        tags=frozenset({"requires_shvdn", "scripts_install"}) | libraries,
                    )
                )
        return tuple(hits)


class LuaScriptRule(AnalyzerRule):
    """Votes for a generic script mod when Lua files are present."""

    rule_id = "script.lua"
    display_name = "Lua script"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return a vote when ``.lua`` files exist."""
        count = context.count_suffix(".lua")
        if count == 0:
            return ()
        return (
            RuleHit(
                kind=ModKind.SCRIPT,
                weight=0.7,
                reason=f"Contains {count} Lua script(s)",
                tags=frozenset({"requires_lua_plugin", "scripts_install"}),
            ),
        )


class MenyooRule(AnalyzerRule):
    """Votes for Menyoo content, which is a saved map rather than a script."""

    rule_id = "script.menyoo"
    display_name = "Menyoo content"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return votes for Menyoo spooner files or the Menyoo folder layout."""
        hits: list[RuleHit] = []
        if context.has_directory("menyoostuff"):
            hits.append(
                RuleHit(
                    kind=ModKind.MENYOO,
                    weight=0.85,
                    reason="Uses the menyooStuff folder layout",
                    tags=frozenset({"requires_menyoo", "root_install"}),
                )
            )
        if context.any_text_contains((".xml",), "<spoonerplacements", "menyoo"):
            hits.append(
                RuleHit(
                    kind=ModKind.MENYOO,
                    weight=0.8,
                    reason="Contains a Menyoo spooner placement file",
                    tags=frozenset({"requires_menyoo"}),
                )
            )
        return tuple(hits)


class TrainerRule(KeywordRule):
    """Votes for a trainer based on well known trainer names."""

    rule_id = "script.trainer"
    display_name = "Trainer"
    kind = ModKind.TRAINER
    base_weight = 0.3
    keywords = (
        "trainer",
        "simple trainer",
        "enhanced native trainer",
        "menyoo",
        "lambda menu",
        "map editor",
    )


class ZombieRule(KeywordRule):
    """Votes for a zombie/overhaul mod based on naming."""

    rule_id = "script.zombie"
    display_name = "Zombie overhaul"
    kind = ModKind.ZOMBIE
    base_weight = 0.35
    keywords = ("zombie", "apocalypse", "outbreak", "infected", "undead")
