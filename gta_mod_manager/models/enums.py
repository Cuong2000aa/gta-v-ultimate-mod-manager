"""Enumerations shared by the whole domain model."""

from __future__ import annotations

from enum import Enum


class GamePlatform(str, Enum):
    """Distribution platform an installation belongs to."""

    STEAM = "steam"
    EPIC = "epic"
    ROCKSTAR = "rockstar"
    MANUAL = "manual"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        """Return a human readable platform name."""
        return {
            GamePlatform.STEAM: "Steam",
            GamePlatform.EPIC: "Epic Games",
            GamePlatform.ROCKSTAR: "Rockstar Launcher",
            GamePlatform.MANUAL: "Manual",
            GamePlatform.UNKNOWN: "Unknown",
        }[self]


class ModKind(str, Enum):
    """Category assigned to a mod package by the analyzer."""

    VEHICLE_REPLACE = "vehicle_replace"
    VEHICLE_ADDON = "vehicle_addon"
    GRAPHICS = "graphics"
    MAP = "map"
    WEAPON = "weapon"
    SCRIPT = "script"
    ASI = "asi"
    SCRIPT_HOOK_DOTNET = "scripthookvdotnet"
    MENYOO = "menyoo"
    TRAINER = "trainer"
    ZOMBIE = "zombie"
    SOUND = "sound"
    LML = "lml"
    OPENIV_PACKAGE = "openiv_package"
    PED = "ped"
    TEXTURE = "texture"
    UNKNOWN = "unknown"

    @property
    def display_name(self) -> str:
        """Return a human readable category name."""
        return _MOD_KIND_LABELS[self]


_MOD_KIND_LABELS: dict[ModKind, str] = {
    ModKind.VEHICLE_REPLACE: "Vehicle (Replace)",
    ModKind.VEHICLE_ADDON: "Vehicle (Add-On)",
    ModKind.GRAPHICS: "Graphics",
    ModKind.MAP: "Map",
    ModKind.WEAPON: "Weapon",
    ModKind.SCRIPT: "Script",
    ModKind.ASI: "ASI Plugin",
    ModKind.SCRIPT_HOOK_DOTNET: "ScriptHookVDotNet Script",
    ModKind.MENYOO: "Menyoo",
    ModKind.TRAINER: "Trainer",
    ModKind.ZOMBIE: "Zombie / Overhaul",
    ModKind.SOUND: "Sound",
    ModKind.LML: "LML Package",
    ModKind.OPENIV_PACKAGE: "OpenIV Package",
    ModKind.PED: "Ped / Character",
    ModKind.TEXTURE: "Texture",
    ModKind.UNKNOWN: "Unknown",
}


class ConfidenceLevel(str, Enum):
    """Bucketed confidence used by the UI."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CERTAIN = "certain"

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        """Map a ``0.0`` - ``1.0`` score onto a bucket."""
        if score >= 0.95:
            return cls.CERTAIN
        if score >= 0.75:
            return cls.HIGH
        if score >= 0.5:
            return cls.MEDIUM
        if score >= 0.25:
            return cls.LOW
        return cls.VERY_LOW


class InstallTarget(str, Enum):
    """Where a file is allowed to be written."""

    MODS_FOLDER = "mods"
    GAME_ROOT = "root"
    SCRIPTS_FOLDER = "scripts"
    LML_FOLDER = "lml"
    DLC_PACKS = "dlcpacks"
    EXTERNAL = "external"


class FileAction(str, Enum):
    """The kind of change an install operation performs."""

    COPY = "copy"
    OVERWRITE = "overwrite"
    CREATE_DIRECTORY = "create_directory"
    DELETE = "delete"
    XML_PATCH = "xml_patch"
    XML_APPEND = "xml_append"
    #: Copy an original ``.rpf`` into ``mods/`` so OpenIV.asi can load it.
    RPF_COPY = "rpf_copy"
    #: Import one or more members into a mods-folder ``.rpf`` (never the original).
    RPF_IMPORT = "rpf_import"
    #: Append DLC pack entries to ``dlclist.xml`` inside mods ``update.rpf``.
    RPF_DLC_REGISTER = "rpf_dlc_register"
    #: Create/update the manager add-on ped pack (models + ``peds.meta``).
    RPF_PED_IMPORT = "rpf_ped_import"


class OperationStatus(str, Enum):
    """Lifecycle state of a recorded operation."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class OperationKind(str, Enum):
    """The high level operation an audit record describes."""

    INSTALL = "install"
    UNINSTALL = "uninstall"
    BACKUP = "backup"
    RESTORE = "restore"
    REPAIR = "repair"


class ConflictType(str, Enum):
    """Category of a detected conflict."""

    DUPLICATE_VEHICLE_NAME = "duplicate_vehicle_name"
    DUPLICATE_DLC = "duplicate_dlc"
    DUPLICATE_XML_ENTRY = "duplicate_xml_entry"
    DUPLICATE_HANDLING_ID = "duplicate_handling_id"
    DUPLICATE_TEXTURE = "duplicate_texture"
    DUPLICATE_GAMECONFIG = "duplicate_gameconfig"
    DUPLICATE_PACKFILE = "duplicate_packfile"
    FILE_OVERWRITE = "file_overwrite"
    MISSING_DEPENDENCY = "missing_dependency"
    PROTECTED_TARGET = "protected_target"

    @property
    def display_name(self) -> str:
        """Return a human readable conflict name."""
        return self.value.replace("_", " ").title()


class ConflictSeverity(str, Enum):
    """How badly a conflict affects an installation."""

    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"

    @property
    def is_blocking(self) -> bool:
        """Return ``True`` when the conflict must stop the installation."""
        return self is ConflictSeverity.BLOCKING


class ComponentStatus(str, Enum):
    """Installation state of a required or optional game component."""

    INSTALLED = "installed"
    MISSING = "missing"
    OUTDATED = "outdated"
    UNKNOWN = "unknown"


class ModStatus(str, Enum):
    """State of a mod tracked by the library."""

    INSTALLED = "installed"
    DISABLED = "disabled"
    BROKEN = "broken"
    AVAILABLE = "available"
