"""Known GTA V crash / init error signatures and remediation hints."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnownErrorPattern:
    """A log / dialog signature the scanner looks for."""

    code: str
    #: Substrings matched case-insensitively in logs or crash text.
    needles: tuple[str, ...]
    title: str
    detail: str
    fix: str
    category: str = "crash"
    severity: str = "error"


#: Rockstar / RAGE dialogs and common log lines.
KNOWN_ERROR_PATTERNS: tuple[KnownErrorPattern, ...] = (
    KnownErrorPattern(
        code="sys.invalid_resource",
        needles=(
            "ERR_SYS_INVALIDRESOURCE_5",
            "ERR_SYS_INVALIDRESOURCE",
            "Corrupt game data. Please reboot, verify the game data",
        ),
        title="Corrupt game data (ERR_SYS_INVALIDRESOURCE_5)",
        detail=(
            "RAGE refused to load a resource — almost always a bad/modded .rpf "
            "(for example mods/x64e.rpf or mods/update/update.rpf), a half-written "
            "archive after a crash, or a replace vehicle that does not match the "
            "game build. Less often: genuinely corrupted stock game files."
        ),
        fix=(
            "1) Rename the mods folder to mods_off and launch again. "
            "2) If that works, rename back and remove/rename mods/x64e.rpf then "
            "mods/update/update.rpf one at a time. "
            "3) Uninstall the last replace vehicle you installed. "
            "4) Steam → Verify integrity of game files. "
            "5) Reboot, then retry."
        ),
    ),
    KnownErrorPattern(
        code="gfx.d3d_init",
        needles=("ERR_GFX_D3D_INIT", "Failed Initialization. Please reboot"),
        title="DirectX failed to start (ERR_GFX_D3D_INIT)",
        detail=(
            "GTA V could not create the Direct3D device. This is usually the GPU "
            "driver, overlays, fullscreen mode, or a broken graphics mod (ENB/ReShade) "
            "— not a missing vehicle model."
        ),
        fix=(
            "1) Reboot PC. 2) Update GPU drivers. 3) Disable Discord/Steam/NVIDIA overlays. "
            "4) Add -windowed to commandline.txt. 5) Remove leftover ENB files if d3d11.dll "
            "is missing. 6) Temporarily rename the mods folder to test vanilla."
        ),
    ),
    KnownErrorPattern(
        code="gfx.state",
        needles=("ERR_GFX_STATE",),
        title="Graphics state error (ERR_GFX_STATE)",
        detail="The GPU lost or rejected a render state — often VRAM, driver crash, or bad shaders.",
        fix="Lower graphics settings, update drivers, disable ENB/ReShade, verify game files on Steam.",
    ),
    KnownErrorPattern(
        code="gfx.d3d_reset",
        needles=("ERR_GFX_D3D_RESET",),
        title="Direct3D device reset (ERR_GFX_D3D_RESET)",
        detail="The graphics device was lost mid-session (driver timeout, sleep, alt-tab).",
        fix="Update GPU drivers, disable fullscreen optimizations, avoid forcing VSync via ENB.",
    ),
    KnownErrorPattern(
        code="file.version",
        needles=("ERR_FILE_VERSION",),
        title="Game file version mismatch (ERR_FILE_VERSION)",
        detail="Game binaries and assets do not match — often after a partial update or bad replace.",
        fix="Verify integrity of game files in Steam/Rockstar Launcher, then re-check mods.",
    ),
    KnownErrorPattern(
        code="net.profile",
        needles=("ERR_NET_PROFILEDOWN", "ERR_NET_"),
        title="Online / profile network error",
        detail="Rockstar services or the local profile could not be reached.",
        fix="Check Rockstar status, firewall, and that you are signed in to the launcher.",
        severity="warning",
    ),
    KnownErrorPattern(
        code="scripthook.compat",
        needles=(
            "Script Hook V: Failed to load",
            "FATAL ERROR: ScriptHookV",
            "ScriptHookV.dll is outdated",
            "Unsupported game version",
        ),
        title="Script Hook V problem",
        detail="ScriptHookV failed to load or does not match this GTA V build.",
        fix="Download a ScriptHookV build that matches your GTA V version, or wait for an update.",
        category="asi",
    ),
)
