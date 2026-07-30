"""The rule set used by the smart mod analyzer.

Rules are deliberately small and independent. Registering a new heuristic is a
matter of writing a class and adding it to :func:`default_rules`.
"""

from gta_mod_manager.analyzer.rule_base import AnalyzerRule
from gta_mod_manager.analyzer.rules.graphics_rules import (
    EnbRule,
    GraphicsKeywordRule,
    ReShadeRule,
    TimecycleRule,
)
from gta_mod_manager.analyzer.rules.package_rules import (
    GameConfigRule,
    LmlPackageRule,
    OpenIvPackageRule,
    RpfArchiveRule,
)
from gta_mod_manager.analyzer.rules.script_rules import (
    AsiPluginRule,
    DotNetScriptRule,
    LuaScriptRule,
    MenyooRule,
    TrainerRule,
    ZombieRule,
)
from gta_mod_manager.analyzer.rules.vehicle_rules import (
    AddonVehicleRule,
    ReplaceLayoutRule,
    VehicleAssetRule,
    VehicleMetaRule,
)
from gta_mod_manager.analyzer.rules.world_rules import (
    MapRule,
    PedRule,
    SoundRule,
    TextureOnlyRule,
    WeaponRule,
)

__all__ = [
    "AddonVehicleRule",
    "AsiPluginRule",
    "DotNetScriptRule",
    "EnbRule",
    "GameConfigRule",
    "GraphicsKeywordRule",
    "LmlPackageRule",
    "LuaScriptRule",
    "MapRule",
    "MenyooRule",
    "OpenIvPackageRule",
    "PedRule",
    "ReShadeRule",
    "ReplaceLayoutRule",
    "RpfArchiveRule",
    "SoundRule",
    "TextureOnlyRule",
    "TimecycleRule",
    "TrainerRule",
    "VehicleAssetRule",
    "VehicleMetaRule",
    "WeaponRule",
    "ZombieRule",
    "default_rules",
]


def default_rules() -> tuple[AnalyzerRule, ...]:
    """Return every rule the analyzer runs by default."""
    return (
        OpenIvPackageRule(),
        LmlPackageRule(),
        GameConfigRule(),
        RpfArchiveRule(),
        AddonVehicleRule(),
        VehicleMetaRule(),
        VehicleAssetRule(),
        ReplaceLayoutRule(),
        AsiPluginRule(),
        DotNetScriptRule(),
        LuaScriptRule(),
        MenyooRule(),
        TrainerRule(),
        ZombieRule(),
        MapRule(),
        WeaponRule(),
        PedRule(),
        SoundRule(),
        TextureOnlyRule(),
        ReShadeRule(),
        EnbRule(),
        TimecycleRule(),
        GraphicsKeywordRule(),
    )
