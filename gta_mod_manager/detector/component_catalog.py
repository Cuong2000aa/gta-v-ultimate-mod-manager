"""Declarative catalogue of the components the detector looks for.

Adding support for a new tool means adding one :class:`ComponentProbe` here;
no detector code has to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gta_mod_manager.core import constants
from gta_mod_manager.models.component import ComponentSpec


@dataclass(frozen=True, slots=True)
class ComponentProbe:
    """How to recognise one component inside a game installation.

    Attributes:
        spec: Static description shown in the dashboard.
        root_files: File names, relative to the game root, that prove presence.
        root_directories: Folder names that prove presence.
        mods_files: Files searched relative to the ``mods`` folder.
        version_from: Which of :attr:`root_files` carries the file version.
        require_all: Require every listed entry instead of just one.
    """

    spec: ComponentSpec
    root_files: tuple[str, ...] = field(default_factory=tuple)
    root_directories: tuple[str, ...] = field(default_factory=tuple)
    mods_files: tuple[str, ...] = field(default_factory=tuple)
    version_from: str | None = None
    require_all: bool = False


def default_catalog() -> tuple[ComponentProbe, ...]:
    """Return the probes for every component the application understands."""
    return (
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_SCRIPT_HOOK_V,
                display_name="ScriptHookV",
                required_by=("ASI plugins", "Trainers", "ScriptHookVDotNet"),
                homepage="http://www.dev-c.com/gtav/scripthookv/",
                is_essential=True,
            ),
            root_files=("ScriptHookV.dll",),
            version_from="ScriptHookV.dll",
        ),
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_ASI_LOADER,
                display_name="ASI Loader (dinput8.dll)",
                required_by=("ASI plugins",),
                homepage="http://www.dev-c.com/gtav/scripthookv/",
                is_essential=True,
            ),
            root_files=("dinput8.dll",),
            version_from="dinput8.dll",
        ),
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_SCRIPT_HOOK_V_DOTNET,
                display_name="ScriptHookVDotNet",
                required_by=("C# scripts",),
                homepage="https://github.com/scripthookvdotnet/scripthookvdotnet",
            ),
            root_files=(
                "ScriptHookVDotNet.asi",
                "ScriptHookVDotNet2.dll",
                "ScriptHookVDotNet3.dll",
            ),
            version_from="ScriptHookVDotNet3.dll",
        ),
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_OPENIV_ASI,
                display_name="OpenIV.asi",
                required_by=("mods folder", "OpenIV packages"),
                homepage="https://openiv.com/",
                is_essential=True,
            ),
            root_files=("OpenIV.asi",),
        ),
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_PACKFILE_LIMIT_ADJUSTER,
                display_name="Packfile Limit Adjuster",
                required_by=("Add-on vehicles", "Map mods"),
                homepage="https://www.gta5-mods.com/tools/packfile-limit-adjuster",
            ),
            root_files=("PackfileLimitAdjuster.asi",),
        ),
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_HEAP_ADJUSTER,
                display_name="Heap Adjuster",
                required_by=("Large mod setups",),
                homepage="https://www.gta5-mods.com/tools/heap-adjuster",
            ),
            root_files=("GTAVHeapAdjuster.asi", "HeapAdjuster.asi"),
        ),
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_GAMECONFIG,
                display_name="Custom gameconfig.xml",
                required_by=("Add-on vehicles", "Large mod setups"),
                homepage="https://www.gta5-mods.com/misc/gameconfig-for-more-mods",
            ),
            mods_files=("update/update.rpf/common/data/gameconfig.xml",),
        ),
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_NATIVE_UI,
                display_name="NativeUI",
                required_by=("Menu based scripts",),
                homepage="https://github.com/Guad/NativeUI/releases/tag/1.9.1",
            ),
            root_files=("NativeUI.dll", "scripts/NativeUI.dll"),
            version_from="scripts/NativeUI.dll",
        ),
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_LML,
                display_name="Lenny's Mod Loader",
                required_by=("LML packages",),
                homepage="https://www.lennysmodloader.com/",
            ),
            root_files=("ModLoader.asi",),
            root_directories=("lml",),
        ),
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_MENYOO,
                display_name="Menyoo Trainer",
                required_by=("Menyoo maps",),
            ),
            root_files=("Menyoo.asi",),
            root_directories=("menyooStuff",),
        ),
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_RESHADE,
                display_name="ReShade",
                required_by=("Graphics presets",),
                homepage="https://reshade.me/",
            ),
            root_files=("ReShade64.dll", "dxgi.dll", "d3d11.dll"),
            root_directories=("reshade-shaders",),
        ),
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_ENB,
                display_name="ENBSeries",
                required_by=("Graphics presets",),
                homepage="http://enbdev.com/",
            ),
            root_files=("enbseries.ini", "d3d11.dll"),
            root_directories=("enbseries",),
        ),
        ComponentProbe(
            spec=ComponentSpec(
                component_id=constants.COMPONENT_MODS_FOLDER,
                display_name="mods folder",
                required_by=("Every safe installation",),
                is_essential=True,
            ),
            root_directories=(constants.MODS_FOLDER_NAME,),
        ),
    )
