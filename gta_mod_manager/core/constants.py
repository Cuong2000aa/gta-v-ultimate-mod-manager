"""Central place for every literal the application relies on.

No module outside this one is allowed to hardcode file names, folder names,
registry keys or extension lists. Keeping them here makes the rules auditable
and lets plugins for other games override them without touching the core.
"""

from __future__ import annotations

from typing import Final

APP_NAME: Final[str] = "GTA V Ultimate Mod Manager"
APP_SLUG: Final[str] = "GtaVUltimateModManager"
APP_VERSION: Final[str] = "3.0.0"
ORG_NAME: Final[str] = "UltimateModTools"

# --------------------------------------------------------------------------
# Working directory names (relative to the application data root)
# --------------------------------------------------------------------------
DIR_LOGS: Final[str] = "logs"
DIR_TEMP: Final[str] = "temp"
DIR_BACKUP: Final[str] = "backup"
DIR_CACHE: Final[str] = "cache"
DIR_CONFIG: Final[str] = "config"
DIR_LIBRARY: Final[str] = "library"
DIR_DOWNLOADS: Final[str] = "downloads"

SETTINGS_FILE: Final[str] = "settings.json"
MODS_DB_FILE: Final[str] = "installed_mods.sqlite3"
LEGACY_MODS_DB_FILE: Final[str] = "installed_mods.json"
BACKUP_DB_FILE: Final[str] = "backups.json"
LOG_FILE: Final[str] = "gta_mod_manager.log"
DATA_ROOT_POINTER_FILE: Final[str] = f"{APP_SLUG}.bootstrap.json"
DATA_MIGRATION_MARKER_FILE: Final[str] = ".data-migration-complete"

# --------------------------------------------------------------------------
# GTA V game layout
# --------------------------------------------------------------------------
GAME_ID_GTA_V: Final[str] = "gta_v"
GAME_TITLE_GTA_V: Final[str] = "Grand Theft Auto V"

MODS_FOLDER_NAME: Final[str] = "mods"
#: Where diagnostics moves leftover ENB config/shaders out of the game root.
ENB_QUARANTINE_FOLDER: Final[str] = "mods/_enb_quarantine_by_manager"
SCRIPTS_FOLDER_NAME: Final[str] = "scripts"
LML_FOLDER_NAME: Final[str] = "lml"
UPDATE_FOLDER_NAME: Final[str] = "update"
DLC_PACKS_RELATIVE: Final[str] = "update/x64/dlcpacks"
DLC_LIST_RELATIVE: Final[str] = "update/update.rpf/common/data/dlclist.xml"
#: Mods-folder copy of the update archive that holds ``dlclist.xml``.
UPDATE_ARCHIVE_RELATIVE: Final[str] = "update/update.rpf"
#: Member path of ``dlclist.xml`` inside :data:`UPDATE_ARCHIVE_RELATIVE`.
DLC_LIST_MEMBER: Final[str] = "common/data/dlclist.xml"

#: Manager-owned add-on ped DLC pack (replaces manual AddonPeds Rebuild).
ADDON_PEDS_PACK_NAME: Final[str] = "umm_peds"
#: Nested stream archive inside the manager ped pack.
ADDON_PEDS_STREAM_ARCHIVE: Final[str] = "peds.rpf"
#: Ped metadata file inside the manager ped pack.
ADDON_PEDS_META_MEMBER: Final[str] = "peds.meta"
#: Where Iron Man-style ``*_armor.ini`` files belong under the game root.
IRONMAN_ARMOR_RELATIVE: Final[str] = "scripts/IronmanV Files/armors"

#: DLC pack folders that are intentional even when not (yet) in the library.
#: ``umm_peds`` is owned by this manager; ``pedselector`` / ``addonpeds`` come
#: from Ped Selector / AddonPeds installs that live outside the mod database.
KNOWN_EXTERNAL_DLC_PACKS: Final[frozenset[str]] = frozenset(
    {
        ADDON_PEDS_PACK_NAME,
        "pedselector",
        "addonpeds",
    }
)

PRIMARY_EXECUTABLE: Final[str] = "GTA5.exe"
GAME_EXECUTABLES: Final[tuple[str, ...]] = (
    "GTA5.exe",
    "GTA5_Enhanced.exe",
    "PlayGTAV.exe",
    "GTAVLauncher.exe",
)

#: Processes the crash monitor watches (the game itself, not the launcher).
GAME_PROCESS_NAMES: Final[tuple[str, ...]] = ("GTA5.exe", "GTA5_Enhanced.exe")

#: Files/folders that prove a folder really is a GTA V installation.
GAME_SIGNATURE_ENTRIES: Final[tuple[str, ...]] = (
    "GTA5.exe",
    "common.rpf",
    "x64a.rpf",
    "update",
    "x64",
)

#: Archives the application is never allowed to touch, even with a backup.
PROTECTED_ARCHIVE_SUFFIX: Final[str] = ".rpf"

#: Outer archive under the game root that holds stock vehicle stream files.
VEHICLE_STREAM_ARCHIVE: Final[str] = "x64e.rpf"
#: Nested archive path inside :data:`VEHICLE_STREAM_ARCHIVE`.
VEHICLE_STREAM_NESTED_RPF: Final[str] = "levels/gta5/vehicles.rpf"
#: Stream assets the manager can auto-import into the mods copy of x64e.rpf.
VEHICLE_STREAM_EXTENSIONS: Final[frozenset[str]] = frozenset({".yft", ".ytd"})

PROTECTED_ROOT_FILES: Final[frozenset[str]] = frozenset(
    {
        "gta5.exe",
        "gta5_enhanced.exe",
        "playgtav.exe",
        "gtavlauncher.exe",
        "gtavlanguageselect.exe",
        "steam_api64.dll",
        "gfsdk_shadowlib.win64.dll",
        "index.bin",
        "common.rpf",
    }
)

# --------------------------------------------------------------------------
# Root-installation whitelist (ABSOLUTE SAFETY RULE)
# Anything not matching these patterns must be installed inside <game>/mods.
# --------------------------------------------------------------------------
ALLOWED_ROOT_FILE_PATTERNS: Final[tuple[str, ...]] = (
    "ScriptHookV.dll",
    "dinput8.dll",
    "ScriptHookVDotNet*.dll",
    "ScriptHookVDotNet*.ini",
    "ScriptHookVDotNet*.xml",
    "*.asi",
    "*.ini",
    "*.log",
    "openIV.asi",
    "PackfileLimitAdjuster.asi",
    "GTAVHeapAdjuster.asi",
    "d3d11.dll",
    "d3d12.dll",
    "dxgi.dll",
    "d3dcompiler_47.dll",
    "ReShade*.ini",
    "ReShadePreset*.ini",
    "enbseries.ini",
    "enblocal.ini",
    "enbhost.exe",
)

ALLOWED_ROOT_DIRECTORIES: Final[tuple[str, ...]] = (
    "scripts",
    "lml",
    "reshade",
    "reshade-shaders",
    "reshade-presets",
    "enbseries",
    "enbcache",
    "menyoostuff",
    "asi",
    "plugins",
    "openivscripts",
)

# --------------------------------------------------------------------------
# File classification helpers
# --------------------------------------------------------------------------
ARCHIVE_EXTENSIONS: Final[frozenset[str]] = frozenset({".zip", ".7z", ".rar", ".oiv"})
OIV_EXTENSION: Final[str] = ".oiv"

# --------------------------------------------------------------------------
# External archive tools used for formats Python cannot open on its own
# --------------------------------------------------------------------------
SEVEN_ZIP_COMMAND_NAMES: Final[tuple[str, ...]] = ("7z", "7za")
SEVEN_ZIP_INSTALL_PATHS: Final[tuple[str, ...]] = (
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
)

#: ``UnRAR.exe`` is the console tool and is always preferred; ``WinRAR.exe``
#: is a GUI application that accepts the same extraction command.
UNRAR_COMMAND_NAMES: Final[tuple[str, ...]] = ("unrar", "UnRAR")
UNRAR_INSTALL_PATHS: Final[tuple[str, ...]] = (
    r"C:\Program Files\WinRAR\UnRAR.exe",
    r"C:\Program Files (x86)\WinRAR\UnRAR.exe",
    r"C:\Program Files\WinRAR\WinRAR.exe",
    r"C:\Program Files (x86)\WinRAR\WinRAR.exe",
)

#: Folder used to contain a command-line extraction before its content is
#: moved into the workspace, so a traversal entry cannot escape.
CLI_EXTRACTION_STAGING_DIR: Final[str] = "__extracted__"

GAME_ASSET_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        ".yft",
        ".ytd",
        ".ydr",
        ".ydd",
        ".ymap",
        ".ymt",
        ".ybn",
        ".ynv",
        ".ytyp",
        ".yed",
        ".ycd",
        ".awc",
        ".rpf",
    }
)
META_EXTENSIONS: Final[frozenset[str]] = frozenset({".meta", ".xml", ".dat", ".ymt"})
SCRIPT_EXTENSIONS: Final[frozenset[str]] = frozenset({".cs", ".vb", ".lua", ".js", ".dll"})
IMAGE_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".dds", ".psd"}
)
DOCUMENT_EXTENSIONS: Final[frozenset[str]] = frozenset({".txt", ".md", ".pdf", ".rtf", ".nfo"})

# --------------------------------------------------------------------------
# Well known metadata file names
# --------------------------------------------------------------------------
VEHICLES_META: Final[str] = "vehicles.meta"
HANDLING_META: Final[str] = "handling.meta"
CARCOLS_META: Final[str] = "carcols.meta"
CARVARIATIONS_META: Final[str] = "carvariations.meta"
VEHICLE_LAYOUTS_META: Final[str] = "vehiclelayouts.meta"
DLCTEXT_META: Final[str] = "dlctext.meta"
CONTENT_XML: Final[str] = "content.xml"
SETUP2_XML: Final[str] = "setup2.xml"
DLCLIST_XML: Final[str] = "dlclist.xml"
GAMECONFIG_XML: Final[str] = "gameconfig.xml"
PACKAGE_XML: Final[str] = "package.xml"
ASSEMBLY_XML: Final[str] = "assembly.xml"

VEHICLE_META_FILES: Final[frozenset[str]] = frozenset(
    {
        VEHICLES_META,
        HANDLING_META,
        CARCOLS_META,
        CARVARIATIONS_META,
        VEHICLE_LAYOUTS_META,
    }
)

# --------------------------------------------------------------------------
# Windows registry lookup locations for game/platform detection
# --------------------------------------------------------------------------
REG_STEAM_PATHS: Final[tuple[tuple[str, str, str], ...]] = (
    ("HKEY_CURRENT_USER", r"Software\Valve\Steam", "SteamPath"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\Valve\Steam", "InstallPath"),
)
REG_ROCKSTAR_PATHS: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "HKEY_LOCAL_MACHINE",
        r"SOFTWARE\WOW6432Node\Rockstar Games\Grand Theft Auto V",
        "InstallFolder",
    ),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\Rockstar Games\Grand Theft Auto V", "InstallFolder"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\Rockstar Games\GTAV", "InstallFolder"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\Rockstar Games\Launcher", "InstallFolder"),
)
REG_UNINSTALL_ROOTS: Final[tuple[tuple[str, str], ...]] = (
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ("HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
)

STEAM_APP_ID_GTA_V: Final[str] = "271590"
STEAM_LIBRARY_MANIFEST: Final[str] = "steamapps/libraryfolders.vdf"
STEAM_DEFAULT_GAME_FOLDER: Final[str] = "steamapps/common/Grand Theft Auto V"

EPIC_MANIFEST_DIR: Final[str] = r"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests"
EPIC_GTA_V_APP_NAMES: Final[frozenset[str]] = frozenset({"9d2d0eb64d5c44529cece33fe2a46482"})

COMMON_INSTALL_FOLDERS: Final[tuple[str, ...]] = (
    r"C:\Program Files\Rockstar Games\Grand Theft Auto V",
    r"C:\Program Files (x86)\Rockstar Games\Grand Theft Auto V",
    r"C:\Program Files\Epic Games\GTAV",
    r"C:\Program Files (x86)\Steam\steamapps\common\Grand Theft Auto V",
    r"C:\Games\Grand Theft Auto V",
    r"D:\Games\Grand Theft Auto V",
    r"D:\SteamLibrary\steamapps\common\Grand Theft Auto V",
    r"E:\SteamLibrary\steamapps\common\Grand Theft Auto V",
)

# --------------------------------------------------------------------------
# Component fingerprints (file name -> component id) used by the detector
# --------------------------------------------------------------------------
COMPONENT_SCRIPT_HOOK_V: Final[str] = "scripthookv"
COMPONENT_SCRIPT_HOOK_V_DOTNET: Final[str] = "scripthookvdotnet"
COMPONENT_ASI_LOADER: Final[str] = "asiloader"
COMPONENT_OPENIV_ASI: Final[str] = "openiv_asi"
COMPONENT_PACKFILE_LIMIT_ADJUSTER: Final[str] = "packfile_limit_adjuster"
COMPONENT_HEAP_ADJUSTER: Final[str] = "heap_adjuster"
COMPONENT_GAMECONFIG: Final[str] = "gameconfig"
COMPONENT_LML: Final[str] = "lml"
COMPONENT_NATIVE_UI: Final[str] = "nativeui"
COMPONENT_MENYOO: Final[str] = "menyoo"
COMPONENT_RESHADE: Final[str] = "reshade"
COMPONENT_ENB: Final[str] = "enb"
COMPONENT_MODS_FOLDER: Final[str] = "mods_folder"

# --------------------------------------------------------------------------
# Operational limits
# --------------------------------------------------------------------------
MAX_SCAN_DEPTH: Final[int] = 12
MAX_NESTED_ARCHIVE_DEPTH: Final[int] = 3
HASH_CHUNK_SIZE: Final[int] = 1024 * 1024
LOG_MAX_BYTES: Final[int] = 5 * 1024 * 1024
LOG_BACKUP_COUNT: Final[int] = 5
LOG_RING_CAPACITY: Final[int] = 2000

# --------------------------------------------------------------------------
# Online mod catalogues
# --------------------------------------------------------------------------
NEXUS_API_BASE: Final[str] = "https://api.nexusmods.com/v1"
NEXUS_GAME_DOMAIN_GTA_V: Final[str] = "gta5"
NEXUS_SITE_BASE: Final[str] = "https://www.nexusmods.com/gta5"
GTA5MODS_SITE_BASE: Final[str] = "https://www.gta5-mods.com"
ONLINE_USER_AGENT: Final[str] = f"{APP_SLUG}/{APP_VERSION}"
ARCHIVE_DOWNLOAD_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".zip", ".rar", ".7z", ".oiv"}
)
