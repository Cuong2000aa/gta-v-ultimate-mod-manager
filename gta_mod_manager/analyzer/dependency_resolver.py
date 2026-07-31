"""Derives the components a classified package needs in order to work."""

from __future__ import annotations

from gta_mod_manager.core import constants
from gta_mod_manager.models.classification import ModClassification
from gta_mod_manager.models.component import ComponentReport
from gta_mod_manager.models.enums import ModKind
from gta_mod_manager.models.mod_package import DependencyRef

#: Dependencies implied by a classification tag.
_TAG_DEPENDENCIES: dict[str, DependencyRef] = {
    "requires_asi_loader": DependencyRef(
        component_id=constants.COMPONENT_ASI_LOADER,
        display_name="ASI Loader (dinput8.dll)",
        reason="ASI plugins are loaded by the ASI loader",
    ),
    "requires_shvdn": DependencyRef(
        component_id=constants.COMPONENT_SCRIPT_HOOK_V_DOTNET,
        display_name="ScriptHookVDotNet",
        reason="C#/VB scripts run inside ScriptHookVDotNet",
    ),
    "requires_nativeui": DependencyRef(
        component_id=constants.COMPONENT_NATIVE_UI,
        display_name="NativeUI",
        reason="The script draws its menu with the NativeUI library",
    ),
    "requires_menyoo": DependencyRef(
        component_id=constants.COMPONENT_MENYOO,
        display_name="Menyoo Trainer",
        reason="Menyoo maps are loaded by the Menyoo trainer",
    ),
    "requires_lml": DependencyRef(
        component_id=constants.COMPONENT_LML,
        display_name="Lenny's Mod Loader",
        reason="LML packages are loaded by Lenny's Mod Loader",
    ),
    "requires_openiv_rules": DependencyRef(
        component_id=constants.COMPONENT_OPENIV_ASI,
        display_name="OpenIV.asi",
        reason="OpenIV packages install into the mods folder, which needs OpenIV.asi",
    ),
    "requires_dlclist": DependencyRef(
        component_id=constants.COMPONENT_PACKFILE_LIMIT_ADJUSTER,
        display_name="Packfile Limit Adjuster",
        optional=True,
        reason="Add-on DLC packs raise the packfile count",
    ),
    "requires_lua_plugin": DependencyRef(
        component_id="lua_plugin",
        display_name="Lua Plugin for GTA V",
        reason="Lua scripts need the Lua plugin",
    ),
}

#: Dependencies implied by the winning category.
_KIND_DEPENDENCIES: dict[ModKind, tuple[str, ...]] = {
    ModKind.ASI: ("requires_asi_loader",),
    ModKind.SCRIPT_HOOK_DOTNET: ("requires_shvdn", "requires_asi_loader"),
    ModKind.MENYOO: ("requires_menyoo",),
    ModKind.LML: ("requires_lml",),
    ModKind.OPENIV_PACKAGE: ("requires_openiv_rules",),
    ModKind.VEHICLE_ADDON: ("requires_openiv_rules", "requires_dlclist"),
    ModKind.VEHICLE_REPLACE: ("requires_openiv_rules",),
    ModKind.MAP: ("requires_openiv_rules", "requires_dlclist"),
    ModKind.WEAPON: ("requires_openiv_rules", "requires_dlclist"),
    ModKind.TRAINER: ("requires_asi_loader",),
}

#: ScriptHookV underpins every ASI-based component.
_SCRIPT_HOOK_DEPENDENCY = DependencyRef(
    component_id=constants.COMPONENT_SCRIPT_HOOK_V,
    display_name="ScriptHookV",
    reason="Required by the ASI loader and every native script",
)


class DependencyResolver:
    """Maps a classification onto the components it depends on."""

    def resolve(self, classification: ModClassification) -> tuple[DependencyRef, ...]:
        """Return the dependencies implied by ``classification``."""
        keys: list[str] = list(_KIND_DEPENDENCIES.get(classification.primary, ()))
        keys.extend(tag for tag in classification.tags if tag in _TAG_DEPENDENCIES)

        resolved: dict[str, DependencyRef] = {}
        for key in keys:
            dependency = _TAG_DEPENDENCIES.get(key)
            if dependency is not None:
                resolved.setdefault(dependency.component_id, dependency)

        if any(
            key in ("requires_asi_loader", "requires_shvdn", "requires_menyoo") for key in keys
        ):
            resolved.setdefault(_SCRIPT_HOOK_DEPENDENCY.component_id, _SCRIPT_HOOK_DEPENDENCY)

        return tuple(resolved.values())

    def unmet(
        self, dependencies: tuple[DependencyRef, ...], report: ComponentReport
    ) -> tuple[DependencyRef, ...]:
        """Return the dependencies that ``report`` shows as not installed."""
        return tuple(
            dependency
            for dependency in dependencies
            if not report.has(dependency.component_id)
        )
