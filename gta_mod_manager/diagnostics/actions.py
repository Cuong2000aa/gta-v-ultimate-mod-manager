"""Stable fix-action identifiers for diagnostics one-click repairs."""

from __future__ import annotations

#: Delete orphan folders under ``mods/update/x64/dlcpacks``.
FIX_DELETE_ORPHAN_DLCPACKS = "delete_orphan_dlcpacks"

#: Restore listed vehicle stream members from stock ``x64e.rpf`` into the mods copy.
FIX_RESTORE_VEHICLE_STREAM = "restore_vehicle_stream_members"

#: Move leftover ENB config / shader files out of the game root (ERR_GFX_D3D_INIT).
FIX_QUARANTINE_ENB_LEFTOVERS = "quarantine_enb_leftovers"

#: Physically disable one or more library mods (quarantine loose files).
FIX_DISABLE_MODS = "disable_mods"
