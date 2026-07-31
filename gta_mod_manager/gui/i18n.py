"""Lightweight UI string catalog (English + Vietnamese).

Qt Designer / ``QTranslator`` is a poor fit for this hand-built UI, so pages
look up stable keys through :func:`t`. The active language is process-global
and loaded from :class:`~gta_mod_manager.models.settings.AppSettings` at
startup.
"""

from __future__ import annotations

from collections.abc import Mapping

SUPPORTED_LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("vi", "Tiếng Việt"),
)

_DEFAULT = "en"
_language = _DEFAULT

_EN: dict[str, str] = {
    # Sidebar / chrome
    "nav.overview": "Overview",
    "nav.mods": "Mods",
    "nav.safety": "Safety",
    "nav.application": "Application",
    "nav.dashboard": "Dashboard",
    "nav.install": "Install a Mod",
    "nav.online": "Online Mods",
    "nav.installed": "Installed Mods",
    "nav.spawn": "Spawn Center",
    "nav.graphics": "Graphics Mods",
    "nav.game_modes": "Game modes",
    "nav.zombie": "Zombie Mode",
    "nav.conflicts": "Conflict Center",
    "nav.backup": "Backup & Restore",
    "nav.diagnostics": "Game Diagnostics",
    "nav.logs": "Log Viewer",
    "nav.settings": "Settings",
    "chrome.safety_first": "v{version} - safety first",
    "chrome.no_install": "No installation selected",
    "chrome.game_folder": "Game folder:\n{path}",
    "chrome.starting": "Starting...",
    "chrome.read_only": "Original game archives are read-only",
    "chrome.something_wrong": "Something went wrong",
    "chrome.error": "Error",
    # Common
    "common.refresh": "Refresh",
    "common.browse": "Browse...",
    "common.open": "Open",
    "common.yes": "Yes",
    "common.no": "No",
    "common.search": "Search",
    "common.re_scan": "Re-scan",
    "common.expand_all": "Expand all",
    "common.collapse_all": "Collapse all",
    # Settings
    "settings.title": "Settings",
    "settings.subtitle": "Detection, safety behaviour and working folders.",
    "settings.installs": "GTA V installations",
    "settings.folder": "Folder",
    "settings.platform": "Platform",
    "settings.version": "Version",
    "settings.detected_by": "Detected by",
    "settings.detect_again": "Detect again",
    "settings.use_selected": "Use selected",
    "settings.choose_manually": "Choose manually...",
    "settings.behaviour": "Behaviour",
    "settings.language": "Language",
    "settings.language_hint": "Restart the app after changing the language.",
    "settings.backups": "Backups",
    "settings.auto_backup": "Create a snapshot before every write",
    "settings.auto_backup_hint": (
        "Backs up loose files and script/ASI installs. Shared game archives "
        "(mods/*.rpf such as x64e.rpf) are not full-copied — they are restored "
        "member-by-member on uninstall, so backups stay small."
    ),
    "settings.safety": "Safety",
    "settings.confirm_root": "Ask before writing outside the mods folder",
    "settings.diagnostics": "Diagnostics",
    "settings.keep_temp": "Keep extraction workspaces for troubleshooting",
    "settings.crash_monitor_label": "Crash monitor",
    "settings.crash_monitor": "Watch the game while it runs and report crashes",
    "settings.crash_monitor_hint": (
        "When the game exits abnormally, the tool collects the exit code, Windows "
        "crash dumps and script logs, then names the most likely mod on the "
        "Diagnostics page."
    ),
    "settings.snapshots_kept": "Snapshots kept per mod",
    "settings.seven_zip": "7-Zip executable",
    "settings.seven_zip_ph": "Optional path to 7z.exe, used for RAR archives",
    "settings.unrar": "UnRAR executable",
    "settings.unrar_ph": "Optional path to UnRAR.exe, auto-detected when WinRAR is installed",
    "settings.nexus_api_key": "Nexus Mods API key",
    "settings.nexus_api_key_ph": "Paste your personal API key",
    "settings.nexus_api_key_hint": (
        "Create a key at "
        "<a href='https://www.nexusmods.com/users/myaccount?tab=api%20access'>"
        "nexusmods.com → API Access</a>. "
        "Direct API downloads require Nexus Premium; free accounts can still search "
        "and open the Files tab in the browser."
    ),
    "settings.working_folders": "Working folders",
    "settings.app_data": "Application data",
    "settings.change_data_folder": "Change...",
    "settings.data_folder_hint": (
        "Choose where the SQLite library, settings, logs and backups are stored. "
        "The app copies everything safely and switches after restarting."
    ),
    "settings.data_folder_title": "Choose an empty application-data folder",
    "settings.data_move_title": "Move application data",
    "settings.data_move_body": (
        "Copy all application data?\n\nFrom: {source}\nTo: {destination}\n\n"
        "The app will close when the copy is ready. The old folder is deleted only "
        "after the new copy starts successfully."
    ),
    "settings.data_move_done_title": "Data move ready",
    "settings.data_move_done_body": (
        "Data was copied to:\n{destination}\n\n"
        "The app will now close. Open it again to use the new location."
    ),
    "settings.logs": "Logs",
    "settings.backups_folder": "Backups",
    "settings.temp": "Temporary extraction",
    "settings.config": "Configuration",
    "settings.saved": "Settings saved",
    "settings.language_restart_title": "Language changed",
    "settings.language_restart_body": (
        "Language saved as {language}.\n\n"
        "Close the app and open it again with run.bat to apply the new language."
    ),
    "settings.scanning": "Scanning for GTA V installations...",
    "settings.found_installs": "Found {count} installation(s)",
    # Dashboard
    "dashboard.title": "Dashboard",
    "dashboard.subtitle": "Installation health, library size and recent activity.",
    # Install
    "install.title": "Install a Mod",
    "install.subtitle": (
        "Drop an archive, preview every write, then confirm. "
        "Vehicles, weapons, maps (add-on DLC), peds, and scripts install automatically."
    ),
    # Library
    "library.title": "Installed mods",
    "library.subtitle": (
        "Every file listed here was written by this manager and can be removed exactly."
    ),
    "library.search_ph": "Search by name, category or spawn code",
    "library.card": "Your mods",
    "library.details": "Details",
    "library.verify": "Verify files",
    "library.disable": "Disable",
    "library.enable": "Enable",
    "library.uninstall": "Uninstall",
    "library.select_mod": "Select a mod",
    "library.status_installed": "Installed",
    "library.status_disabled": "Disabled",
    "library.status_broken": "Incomplete files",
    "library.status_available": "Available",
    "library.status_files_missing": "Files missing",
    "library.files_header": "Installed content",
    "library.files_state": "State",
    "library.working": "Working...",
    "library.spawn_tip": (
        "Type this in a trainer (Menyoo / Simple Trainer) to spawn the vehicle:\n{codes}"
    ),
    "library.disable_hint": (
        "Disable moves loose files out of the game folder so they cannot load. "
        "Shared archive models are restored to stock and re-applied when you enable "
        "(when install-time payloads were cached)."
    ),
    "library.uninstall_title": "Uninstall mod",
    "library.uninstall_complete": "Uninstall complete",
    "library.uninstall_complete_body": (
        "The mod was removed from the library.\n"
        "If it was a replace vehicle, stock models were restored in the shared archive."
    ),
    "library.shared_detail": (
        "This mod lives inside a shared mods archive (for example x64e.rpf). "
        "Uninstall restores the stock models for this vehicle. "
        "Other replace mods that share the same archive stay installed. "
        "Rewriting the archive can take a minute — watch the progress bar."
    ),
    "library.staging_detail": (
        "These files were only staged for OpenIV and never written into the game "
        "folder. Uninstall removes them from the manager library."
    ),
    "library.plain_detail": (
        "Files this manager wrote for the mod will be deleted. "
        "A backup is taken first, so this can be undone from Backup & Restore."
    ),
    "library.remove_confirm": "Remove {name}?\n\n{count} tracked file(s).\n\n{detail}",
    "library.col_mod": "Mod",
    "library.col_category": "Category",
    "library.col_spawn": "Spawn code",
    "library.col_files": "Files",
    "library.col_size": "Size",
    "library.col_status": "Status",
    # Conflicts
    "conflicts.title": "Conflict center",
    "conflicts.subtitle": "Duplicate spawn codes, DLC packs, shared files and missing dependencies.",
    "conflicts.summary": "{count} conflict(s) across {categories} category(ies), {blocking} blocking.",
    "conflicts.detected": "Detected conflicts",
    "conflicts.col_conflict": "Conflict",
    "conflicts.col_severity": "Severity",
    "conflicts.col_action": "Suggested action",
    "conflicts.none": "No conflicts detected.",
    "conflicts.disable": "Disable conflicting mods",
    "conflicts.disable_pick": "Select a conflict row that lists one or more mods first.",
    "conflicts.disable_confirm": (
        "Disable {count} conflicting mod(s)? You can re-enable the one you want to keep."
    ),
    "conflicts.disable_hint": "Select this row, then press Disable conflicting mods",
    "conflicts.sev_blocking": "Blocking",
    "conflicts.sev_warning": "Warning",
    "conflicts.sev_info": "Info",
    "conflicts.duplicate_vehicle_name": "Duplicate Vehicle Name",
    "conflicts.file_overwrite": "File Overwrite",
    "conflicts.duplicate_dlc": "Duplicate Dlc",
    "conflicts.duplicate_gameconfig": "Duplicate Gameconfig",
    "conflicts.missing_dependency": "Missing Dependency",
    # Backup
    "backup.title": "Backup & Restore",
    "backup.subtitle": "Snapshots taken before installs and uninstalls.",
    # Logs
    "logs.title": "Log Viewer",
    "logs.subtitle": "Live application log for troubleshooting.",
    "diagnostics.title": "Game diagnostics",
    "diagnostics.subtitle": (
        "Detects known GTA V errors (ERR_GFX_D3D_INIT, ScriptHook, ENB leftovers, "
        "orphan DLC packs, broken vehicle stream entries) from logs and the game folder."
    ),
    "diagnostics.findings": "Findings",
    "diagnostics.col_issue": "Issue",
    "diagnostics.col_severity": "Severity",
    "diagnostics.col_fix": "Suggested fix",
    "diagnostics.need_game": "Select a GTA V installation first",
    "diagnostics.scanning": "Scanning game folder and logs...",
    "diagnostics.fixing": "Applying repair...",
    "diagnostics.clean": "No known crash problems detected",
    "diagnostics.summary": "{errors} error(s), {warnings} warning(s) — {total} finding(s)",
    "diagnostics.summary_status": "{errors} error(s), {warnings} warning(s)",
    "diagnostics.sev_error": "Error",
    "diagnostics.sev_warning": "Warning",
    "diagnostics.sev_info": "Info",
    "diagnostics.sev_ok": "OK",
    "diagnostics.cat_crash": "Crash / error codes",
    "diagnostics.cat_graphics": "Graphics mods",
    "diagnostics.cat_asi": "ASI / ScriptHook",
    "diagnostics.cat_mods": "Mods folder",
    "diagnostics.cat_vehicles": "Vehicles / RPF",
    "diagnostics.cat_components": "Components",
    "diagnostics.cat_launch": "Launch options",
    "diagnostics.cat_logs": "Logs",
    "diagnostics.cat_summary": "Summary",
    "diagnostics.cat_general": "General",
    "diagnostics.repair_selected": "Repair selected",
    "diagnostics.fix_unavailable": "This finding has no automatic repair",
    "diagnostics.fix_select_first": "Select a finding that supports one-click repair.",
    "diagnostics.repair_confirm_title": "Apply repair?",
    "diagnostics.repair_confirm_body": (
        "{title}\n\n{fix}\n\nTargets:\n{targets}\n\n"
        "Safe repair only — originals stay read-only. Continue?"
    ),
    "diagnostics.repair_done_title": "Repair applied",
    "diagnostics.finding.mods.orphan_dlcpack.title": "Orphan DLC pack folder: {short}",
    "diagnostics.finding.mods.orphan_dlcpack.detail": (
        "This folder sits under mods/update/x64/dlcpacks but is not tracked by any "
        "installed mod in the library. Leftovers like 'hellcat' after a bad uninstall "
        "commonly cause ERR_SYS_INVALIDRESOURCE or spawn failures. If you installed this "
        "pack outside the manager and still want it, keep the folder and re-import the mod."
    ),
    "diagnostics.finding.mods.orphan_dlcpack.fix": (
        "Delete this orphan pack folder from mods/update/x64/dlcpacks "
        "(and remove matching dlclist entries). Use Repair selected for a safe fix."
    ),
    "diagnostics.finding.mods.bad_vehicle_stream.title": "Broken vehicle stream entries: {short}",
    "diagnostics.finding.mods.bad_vehicle_stream.detail": (
        "In mods/x64e.rpf → levels/gta5/vehicles.rpf, one or more .yft/.ytd files are "
        "stored as binary entries instead of resources. This often follows a bad "
        "replace/uninstall (e.g. gauntlet, baller, f620) and triggers ERR_SYS_INVALIDRESOURCE_5."
    ),
    "diagnostics.finding.mods.bad_vehicle_stream.fix": (
        "Restore the listed stock members from the original game x64e.rpf into the mods "
        "copy. Use Repair selected — originals stay read-only."
    ),
    "diagnostics.finding.mods.replace_members_unhealthy.title": (
        "Installed replace assets look unhealthy: {short}"
    ),
    "diagnostics.finding.mods.replace_members_unhealthy.detail": (
        "One or more library-tracked replace vehicle members are missing from "
        "mods/x64e.rpf or are no longer valid resource entries."
    ),
    "diagnostics.finding.mods.replace_members_unhealthy.fix": (
        "Restore stock members for the listed paths, or uninstall/reinstall the "
        "affected replace mod."
    ),
    # Crash monitor (session watcher)
    "crash.session_started_title": "Game detected",
    "crash.session_started_body": "Watching {name} — crashes will be reported here.",
    "crash.detected_title": "The game crashed",
    "crash.detected_body": (
        "Session lasted about {minutes} minute(s).\n{detail}\n"
        "See the Diagnostics page for the full report."
    ),
    "crash.no_suspect": "No single mod could be identified as the cause.",
    "crash.clean_title": "Game closed normally",
    "crash.clean_body": "Session lasted about {minutes} minute(s); no crash detected.",
    "diagnostics.finding.crash.exit_code.title": "The game exited abnormally (code {names})",
    "diagnostics.finding.crash.exit_code.detail": (
        "The exit code is an NTSTATUS warning/error exception (0x8xxxxxxx or "
        "0xCxxxxxxx), which means the game process crashed rather than being "
        "closed normally."
    ),
    "diagnostics.finding.crash.dump.title": "Windows wrote crash dump(s): {short}",
    "diagnostics.finding.crash.dump.detail": (
        "A crash dump is definite proof the game crashed."
    ),
    "diagnostics.finding.crash.script_error.title": "Script threw errors: {names}",
    "diagnostics.finding.crash.script_error.detail": (
        "ScriptHookVDotNet logged unhandled exceptions from this script during "
        "the session. The script is broken or incompatible with the current "
        "game/SHVDN version."
    ),
    "diagnostics.finding.crash.script_error.fix": (
        "Use Repair to disable the owning mod, or uninstall/update it / SHVDN."
    ),
    "diagnostics.finding.crash.script_load.title": "Script failed to load: {names}",
    "diagnostics.finding.crash.script_load.detail": (
        "The assembly could not be loaded, usually because a dependency "
        "(ScriptHookVDotNet version, NativeUI, ...) is missing or too old."
    ),
    "diagnostics.finding.crash.script_load.fix": (
        "Install the missing dependency from Essentials Kit, or disable the mod."
    ),
    "diagnostics.finding.crash.recent_mods.title": "Recently installed mods: {names}",
    "diagnostics.finding.crash.recent_mods.detail": (
        "Mods installed in the last 48 hours are the prime suspects after a "
        "new crash."
    ),
    "diagnostics.finding.crash.recent_mods.fix": (
        "Use Repair to physically disable the recent mods and relaunch."
    ),
    "diagnostics.finding.crash.no_evidence.title": (
        "The game crashed but no script left evidence"
    ),
    "diagnostics.finding.crash.no_evidence.detail": (
        "No script errors were logged. Typical causes are native .asi plugins, "
        "texture/vehicle mods exceeding memory pools, or an outdated "
        "ScriptHookV after a game update."
    ),
    "diagnostics.finding.crash.no_evidence.fix": (
        "Rename dinput8.dll to dinput8.dll.off and start the game; if it stops "
        "crashing, re-enable mods in small groups."
    ),
    "diagnostics.finding.crash.session_ok.title": "Last game session ended normally",
    "diagnostics.finding.crash.session_ok.detail": (
        "No crash dump and a clean exit code were observed."
    ),
    # Install view
    "install.card_plan": "Planned operations",
    "install.col_action": "Action",
    "install.col_zone": "Where it writes",
    "install.col_target": "Target path",
    "install.col_detail": "Detail",
    "install.col_vehicle_source": "Source",
    "install.col_vehicle_handling": "Handling",
    "install.col_vehicle_make": "Manufacturer",
    "install.kind_confidence": "Detected as {kind} ({confidence} confidence)",
    "install.kind_vehicle_addon": "Vehicle add-on",
    "install.kind_vehicle_replace": "Vehicle replace",
    "install.kind_ped": "Character / ped",
    "install.kind_weapon": "Weapon",
    "install.kind_map": "Map",
    "install.kind_script": "Script",
    "install.kind_asi": "ASI plugin",
    "install.kind_script_hook_dotnet": "ScriptHookVDotNet script",
    "install.kind_graphics": "Graphics",
    "install.kind_lml": "LML package",
    "install.kind_openiv_package": "OpenIV package",
    "install.kind_menyoo": "Menyoo",
    "install.kind_trainer": "Trainer",
    "install.kind_zombie": "Zombie",
    "install.kind_sound": "Audio",
    "install.kind_texture": "Texture pack",
    "install.kind_unknown": "Unknown type",
    "install.card_package": "Package",
    "install.tab_vehicles": "Vehicles",
    "install.tab_vehicles_n": "Vehicles ({count})",
    "install.tab_conflicts": "Conflicts",
    "install.tab_conflicts_n": "Conflicts ({count})",
    "install.tab_manual": "Manual steps",
    "install.tab_manual_n": "Manual steps ({count})",
    "install.tab_evidence": "Why this verdict",
    "install.tab_readme": "Readme",
    "install.tab_readme_n": "Readme ({count})",
    "install.discard": "Discard",
    "install.confirm": "Install",
    "install.select_archive": "Select a mod archive",
    "install.file_filter": "Mod archives ({patterns});;All files (*)",
    "install.summary": "{files} file(s), {size} — {ops} operation(s), {write} to write",
    "install.summary_root": " — {count} outside the mods folder",
    "install.summary_spawn": "\nIn-game spawn: {codes}",
    "install.variant_hint": (
        "This package includes both Add-On and Replace. Tick one or both, then Install."
    ),
    "install.variant_addon": "Add-On (new vehicle)",
    "install.variant_replace": "Replace (overwrite stock car)",
    "install.variant_required": "Tick Add-On, Replace, or both before installing.",
    "install.zone_mods": "mods folder (safe)",
    "install.zone_dlc": "DLC packs under mods (safe)",
    "install.zone_scripts": "scripts folder",
    "install.zone_lml": "LML folder",
    "install.zone_root": "Game folder (allowed files only)",
    "install.zone_external": "Staged for OpenIV (outside game)",
    "install.zone_outside_tip": (
        "Written outside the mods folder because the safety policy allows it"
    ),
    "install.spawn_tip": "Type '{code}' in Menyoo / Simple Trainer to spawn this vehicle",
    "install.dlc_tip": "Will register {entry} in mods/update/update.rpf automatically",
    "install.no_vehicle_meta": "No vehicle metadata found",
    "install.installs_auto": "This package installs fully automatically.",
    "install.no_markers": "The analyzer found no distinctive markers.",
    "install.no_readme": "The package ships no readme.",
    "install.readme_spawn": (
        "In-game spawn: {codes}\n"
        "(Type this in Menyoo / Simple Trainer → Spawn by name)\n\n"
    ),
    # Drop area
    "drop.title": "Drop a mod here",
    "drop.hint": "Supported: {formats}, loose files or a folder",
    # Dashboard
    "dashboard.card_active": "Active installation",
    "dashboard.detecting": "Detecting...",
    "dashboard.badge_checking": "Checking…",
    "dashboard.badge_not_ready": "Fix issues first",
    "dashboard.badge_ready_warn": "Ready — warnings",
    "dashboard.badge_ready": "Ready to launch",
    "dashboard.badge_not_detected": "Pick game folder",
    "dashboard.card_validation": "Issues & blockers",
    "dashboard.essentials_install": "Install missing essentials",
    "dashboard.essentials_manual": "Open ScriptHookV / OpenIV / stability pages",
    "dashboard.essentials_mark_ok": "OK",
    "dashboard.essentials_mark_missing": "Missing",
    "dashboard.change_folder": "Change folder...",
    "dashboard.redetect": "Re-detect",
    "dashboard.create_mods": "Create mods folder",
    "dashboard.launch": "Play GTA V",
    "dashboard.launch_title": "Launch Grand Theft Auto V",
    "dashboard.launch_no_exe": "GTA5.exe was not found in the selected game folder.",
    "dashboard.launch_issues_intro": "Found {count} issue(s) before launching:",
    "dashboard.launch_issues_more": "...and {count} more.",
    "dashboard.launch_anyway_hint": "Launch anyway?",
    "dashboard.launch_started": "Started {exe}. Have fun.",
    "dashboard.essentials_card": "Essentials + Stability Kit",
    "dashboard.essentials_waiting": "Select a GTA V folder to check Story Mode essentials.",
    "dashboard.stat_mods": "Installed mods",
    "dashboard.stat_mods_cap": "tracked by the library",
    "dashboard.stat_components": "Components",
    "dashboard.stat_components_cap": "detected in the game folder",
    "dashboard.stat_backups": "Backups",
    "dashboard.stat_backups_cap": "restore points available",
    "dashboard.card_components": "Detected components",
    "dashboard.col_component": "Component",
    "dashboard.col_status": "Status",
    "dashboard.col_version": "Version",
    "dashboard.col_location": "Location",
    "dashboard.meta": "{platform} - version {version} - detected by {source}",
    "dashboard.components_all": "all essential components present",
    "dashboard.components_missing": "{count} essential component(s) missing",
    "dashboard.no_install": "No GTA V installation selected",
    "dashboard.pick_folder": "Pick the folder containing GTA5.exe to continue.",
    "dashboard.essential_tip": "Essential component - most mods will not load without it",
    "dashboard.missing_line": "[warning] {name} is missing",
    "dashboard.missing_line_url": " - see {url}",
    "dashboard.no_problems": "No problems found. The installation is ready for mods.",
    "dashboard.select_game_folder": "Select the GTA V folder",
    "dashboard.comp_installed": "Installed",
    "dashboard.comp_outdated": "Outdated",
    "dashboard.comp_missing": "Missing",
    "dashboard.comp_unknown": "Unknown",
    "dashboard.comp_missing": "Missing",
    "dashboard.comp_unknown": "Unknown",
    # Backup view
    "backup.undo_last": "Undo last operation",
    "backup.card_points": "Restore points",
    "backup.col_created": "Created",
    "backup.col_reason": "Reason",
    "backup.col_files": "Files",
    "backup.col_size": "Size",
    "backup.card_content": "Snapshot content",
    "backup.select_point": "Select a restore point",
    "backup.restore_this": "Restore this snapshot",
    "backup.delete": "Delete",
    "backup.meta": "{files} file(s), {size} - game folder {root}",
    "backup.meta_mod": " - mod {mod}",
    "backup.marker_restore": "restore",
    "backup.marker_delete": "delete on restore",
    "backup.undo_title": "Undo last operation",
    "backup.undo_body": "Restore the newest snapshot? Files written after it will be replaced.",
    "backup.restore_title": "Restore snapshot",
    "backup.restore_body": "Restore {count} file(s) from\n{label}?",
    "backup.delete_title": "Delete snapshot",
    "backup.delete_body": (
        "Delete this restore point? The operation it protects can no longer be undone."
    ),
    # Log view
    "logs.level": "Level",
    "logs.filter_ph": "Filter messages",
    "logs.follow": "Follow live",
    "logs.reload": "Reload",
    "logs.clear": "Clear",
    "logs.open_file": "Open log file",
    "logs.card_records": "Records",
    "logs.col_time": "Time",
    "logs.col_level": "Level",
    "logs.col_logger": "Logger",
    "logs.col_message": "Message",
    # Conflict view extras
    "conflicts.owned_by": "Currently owned by {owner}",
    # Graphics / NCCVision
    "graphics.title": "Graphics Mods",
    "graphics.subtitle": "Install the single flagship NCCVision Ultimate profile.",
    "graphics.card_pack": "Pack",
    "graphics.pack.nccvision.desc": (
        "NCCVision Ultimate: lighter filmic grade, stronger scene micro-detail + color-only "
        "SMAA and AMD CAS — still depth-free and FPS-safe. No MXAO, DOF, MagicBloom or ENB. "
        "Home = menu, ScrollLock = toggle."
    ),
    "graphics.card_levels": "Visual profile",
    "graphics.level.light": "Light — Natural Clarity",
    "graphics.level.light.hint": "Clean daylight grade only. Near-zero FPS cost.",
    "graphics.level.medium": "Medium — Pacific Drive",
    "graphics.level.medium.hint": "Warmer LA look + FineSharp for chrome/paint. Still light on GPU.",
    "graphics.level.high": "High — Night City Lite",
    "graphics.level.high.hint": "Adds soft ambient glow (no depth bloom). Clear cinematic jump, small FPS cost.",
    "graphics.level.very_high": "Very high — Director's Cut",
    "graphics.level.very_high.hint": (
        "Strongest film curves + MagicBloom + fine grain. Still no depth/DOF/MXAO. "
        "After a crash, start at Medium."
    ),
    "graphics.level.detail_aa": "Detail + AA — Clear Roads & Grass",
    "graphics.level.detail_aa.hint": (
        "Color-only SMAA smooths foliage/edge aliasing, then AMD CAS restores road and "
        "texture detail. "
        "No depth access; tuned for RX 6800."
    ),
    "graphics.level.cinematic_detail_aa": "Cinematic + Detail AA — Ultimate",
    "graphics.level.cinematic_detail_aa.hint": (
        "Filmic teal/orange grade with soft bloom + local contrast + color-only SMAA "
        "and restrained AMD CAS. No rain, MagicBloom, DOF, MXAO or depth."
    ),
    "graphics.install": "Install / update Ultimate",
    "graphics.update_reshade": "Update ReShade",
    "graphics.apply_level": "Apply level",
    "graphics.uninstall": "Uninstall",
    "graphics.status_unknown": "Checking graphics status...",
    "graphics.badge_short_installed": "Installed",
    "graphics.badge_short_missing": "Not installed",
    "graphics.badge_short_conflict": "Blocked by ENB",
    "graphics.badge_short_error": "Error",
    "graphics.badge_installed": "NCCVision Ultimate is active",
    "graphics.badge_installed_unknown_level": "Installed successfully",
    "graphics.badge_not_installed": "Not installed — press Install to add NCCVision Ultimate",
    "graphics.badge_conflict": "Blocked — ENB detected. Remove ENB before installing NCCVision",
    "graphics.badge_error": "Something went wrong — see details below",
    "graphics.card_textures": "Optional selective 2K textures",
    "graphics.road_2k.hint": (
        "Installs two verified 2K Beverly Hills road dictionaries from the official "
        "GTA5-Mods release into mods/x64g.rpf. Stock files stay untouched and uninstall "
        "restores them. Grass stays at its optimized source resolution because repeated "
        "2K grass textures can reduce FPS; Detail + AA keeps it visually crisp instead."
    ),
    "graphics.road_2k.install": "Download + install 2K roads",
    "graphics.road_2k.uninstall": "Restore stock roads",
    "graphics.card_tips": "Safety",
    "graphics.tips": (
        "Do not run ENB together with NCCVision. Use Update ReShade to fetch the "
        "latest signed build from reshade.me (needs 7-Zip). Use 16x anisotropic "
        "filtering for distant roads."
    ),
    # Zombie game mode
    "zombie.title": "Zombie Mode",
    "zombie.subtitle": "A separate Left 4 Dead-style survival mode for GTA V Story Mode.",
    "zombie.checking": "Checking…",
    "zombie.badge_ready": "Ready",
    "zombie.badge_missing": "Needs essentials",
    "zombie.badge_not_installed": "Not installed",
    "zombie.badge_error": "Error",
    "zombie.card_mode": "Simple Zombies Reborn 1.0.5f",
    "zombie.description": (
        "Verified May 2026 rebuild: dense sound-driven hordes, fast and special infected, "
        "survivors, crafting, hunger/thirst, vehicles and a persistent apocalypse profile. "
        "The manager verifies SHA-256 and backs up an existing install before changes."
    ),
    "zombie.install": "Install / update Zombie Mode",
    "zombie.uninstall": "Back up & uninstall",
    "zombie.launch": "Launch GTA V",
    "zombie.card_controls": "How to play",
    "zombie.controls": (
        "In Story Mode press F10 (or controller LB + B) → enable Infection Mode. "
        "Inventory: I or LB + X. Craft C, recipes F, E near a survivor to configure them. "
        "Gunfire attracts larger hordes. Disable Infection Mode before returning to normal Story Mode."
    ),
    "zombie.card_notes": "Compatibility",
    "zombie.notes": (
        "Single-player only; never enter GTA Online with script mods. ScriptHookV, "
        "ScriptHookVDotNet v2 and NativeUI are required. iFruitAddon2 is optional and "
        "only enables the military convoy phone contact."
    ),
    "zombie.ready": "Ready — Simple Zombies Reborn {version} is installed",
    "zombie.missing": "Installed, but missing dependencies: {dependencies}",
    "zombie.not_installed": "Not installed",
    "zombie.error": "Zombie Mode error — see details below",
    # Online mods
    "online.title": "Online Mods",
    "online.subtitle": "Search GTA5-Mods and Nexus Mods, then install with the same safe pipeline.",
    "online.search_ph": "Search, or leave empty to browse the category feed",
    "online.source_gta5mods": "GTA5-Mods",
    "online.source_nexus": "Nexus Mods",
    "online.category_vehicles": "Vehicles",
    "online.category_weapons": "Weapons",
    "online.category_maps": "Maps",
    "online.category_scripts": "Scripts",
    "online.category_player": "Player",
    "online.category_misc": "Misc",
    "online.category_tools": "Tools",
    "online.card_paste": "Paste a link",
    "online.url_ph": "Mod page URL or direct .zip / .rar / .7z download",
    "online.download_url": "Download link",
    "online.paste_hint": (
        "Works with GTA5-Mods pages, Nexus mod pages, and direct CDN links "
        "(files.gta5-mods.com, Nexus CDN)."
    ),
    "online.card_results": "Results",
    "online.col_title": "Mod",
    "online.col_author": "Author",
    "online.col_category": "Category",
    "online.col_stats": "Downloads",
    "online.download": "Download / Install",
    "online.open_page": "Open page",
    "online.empty": "Pick a category to browse, search by name, or paste a download URL above.",
    "online.tips": (
        "Browse Vehicles / Weapons / Maps / Scripts without typing a search. "
        "Add-on DLC packs (content.xml + setup2.xml / dlc.rpf) install into mods "
        "dlcpacks automatically. Loose map/weapon files still need OpenIV. "
        "GTA5-Mods often needs their timed download button — the tool opens the page "
        "when a direct file link is blocked. Nexus API downloads need Premium; otherwise "
        "the Files tab opens so you can download and drag the archive onto Install."
    ),
    "online.ready_install": "Downloaded {name} — opening Install...",
    "online.opened_browser": "Opened the download page in your browser.",
    "online.ready_toast_title": "Download ready",
    "online.ready_toast_body": "{name} is ready on the Install page.",
    "online.missing_file": "Downloaded file not found: {path}",
    # Spawn Center
    "spawn.title": "Spawn Center",
    "spawn.subtitle": "Copy vehicle and ped spawn codes from your installed mods.",
    "spawn.search_ph": "Search by code or mod name",
    "spawn.filter_all": "All",
    "spawn.filter_vehicles": "Vehicles",
    "spawn.filter_peds": "Peds",
    "spawn.card_codes": "Spawn codes",
    "spawn.col_code": "Code",
    "spawn.col_kind": "Type",
    "spawn.col_mod": "Mod",
    "spawn.col_tip": "How to use",
    "spawn.copy": "Copy code",
    "spawn.copied": "Copied '{code}' to the clipboard",
    "spawn.count": "{count} spawn code(s)",
    "spawn.empty": "No spawn codes yet — install a vehicle or ped mod first.",
    "spawn.kind_vehicle": "Vehicle",
    "spawn.kind_ped": "Ped",
    "spawn.card_tips": "How to spawn",
    "spawn.tips_body": (
        "Vehicles: open Menyoo (F8) → Vehicle Spawner → type the code, or use "
        "Simple Trainer → Spawn Vehicle by name.\n\n"
        "Peds / characters: Menyoo → Player → Change model, or PedSelector, "
        "and type the ped code."
    ),
}

_VI: dict[str, str] = {
    "nav.overview": "Tổng quan",
    "nav.mods": "Mod",
    "nav.safety": "An toàn",
    "nav.application": "Ứng dụng",
    "nav.dashboard": "Bảng điều khiển",
    "nav.install": "Cài mod",
    "nav.online": "Mod online",
    "nav.installed": "Mod đã cài",
    "nav.spawn": "Trung tâm spawn",
    "nav.graphics": "Mod đồ họa",
    "nav.game_modes": "Chế độ chơi",
    "nav.zombie": "Chế độ Zombie",
    "nav.conflicts": "Trung tâm xung đột",
    "nav.backup": "Sao lưu & Khôi phục",
    "nav.diagnostics": "Chẩn đoán game",
    "nav.logs": "Nhật ký",
    "nav.settings": "Cài đặt",
    "chrome.safety_first": "v{version} - ưu tiên an toàn",
    "chrome.no_install": "Chưa chọn thư mục game",
    "chrome.game_folder": "Thư mục game:\n{path}",
    "chrome.starting": "Đang khởi động...",
    "chrome.read_only": "File gốc của game chỉ đọc, không ghi đè",
    "chrome.something_wrong": "Có lỗi xảy ra",
    "chrome.error": "Lỗi",
    "common.refresh": "Làm mới",
    "common.browse": "Duyệt...",
    "common.open": "Mở",
    "common.yes": "Có",
    "common.no": "Không",
    "common.search": "Tìm",
    "common.re_scan": "Quét lại",
    "common.expand_all": "Mở rộng",
    "common.collapse_all": "Thu gọn",
    "settings.title": "Cài đặt",
    "settings.subtitle": "Nhận diện game, tùy chọn an toàn và thư mục làm việc.",
    "settings.installs": "Bản cài GTA V",
    "settings.folder": "Thư mục",
    "settings.platform": "Nền tảng",
    "settings.version": "Phiên bản",
    "settings.detected_by": "Phát hiện bởi",
    "settings.detect_again": "Quét lại",
    "settings.use_selected": "Dùng bản đã chọn",
    "settings.choose_manually": "Chọn thủ công...",
    "settings.behaviour": "Hành vi",
    "settings.language": "Ngôn ngữ",
    "settings.language_hint": "Đóng app rồi mở lại sau khi đổi ngôn ngữ.",
    "settings.backups": "Sao lưu",
    "settings.auto_backup": "Tạo snapshot trước mỗi lần ghi file",
    "settings.auto_backup_hint": (
        "Sao lưu file lỏng và script/ASI. Archive dùng chung (mods/*.rpf như "
        "x64e.rpf) không copy nguyên file — gỡ mod sẽ khôi phục từng member, "
        "nên backup không phình ổ đĩa."
    ),
    "settings.safety": "An toàn",
    "settings.confirm_root": "Hỏi trước khi ghi ngoài thư mục mods",
    "settings.diagnostics": "Chẩn đoán",
    "settings.keep_temp": "Giữ thư mục giải nén tạm để gỡ lỗi",
    "settings.crash_monitor_label": "Giám sát crash",
    "settings.crash_monitor": "Theo dõi game khi đang chạy và báo cáo crash",
    "settings.crash_monitor_hint": (
        "Khi game thoát bất thường, tool sẽ thu thập exit code, crash dump của "
        "Windows và log script, rồi chỉ ra mod khả nghi nhất ở trang Chẩn đoán."
    ),
    "settings.snapshots_kept": "Số snapshot giữ mỗi mod",
    "settings.seven_zip": "File 7-Zip",
    "settings.seven_zip_ph": "Đường dẫn tùy chọn tới 7z.exe (dùng cho RAR)",
    "settings.unrar": "File UnRAR",
    "settings.unrar_ph": "Đường dẫn tùy chọn tới UnRAR.exe (tự tìm nếu có WinRAR)",
    "settings.nexus_api_key": "API key Nexus Mods",
    "settings.nexus_api_key_ph": "Dán API key cá nhân",
    "settings.nexus_api_key_hint": (
        "Tạo key tại "
        "<a href='https://www.nexusmods.com/users/myaccount?tab=api%20access'>"
        "nexusmods.com → API Access</a>. "
        "Tải trực tiếp qua API cần Nexus Premium; tài khoản miễn phí vẫn tìm được "
        "và mở tab Files trên trình duyệt."
    ),
    "settings.working_folders": "Thư mục làm việc",
    "settings.app_data": "Dữ liệu ứng dụng",
    "settings.change_data_folder": "Đổi vị trí...",
    "settings.data_folder_hint": (
        "Chọn nơi lưu thư viện SQLite, cài đặt, nhật ký và backup. Tool sẽ sao chép "
        "an toàn toàn bộ dữ liệu rồi chuyển sang chỗ mới sau khi mở lại."
    ),
    "settings.data_folder_title": "Chọn thư mục dữ liệu ứng dụng trống",
    "settings.data_move_title": "Di chuyển dữ liệu ứng dụng",
    "settings.data_move_body": (
        "Sao chép toàn bộ dữ liệu ứng dụng?\n\nTừ: {source}\nĐến: {destination}\n\n"
        "Tool sẽ đóng sau khi sao chép xong. Thư mục cũ chỉ bị xóa sau khi bản ở "
        "vị trí mới khởi động thành công."
    ),
    "settings.data_move_done_title": "Đã chuẩn bị xong dữ liệu",
    "settings.data_move_done_body": (
        "Đã sao chép dữ liệu tới:\n{destination}\n\n"
        "Tool sẽ đóng ngay. Mở lại để dùng vị trí mới."
    ),
    "settings.logs": "Nhật ký",
    "settings.backups_folder": "Sao lưu",
    "settings.temp": "Giải nén tạm",
    "settings.config": "Cấu hình",
    "settings.saved": "Đã lưu cài đặt",
    "settings.language_restart_title": "Đã đổi ngôn ngữ",
    "settings.language_restart_body": (
        "Đã lưu ngôn ngữ: {language}.\n\n"
        "Đóng app rồi mở lại bằng run.bat để áp dụng."
    ),
    "settings.scanning": "Đang tìm bản cài GTA V...",
    "settings.found_installs": "Tìm thấy {count} bản cài",
    "dashboard.title": "Bảng điều khiển",
    "dashboard.subtitle": "Tình trạng cài đặt, thư viện mod và hoạt động gần đây.",
    "install.title": "Cài mod",
    "install.subtitle": (
        "Kéo thả file nén vào, xem trước mọi thay đổi, rồi xác nhận. "
        "Xe, vũ khí, map (add-on DLC), ped và script được cài tự động."
    ),
    "library.title": "Mod đã cài",
    "library.subtitle": (
        "Mọi file liệt kê ở đây do tool ghi và có thể gỡ chính xác từng file."
    ),
    "library.search_ph": "Tìm theo tên, loại hoặc spawn code",
    "library.card": "Mod của bạn",
    "library.details": "Chi tiết",
    "library.verify": "Kiểm tra file",
    "library.disable": "Tắt",
    "library.enable": "Bật",
    "library.uninstall": "Gỡ cài đặt",
    "library.select_mod": "Chọn một mod",
    "library.status_installed": "Đã cài",
    "library.status_disabled": "Đã tắt",
    "library.status_broken": "Thiếu / lệch file",
    "library.status_available": "Có sẵn",
    "library.status_files_missing": "Thiếu file",
    "library.files_header": "Nội dung đã cài",
    "library.files_state": "Trạng thái",
    "library.working": "Đang xử lý...",
    "library.spawn_tip": (
        "Gõ mã này trong trainer (Menyoo / Simple Trainer) để spawn xe:\n{codes}"
    ),
    "library.disable_hint": (
        "Tắt sẽ dời file lỏng ra khỏi thư mục game để không còn load. "
        "Model trong archive dùng chung được trả về stock và gắn lại khi bật "
        "(nếu lần cài đã lưu payload)."
    ),
    "library.uninstall_title": "Gỡ mod",
    "library.uninstall_complete": "Gỡ xong",
    "library.uninstall_complete_body": (
        "Mod đã được xóa khỏi thư viện.\n"
        "Nếu là xe replace, model gốc đã được khôi phục trong archive dùng chung."
    ),
    "library.shared_detail": (
        "Mod này nằm trong archive dùng chung (ví dụ x64e.rpf). "
        "Gỡ sẽ trả model gốc của xe này. "
        "Các xe replace khác dùng chung archive vẫn giữ nguyên. "
        "Viết lại archive có thể mất khoảng một phút — xem thanh tiến trình."
    ),
    "library.staging_detail": (
        "Các file này chỉ được xếp sẵn cho OpenIV, chưa ghi vào game. "
        "Gỡ sẽ xóa chúng khỏi thư viện manager."
    ),
    "library.plain_detail": (
        "Các file manager đã ghi cho mod sẽ bị xóa. "
        "Có sao lưu trước, nên có thể hoàn tác ở Sao lưu & Khôi phục."
    ),
    "library.remove_confirm": "Gỡ {name}?\n\n{count} file đang theo dõi.\n\n{detail}",
    "library.col_mod": "Mod",
    "library.col_category": "Loại",
    "library.col_spawn": "Spawn code",
    "library.col_files": "File",
    "library.col_size": "Dung lượng",
    "library.col_status": "Trạng thái",
    "conflicts.title": "Trung tâm xung đột",
    "conflicts.subtitle": "Trùng spawn code, DLC, file dùng chung và thiếu phụ thuộc.",
    "conflicts.summary": "{count} xung đột trong {categories} nhóm, {blocking} chặn cài.",
    "conflicts.detected": "Xung đột phát hiện",
    "conflicts.col_conflict": "Xung đột",
    "conflicts.col_severity": "Mức độ",
    "conflicts.col_action": "Gợi ý xử lý",
    "conflicts.none": "Không có xung đột.",
    "conflicts.disable": "Tắt mod xung đột",
    "conflicts.disable_pick": "Chọn một dòng xung đột có liệt kê mod trước.",
    "conflicts.disable_confirm": (
        "Tắt {count} mod xung đột? Bạn có thể bật lại mod muốn giữ."
    ),
    "conflicts.disable_hint": "Chọn dòng này rồi bấm Tắt mod xung đột",
    "conflicts.sev_blocking": "Chặn cài",
    "conflicts.sev_warning": "Cảnh báo",
    "conflicts.sev_info": "Thông tin",
    "conflicts.duplicate_vehicle_name": "Trùng tên xe / spawn",
    "conflicts.file_overwrite": "Ghi đè file",
    "conflicts.duplicate_dlc": "Trùng DLC",
    "conflicts.duplicate_gameconfig": "Trùng gameconfig",
    "conflicts.missing_dependency": "Thiếu phụ thuộc",
    "backup.title": "Sao lưu & Khôi phục",
    "backup.subtitle": "Snapshot tạo trước khi cài / gỡ mod.",
    "logs.title": "Nhật ký",
    "logs.subtitle": "Log realtime để gỡ lỗi.",
    "diagnostics.title": "Chẩn đoán game",
    "diagnostics.subtitle": (
        "Phát hiện lỗi GTA V quen thuộc (ERR_GFX_D3D_INIT, ScriptHook, ENB sót, "
        "DLC pack không xác định, entry xe hỏng trong RPF) từ log và thư mục game."
    ),
    "diagnostics.findings": "Kết quả",
    "diagnostics.col_issue": "Vấn đề",
    "diagnostics.col_severity": "Mức độ",
    "diagnostics.col_fix": "Cách xử lý",
    "diagnostics.need_game": "Chọn thư mục GTA V trước",
    "diagnostics.scanning": "Đang quét thư mục game và log...",
    "diagnostics.fixing": "Đang sửa...",
    "diagnostics.clean": "Không thấy dấu hiệu crash quen thuộc",
    "diagnostics.summary": "{errors} lỗi, {warnings} cảnh báo — tổng {total}",
    "diagnostics.summary_status": "{errors} lỗi, {warnings} cảnh báo",
    "diagnostics.sev_error": "Lỗi",
    "diagnostics.sev_warning": "Cảnh báo",
    "diagnostics.sev_info": "Thông tin",
    "diagnostics.sev_ok": "Ổn",
    "diagnostics.cat_crash": "Mã lỗi / crash",
    "diagnostics.cat_graphics": "Mod đồ họa",
    "diagnostics.cat_asi": "ASI / ScriptHook",
    "diagnostics.cat_mods": "Thư mục mods",
    "diagnostics.cat_vehicles": "Xe / RPF",
    "diagnostics.cat_components": "Thành phần",
    "diagnostics.cat_launch": "Tùy chọn chạy game",
    "diagnostics.cat_logs": "Nhật ký",
    "diagnostics.cat_summary": "Tóm tắt",
    "diagnostics.cat_general": "Chung",
    "diagnostics.repair_selected": "Sửa mục đã chọn",
    "diagnostics.fix_unavailable": "Mục này không có sửa tự động",
    "diagnostics.fix_select_first": "Chọn mục có hỗ trợ sửa tự động.",
    "diagnostics.repair_confirm_title": "Áp dụng sửa?",
    "diagnostics.repair_confirm_body": (
        "{title}\n\n{fix}\n\nĐối tượng:\n{targets}\n\n"
        "Sửa an toàn — file gốc game không bị ghi. Tiếp tục?"
    ),
    "diagnostics.repair_done_title": "Đã sửa",
    "diagnostics.finding.mods.orphan_dlcpack.title": "Thư mục DLC pack không xác định: {short}",
    "diagnostics.finding.mods.orphan_dlcpack.detail": (
        "Thư mục này nằm trong mods/update/x64/dlcpacks nhưng không thuộc mod nào "
        "trong thư viện. Sót lại như 'hellcat' sau khi gỡ lỗi thường gây "
        "ERR_SYS_INVALIDRESOURCE hoặc không spawn được. Nếu bạn cài pack này ngoài "
        "manager và vẫn muốn giữ, đừng xóa — hãy import lại vào thư viện."
    ),
    "diagnostics.finding.mods.orphan_dlcpack.fix": (
        "Xóa thư mục pack không xác định trong mods/update/x64/dlcpacks "
        "(và gỡ mục tương ứng trong dlclist). Dùng Sửa mục đã chọn để sửa an toàn."
    ),
    "diagnostics.finding.mods.bad_vehicle_stream.title": "Entry stream xe hỏng: {short}",
    "diagnostics.finding.mods.bad_vehicle_stream.detail": (
        "Trong mods/x64e.rpf → levels/gta5/vehicles.rpf, một hoặc nhiều .yft/.ytd "
        "đang lưu dạng binary thay vì resource. Thường gặp sau replace/gỡ lỗi "
        "(ví dụ gauntlet, baller, f620) và gây ERR_SYS_INVALIDRESOURCE_5."
    ),
    "diagnostics.finding.mods.bad_vehicle_stream.fix": (
        "Khôi phục member gốc từ x64e.rpf của game vào bản copy trong mods. "
        "Dùng Sửa mục đã chọn — file gốc không bị ghi."
    ),
    "diagnostics.finding.mods.replace_members_unhealthy.title": (
        "File replace đã cài có dấu hiệu lỗi: {short}"
    ),
    "diagnostics.finding.mods.replace_members_unhealthy.detail": (
        "Một hoặc nhiều member replace mà thư viện đang theo dõi bị thiếu trong "
        "mods/x64e.rpf hoặc không còn là resource hợp lệ."
    ),
    "diagnostics.finding.mods.replace_members_unhealthy.fix": (
        "Khôi phục member gốc cho các đường dẫn đã liệt kê, hoặc gỡ/cài lại mod replace."
    ),
    # Giám sát phiên chơi (crash monitor)
    "crash.session_started_title": "Đã phát hiện game",
    "crash.session_started_body": "Đang theo dõi {name} — nếu crash sẽ báo tại đây.",
    "crash.detected_title": "Game đã crash",
    "crash.detected_body": (
        "Phiên chơi kéo dài khoảng {minutes} phút.\n{detail}\n"
        "Xem báo cáo đầy đủ ở trang Chẩn đoán."
    ),
    "crash.no_suspect": "Chưa xác định được mod nào là thủ phạm duy nhất.",
    "crash.clean_title": "Game thoát bình thường",
    "crash.clean_body": "Phiên chơi kéo dài khoảng {minutes} phút; không phát hiện crash.",
    "diagnostics.finding.crash.exit_code.title": "Game thoát bất thường (mã {names})",
    "diagnostics.finding.crash.exit_code.detail": (
        "Mã thoát là exception NTSTATUS dạng cảnh báo/lỗi (0x8xxxxxxx hoặc "
        "0xCxxxxxxx) — nghĩa là tiến trình game bị crash chứ không phải người "
        "chơi tự thoát bình thường."
    ),
    "diagnostics.finding.crash.dump.title": "Windows đã ghi crash dump: {short}",
    "diagnostics.finding.crash.dump.detail": (
        "Crash dump là bằng chứng chắc chắn game đã crash."
    ),
    "diagnostics.finding.crash.script_error.title": "Script gây lỗi: {names}",
    "diagnostics.finding.crash.script_error.detail": (
        "ScriptHookVDotNet ghi nhận exception chưa được xử lý từ script này "
        "trong phiên chơi. Script bị hỏng hoặc không tương thích với phiên bản "
        "game/SHVDN hiện tại."
    ),
    "diagnostics.finding.crash.script_error.fix": (
        "Dùng Sửa để tắt mod sở hữu script, hoặc gỡ/cập nhật mod / SHVDN."
    ),
    "diagnostics.finding.crash.script_load.title": "Script không nạp được: {names}",
    "diagnostics.finding.crash.script_load.detail": (
        "Assembly không nạp được, thường do thiếu hoặc quá cũ một thành phần "
        "phụ thuộc (phiên bản ScriptHookVDotNet, NativeUI, ...)."
    ),
    "diagnostics.finding.crash.script_load.fix": (
        "Cài dependency từ Bộ Essentials, hoặc tắt mod bị lỗi."
    ),
    "diagnostics.finding.crash.recent_mods.title": "Mod mới cài gần đây: {names}",
    "diagnostics.finding.crash.recent_mods.detail": (
        "Mod cài trong 48 giờ gần nhất là nghi phạm hàng đầu khi xuất hiện crash mới."
    ),
    "diagnostics.finding.crash.recent_mods.fix": (
        "Dùng Sửa để tắt thật các mod mới rồi mở lại game."
    ),
    "diagnostics.finding.crash.no_evidence.title": (
        "Game crash nhưng không script nào để lại dấu vết"
    ),
    "diagnostics.finding.crash.no_evidence.detail": (
        "Không có lỗi script nào được ghi log. Nguyên nhân thường gặp: plugin "
        ".asi native, mod xe/texture vượt giới hạn bộ nhớ, hoặc ScriptHookV "
        "quá cũ sau khi game cập nhật."
    ),
    "diagnostics.finding.crash.no_evidence.fix": (
        "Đổi tên dinput8.dll thành dinput8.dll.off rồi vào game; nếu hết crash, "
        "bật lại mod theo từng nhóm nhỏ để khoanh vùng."
    ),
    "diagnostics.finding.crash.session_ok.title": "Phiên chơi gần nhất kết thúc bình thường",
    "diagnostics.finding.crash.session_ok.detail": (
        "Không có crash dump và exit code sạch."
    ),
    # Chẩn đoán — mã lỗi crash đã biết
    "diagnostics.finding.sys.invalid_resource.title": (
        "Dữ liệu game lỗi (ERR_SYS_INVALIDRESOURCE_5)"
    ),
    "diagnostics.finding.sys.invalid_resource.detail": (
        "Game từ chối nạp một resource — gần như luôn do file .rpf bị mod/hỏng "
        "(ví dụ mods/x64e.rpf hoặc mods/update/update.rpf), archive ghi dở sau "
        "crash, hoặc xe replace không khớp bản game. Hiếm hơn: file gốc hỏng thật."
    ),
    "diagnostics.finding.sys.invalid_resource.fix": (
        "1) Đổi tên thư mục mods thành mods_off rồi chạy lại. "
        "2) Nếu chạy được, đổi tên lại và thử gỡ/đổi tên mods/x64e.rpf rồi "
        "mods/update/update.rpf từng cái một. "
        "3) Gỡ xe replace cài gần nhất. "
        "4) Steam → Kiểm tra tính toàn vẹn file game. "
        "5) Khởi động lại máy rồi thử lại."
    ),
    "diagnostics.finding.gfx.d3d_init.title": "DirectX không khởi động được (ERR_GFX_D3D_INIT)",
    "diagnostics.finding.gfx.d3d_init.detail": (
        "GTA V không tạo được thiết bị Direct3D. Thường do driver GPU, overlay, "
        "chế độ fullscreen, hoặc mod đồ họa hỏng (ENB/ReShade) — không phải do thiếu model xe."
    ),
    "diagnostics.finding.gfx.d3d_init.fix": (
        "1) Khởi động lại máy. 2) Cập nhật driver GPU. 3) Tắt overlay Discord/Steam/NVIDIA. "
        "4) Thêm -windowed vào commandline.txt. 5) Xóa file ENB sót nếu thiếu d3d11.dll. "
        "6) Tạm đổi tên thư mục mods để thử bản gốc."
    ),
    "diagnostics.finding.gfx.state.title": "Lỗi trạng thái đồ họa (ERR_GFX_STATE)",
    "diagnostics.finding.gfx.state.detail": (
        "GPU mất hoặc từ chối render state — thường do VRAM, driver crash hoặc shader lỗi."
    ),
    "diagnostics.finding.gfx.state.fix": (
        "Giảm cài đặt đồ họa, cập nhật driver, tắt ENB/ReShade, kiểm tra file game trên Steam."
    ),
    "diagnostics.finding.gfx.d3d_reset.title": "Thiết bị Direct3D bị reset (ERR_GFX_D3D_RESET)",
    "diagnostics.finding.gfx.d3d_reset.detail": (
        "Thiết bị đồ họa bị mất giữa phiên chơi (driver timeout, sleep, alt-tab)."
    ),
    "diagnostics.finding.gfx.d3d_reset.fix": (
        "Cập nhật driver GPU, tắt fullscreen optimizations, tránh ép VSync qua ENB."
    ),
    "diagnostics.finding.file.version.title": "Phiên bản file game lệch (ERR_FILE_VERSION)",
    "diagnostics.finding.file.version.detail": (
        "File chương trình và asset không khớp nhau — thường sau update dở hoặc replace lỗi."
    ),
    "diagnostics.finding.file.version.fix": (
        "Kiểm tra tính toàn vẹn file game trong Steam/Rockstar Launcher, rồi rà lại mod."
    ),
    "diagnostics.finding.net.profile.title": "Lỗi mạng / profile online",
    "diagnostics.finding.net.profile.detail": (
        "Không kết nối được dịch vụ Rockstar hoặc profile cục bộ."
    ),
    "diagnostics.finding.net.profile.fix": (
        "Kiểm tra trạng thái Rockstar, tường lửa, và đã đăng nhập launcher chưa."
    ),
    "diagnostics.finding.scripthook.compat.title": "Sự cố Script Hook V",
    "diagnostics.finding.scripthook.compat.detail": (
        "ScriptHookV không nạp được hoặc không khớp bản GTA V này."
    ),
    "diagnostics.finding.scripthook.compat.fix": (
        "Tải bản ScriptHookV khớp phiên bản GTA V, hoặc chờ bản cập nhật."
    ),
    # Chẩn đoán — ENB / ASI / mods
    "diagnostics.finding.enb.present.title": "Phát hiện ENB / proxy đồ họa",
    "diagnostics.finding.enb.present.detail": (
        "Có config ENB và DLL proxy DirectX. Khi không tương thích, chúng hay gây "
        "ERR_GFX_D3D_INIT."
    ),
    "diagnostics.finding.enb.present.fix": (
        "Nếu game không mở được, dùng Sửa mục đã chọn để cách ly enb*.ini / enb*.fx, "
        "hoặc đổi tên d3d11.dll / dxgi.dll thủ công."
    ),
    "diagnostics.finding.enb.orphan_config.title": "Config ENB nhưng thiếu d3d11.dll / dxgi.dll",
    "diagnostics.finding.enb.orphan_config.detail": (
        "Có enblocal.ini / enbseries.ini nhưng không thấy DLL proxy DirectX. "
        "File sót lại kiểu này hay góp phần gây ERR_GFX_D3D_INIT."
    ),
    "diagnostics.finding.enb.orphan_config.fix": (
        "Dùng Sửa mục đã chọn để chuyển enb*.ini / enb*.fx vào "
        "mods/_enb_quarantine_by_manager/ (có thể hoàn tác). "
        "Hoặc cài lại ENB đầy đủ gồm d3d11.dll."
    ),
    "diagnostics.finding.asi.openiv_missing.title": (
        "Thiếu OpenIV.asi trong khi mods/ có nội dung"
    ),
    "diagnostics.finding.asi.openiv_missing.detail": (
        "Không có OpenIV.asi (ASI Loader) thì game bỏ qua thư mục mods."
    ),
    "diagnostics.finding.asi.openiv_missing.fix": (
        "Cài OpenIV.asi vào thư mục gốc game (cùng chỗ GTA5.exe)."
    ),
    "diagnostics.finding.asi.dinput_missing.title": "Thiếu ASI Loader (dinput8.dll)",
    "diagnostics.finding.asi.dinput_missing.detail": (
        "Không có dinput8.dll thì các plugin .asi (kể cả OpenIV.asi) không nạp."
    ),
    "diagnostics.finding.asi.dinput_missing.fix": "Cài ASI Loader vào thư mục gốc game.",
    "diagnostics.finding.asi.scripthook_missing.title": (
        "Thiếu ScriptHookV.dll nhưng có ASI script"
    ),
    "diagnostics.finding.asi.scripthook_missing.detail": (
        "Menyoo / SHVDN cần ScriptHookV.dll khớp bản game."
    ),
    "diagnostics.finding.asi.scripthook_missing.fix": "Cài ScriptHookV.dll tương thích.",
    "diagnostics.finding.mods.missing.title": "Chưa có thư mục mods",
    "diagnostics.finding.mods.missing.detail": (
        "Cài an toàn nằm trong mods/. Nó sẽ được tạo khi cài mod hoặc tạo tay."
    ),
    "diagnostics.finding.mods.x64e_present.detail": (
        "Xe replace được nạp từ bản copy này (qua OpenIV.asi). "
        "Nếu game crash lúc mở, đổi tên mods thành mods_off để thử."
    ),
    "diagnostics.finding.mods.x64e_present.fix": (
        "Tạm đổi tên thư mục mods nếu cần cô lập lỗi đồ họa."
    ),
    "diagnostics.finding.ok.clean.title": "Không thấy dấu hiệu crash quen thuộc",
    "diagnostics.finding.ok.clean.detail": (
        "Log và các lỗi mod đồ họa phổ biến đều sạch. Nếu game vẫn lỗi, "
        "thử đổi tên thư mục mods và kiểm tra file game."
    ),
    # Install view
    "install.card_plan": "Thao tác sẽ thực hiện",
    "install.col_action": "Thao tác",
    "install.col_zone": "Ghi vào đâu",
    "install.col_target": "Đường dẫn đích",
    "install.col_detail": "Chi tiết",
    "install.col_vehicle_source": "Nguồn",
    "install.col_vehicle_handling": "Handling",
    "install.col_vehicle_make": "Hãng",
    "install.kind_confidence": "Nhận diện: {kind} (độ tin cậy {confidence})",
    "install.kind_vehicle_addon": "Xe add-on",
    "install.kind_vehicle_replace": "Xe replace",
    "install.kind_ped": "Nhân vật / ped",
    "install.kind_weapon": "Vũ khí",
    "install.kind_map": "Bản đồ",
    "install.kind_script": "Script",
    "install.kind_asi": "Plugin ASI",
    "install.kind_script_hook_dotnet": "Script ScriptHookVDotNet",
    "install.kind_graphics": "Đồ họa",
    "install.kind_lml": "Gói LML",
    "install.kind_openiv_package": "Gói OpenIV",
    "install.kind_menyoo": "Menyoo",
    "install.kind_trainer": "Trainer",
    "install.kind_zombie": "Zombie",
    "install.kind_sound": "Âm thanh",
    "install.kind_texture": "Gói texture",
    "install.kind_unknown": "Không rõ loại",
    "install.card_package": "Gói mod",
    "install.tab_vehicles": "Xe",
    "install.tab_vehicles_n": "Xe ({count})",
    "install.tab_conflicts": "Xung đột",
    "install.tab_conflicts_n": "Xung đột ({count})",
    "install.tab_manual": "Bước thủ công",
    "install.tab_manual_n": "Bước thủ công ({count})",
    "install.tab_evidence": "Vì sao nhận diện vậy",
    "install.tab_readme": "Readme",
    "install.tab_readme_n": "Readme ({count})",
    "install.discard": "Hủy",
    "install.confirm": "Cài đặt",
    "install.select_archive": "Chọn file mod",
    "install.file_filter": "File mod ({patterns});;Tất cả file (*)",
    "install.summary": "{files} file, {size} — {ops} thao tác, ghi {write}",
    "install.summary_root": " — {count} nằm ngoài thư mục mods",
    "install.summary_spawn": "\nSpawn trong game: {codes}",
    "install.variant_hint": (
        "Gói này có cả Add-On và Replace. Tick một hoặc cả hai, rồi bấm Cài đặt."
    ),
    "install.variant_addon": "Add-On (xe mới)",
    "install.variant_replace": "Replace (thay xe gốc)",
    "install.variant_required": "Tick Add-On, Replace, hoặc cả hai trước khi cài.",
    "install.zone_mods": "thư mục mods (an toàn)",
    "install.zone_dlc": "DLC packs trong mods (an toàn)",
    "install.zone_scripts": "thư mục scripts",
    "install.zone_lml": "thư mục LML",
    "install.zone_root": "Thư mục game (chỉ file được phép)",
    "install.zone_external": "Xếp cho OpenIV (ngoài game)",
    "install.zone_outside_tip": (
        "Ghi ngoài thư mục mods vì chính sách an toàn cho phép"
    ),
    "install.spawn_tip": "Gõ '{code}' trong Menyoo / Simple Trainer để spawn xe này",
    "install.dlc_tip": "Sẽ tự đăng ký {entry} vào mods/update/update.rpf",
    "install.no_vehicle_meta": "Không thấy metadata xe",
    "install.installs_auto": "Gói này cài hoàn toàn tự động.",
    "install.no_markers": "Không tìm thấy dấu hiệu đặc trưng.",
    "install.no_readme": "Gói không kèm readme.",
    "install.readme_spawn": (
        "Spawn trong game: {codes}\n"
        "(Gõ trong Menyoo / Simple Trainer → Spawn by name)\n\n"
    ),
    # Drop area
    "drop.title": "Thả mod vào đây",
    "drop.hint": "Hỗ trợ: {formats}, file rời hoặc cả thư mục",
    # Dashboard
    "dashboard.card_active": "Bản cài đang dùng",
    "dashboard.detecting": "Đang nhận diện...",
    "dashboard.badge_checking": "Đang kiểm tra…",
    "dashboard.badge_not_ready": "Cần sửa trước",
    "dashboard.badge_ready_warn": "Sẵn sàng — có cảnh báo",
    "dashboard.badge_ready": "Sẵn sàng chơi",
    "dashboard.badge_not_detected": "Chọn thư mục game",
    "dashboard.card_validation": "Vấn đề & chặn cài",
    "dashboard.essentials_install": "Cài essentials còn thiếu",
    "dashboard.essentials_mark_ok": "OK",
    "dashboard.essentials_mark_missing": "Thiếu",
    "dashboard.change_folder": "Đổi thư mục...",
    "dashboard.redetect": "Quét lại",
    "dashboard.create_mods": "Tạo thư mục mods",
    "dashboard.launch": "Chơi GTA V",
    "dashboard.launch_title": "Khởi chạy Grand Theft Auto V",
    "dashboard.launch_no_exe": "Không thấy GTA5.exe trong thư mục game đã chọn.",
    "dashboard.launch_issues_intro": "Phát hiện {count} vấn đề trước khi mở game:",
    "dashboard.launch_issues_more": "...và thêm {count} mục nữa.",
    "dashboard.launch_anyway_hint": "Vẫn mở game?",
    "dashboard.launch_started": "Đã mở {exe}. Chơi vui.",
    "dashboard.essentials_card": "Bộ Essentials + Ổn định",
    "dashboard.essentials_waiting": "Chọn thư mục GTA V để kiểm tra essentials Story Mode.",
    "dashboard.essentials_install": "Cài essentials còn thiếu",
    "dashboard.essentials_manual": "Mở trang ScriptHookV / OpenIV / ổn định",
    "dashboard.stat_mods": "Mod đã cài",
    "dashboard.stat_mods_cap": "được thư viện theo dõi",
    "dashboard.stat_components": "Thành phần",
    "dashboard.stat_components_cap": "phát hiện trong thư mục game",
    "dashboard.stat_backups": "Sao lưu",
    "dashboard.stat_backups_cap": "điểm khôi phục khả dụng",
    "dashboard.card_components": "Thành phần phát hiện",
    "dashboard.col_component": "Thành phần",
    "dashboard.col_status": "Trạng thái",
    "dashboard.col_version": "Phiên bản",
    "dashboard.col_location": "Vị trí",
    "dashboard.card_validation": "Vấn đề & chặn cài",
    "dashboard.meta": "{platform} — phiên bản {version} — phát hiện bởi {source}",
    "dashboard.badge_not_ready": "Cần sửa trước",
    "dashboard.badge_ready_warn": "Sẵn sàng — có cảnh báo",
    "dashboard.badge_ready": "Sẵn sàng chơi",
    "dashboard.badge_not_detected": "Chọn thư mục game",
    "dashboard.components_all": "đủ các thành phần thiết yếu",
    "dashboard.components_missing": "thiếu {count} thành phần thiết yếu",
    "dashboard.no_install": "Chưa chọn bản cài GTA V",
    "dashboard.pick_folder": "Chọn thư mục chứa GTA5.exe để tiếp tục.",
    "dashboard.essential_tip": "Thành phần thiết yếu — thiếu nó thì đa số mod không chạy",
    "dashboard.missing_line": "[cảnh báo] Thiếu {name}",
    "dashboard.missing_line_url": " — xem {url}",
    "dashboard.no_problems": "Không có vấn đề. Bản cài sẵn sàng để mod.",
    "dashboard.select_game_folder": "Chọn thư mục GTA V",
    "dashboard.comp_installed": "Đã cài",
    "dashboard.comp_outdated": "Cũ",
    "dashboard.comp_missing": "Thiếu",
    "dashboard.comp_unknown": "Không rõ",
    # Backup view
    "backup.undo_last": "Hoàn tác thao tác gần nhất",
    "backup.card_points": "Điểm khôi phục",
    "backup.col_created": "Tạo lúc",
    "backup.col_reason": "Lý do",
    "backup.col_files": "File",
    "backup.col_size": "Dung lượng",
    "backup.card_content": "Nội dung snapshot",
    "backup.select_point": "Chọn một điểm khôi phục",
    "backup.restore_this": "Khôi phục snapshot này",
    "backup.delete": "Xóa",
    "backup.meta": "{files} file, {size} — thư mục game {root}",
    "backup.meta_mod": " — mod {mod}",
    "backup.marker_restore": "khôi phục",
    "backup.marker_delete": "xóa khi khôi phục",
    "backup.undo_title": "Hoàn tác thao tác gần nhất",
    "backup.undo_body": "Khôi phục snapshot mới nhất? File ghi sau thời điểm đó sẽ bị thay.",
    "backup.restore_title": "Khôi phục snapshot",
    "backup.restore_body": "Khôi phục {count} file từ\n{label}?",
    "backup.delete_title": "Xóa snapshot",
    "backup.delete_body": (
        "Xóa điểm khôi phục này? Thao tác nó bảo vệ sẽ không thể hoàn tác nữa."
    ),
    # Log view
    "logs.level": "Mức",
    "logs.filter_ph": "Lọc nội dung",
    "logs.follow": "Theo dõi trực tiếp",
    "logs.reload": "Tải lại",
    "logs.clear": "Xóa",
    "logs.open_file": "Mở file log",
    "logs.card_records": "Bản ghi",
    "logs.col_time": "Thời gian",
    "logs.col_level": "Mức",
    "logs.col_logger": "Nguồn",
    "logs.col_message": "Nội dung",
    # Conflict view extras
    "conflicts.owned_by": "Đang thuộc mod {owner}",
    # Graphics / NCCVision
    "graphics.title": "Mod đồ họa",
    "graphics.subtitle": "Cài một profile NCCVision Ultimate cao cấp duy nhất.",
    "graphics.card_pack": "Gói",
    "graphics.pack.nccvision.desc": (
        "NCCVision Ultimate: grade phim nhạt hơn, micro-detail cảnh vật rõ hơn + SMAA màu "
        "và AMD CAS — vẫn không đọc depth, nhẹ FPS. Không MXAO, DOF, MagicBloom hay ENB. "
        "Home = menu, ScrollLock = bật/tắt."
    ),
    "graphics.card_levels": "Gói hình ảnh",
    "graphics.level.light": "Nhẹ — Natural Clarity",
    "graphics.level.light.hint": "Chỉ grade ban ngày sạch. Gần như không mất FPS.",
    "graphics.level.medium": "Trung bình — Pacific Drive",
    "graphics.level.medium.hint": "LA ấm hơn + FineSharp cho sơn/chrome. GPU vẫn nhẹ.",
    "graphics.level.high": "Cao — Night City Lite",
    "graphics.level.high.hint": "Thêm ambient glow mềm (không bloom đụng depth). Nhảy cinematic rõ, mất FPS nhỏ.",
    "graphics.level.very_high": "Rất cao — Director's Cut",
    "graphics.level.very_high.hint": (
        "Curve phim mạnh + MagicBloom + grain mịn. Vẫn không depth/DOF/MXAO. "
        "Sau crash nên bắt đầu từ Trung bình."
    ),
    "graphics.level.detail_aa": "Chi tiết + AA — Rõ cỏ và mặt đường",
    "graphics.level.detail_aa.hint": (
        "SMAA chỉ dùng màu làm mượt răng cưa lá/cỏ, sau đó AMD CAS phục hồi độ nét "
        "đường và texture. "
        "Không đọc depth; đã cân cho RX 6800."
    ),
    "graphics.level.cinematic_detail_aa": "Cinematic + Chi tiết AA — Ultimate",
    "graphics.level.cinematic_detail_aa.hint": (
        "Grade phim teal/cam + bloom mềm + local contrast + SMAA màu và AMD CAS nhẹ. "
        "Không mưa, MagicBloom, DOF, MXAO hay depth."
    ),
    "graphics.install": "Cài / cập nhật Ultimate",
    "graphics.update_reshade": "Cập nhật ReShade",
    "graphics.apply_level": "Áp cấp độ",
    "graphics.uninstall": "Gỡ mod",
    "graphics.status_unknown": "Đang kiểm tra đồ họa...",
    "graphics.badge_short_installed": "Đã cài",
    "graphics.badge_short_missing": "Chưa cài",
    "graphics.badge_short_conflict": "Bị ENB chặn",
    "graphics.badge_short_error": "Lỗi",
    "graphics.badge_installed": "NCCVision Ultimate đang hoạt động",
    "graphics.badge_installed_unknown_level": "Đã cài thành công",
    "graphics.badge_not_installed": "Chưa cài — bấm Cài để thêm NCCVision Ultimate",
    "graphics.badge_conflict": "Bị chặn — phát hiện ENB. Gỡ ENB trước khi cài NCCVision",
    "graphics.badge_error": "Có lỗi — xem chi tiết bên dưới",
    "graphics.card_textures": "Texture 2K chọn lọc (tùy chọn)",
    "graphics.road_2k.hint": (
        "Cài hai bộ texture đường Beverly Hills 2K đã xác minh từ bản chính thức "
        "GTA5-Mods vào mods/x64g.rpf. Không sửa file game gốc và có thể khôi phục khi gỡ. "
        "Cỏ giữ độ phân giải nguồn tối ưu vì cỏ 2K lặp dày có thể giảm FPS; gói Chi tiết + AA "
        "sẽ làm cỏ rõ hơn bằng SMAA + CAS."
    ),
    "graphics.road_2k.install": "Tải + cài đường 2K",
    "graphics.road_2k.uninstall": "Khôi phục đường gốc",
    "graphics.card_tips": "An toàn",
    "graphics.tips": (
        "Không chạy ENB cùng NCCVision. Dùng Cập nhật ReShade để tải bản signed mới "
        "từ reshade.me (cần 7-Zip). Đặt Anisotropic Filtering 16x để đường xa rõ."
    ),
    # Zombie game mode
    "zombie.title": "Chế độ Zombie",
    "zombie.subtitle": "Chế độ sinh tồn riêng kiểu Left 4 Dead cho GTA V Story Mode.",
    "zombie.checking": "Đang kiểm tra…",
    "zombie.badge_ready": "Sẵn sàng",
    "zombie.badge_missing": "Thiếu essentials",
    "zombie.badge_not_installed": "Chưa cài",
    "zombie.badge_error": "Lỗi",
    "zombie.card_mode": "Simple Zombies Reborn 1.0.5f",
    "zombie.description": (
        "Bản rebuild tháng 5/2026 đã xác minh: horde đông bị thu hút bởi tiếng súng, zombie "
        "nhanh và đặc biệt, đồng đội, chế tạo, đói/khát, xe và hồ sơ tận thế riêng. Tool "
        "kiểm tra SHA-256 và sao lưu bản cũ trước khi thay đổi."
    ),
    "zombie.install": "Cài / cập nhật chế độ Zombie",
    "zombie.uninstall": "Sao lưu & gỡ",
    "zombie.launch": "Mở GTA V",
    "zombie.card_controls": "Cách chơi",
    "zombie.controls": (
        "Trong Story Mode nhấn F10 (hoặc tay cầm LB + B) → bật Infection Mode. "
        "Túi đồ: I hoặc LB + X. C chế tạo, F xem công thức, E gần đồng đội để chỉnh lệnh. "
        "Tiếng súng sẽ kéo horde lớn tới. Tắt Infection Mode trước khi quay lại Story Mode bình thường."
    ),
    "zombie.card_notes": "Tương thích",
    "zombie.notes": (
        "Chỉ chơi đơn; tuyệt đối không vào GTA Online khi đang bật script mod. Cần "
        "ScriptHookV, ScriptHookVDotNet v2 và NativeUI. iFruitAddon2 chỉ là tùy chọn cho "
        "liên lạc đoàn xe quân sự qua điện thoại."
    ),
    "zombie.ready": "Sẵn sàng — đã cài Simple Zombies Reborn {version}",
    "zombie.missing": "Đã cài nhưng còn thiếu: {dependencies}",
    "zombie.not_installed": "Chưa cài",
    "zombie.error": "Chế độ Zombie bị lỗi — xem chi tiết bên dưới",
    # Online mods
    "online.title": "Mod online",
    "online.subtitle": "Tìm trên GTA5-Mods và Nexus Mods, rồi cài bằng pipeline an toàn sẵn có.",
    "online.search_ph": "Tìm kiếm, hoặc để trống để xem bảng xếp hạng danh mục",
    "online.source_gta5mods": "GTA5-Mods",
    "online.source_nexus": "Nexus Mods",
    "online.category_vehicles": "Phương tiện",
    "online.category_weapons": "Vũ khí",
    "online.category_maps": "Bản đồ",
    "online.category_scripts": "Script",
    "online.category_player": "Nhân vật",
    "online.category_misc": "Khác",
    "online.category_tools": "Công cụ",
    "online.card_paste": "Dán link",
    "online.url_ph": "Link trang mod hoặc link tải .zip / .rar / .7z",
    "online.download_url": "Tải link",
    "online.paste_hint": (
        "Hỗ trợ trang GTA5-Mods, trang Nexus, và link CDN trực tiếp "
        "(files.gta5-mods.com, Nexus CDN)."
    ),
    "online.card_results": "Kết quả",
    "online.col_title": "Mod",
    "online.col_author": "Tác giả",
    "online.col_category": "Danh mục",
    "online.col_stats": "Lượt tải",
    "online.download": "Tải / Cài",
    "online.open_page": "Mở trang",
    "online.empty": "Chọn danh mục để duyệt, tìm theo tên, hoặc dán link tải ở trên.",
    "online.tips": (
        "Duyệt Phương tiện / Vũ khí / Map / Script mà không cần gõ tìm. "
        "Pack add-on DLC (content.xml + setup2.xml / dlc.rpf) được cài tự động vào "
        "mods/dlcpacks. File map/vũ khí lỏng vẫn cần OpenIV. "
        "GTA5-Mods thường bắt bấm nút tải có đếm giờ — tool sẽ mở trang khi không lấy "
        "được link file trực tiếp. Nexus API tải thẳng cần Premium; không thì mở tab "
        "Files để tải rồi kéo file vào Cài mod."
    ),
    "online.ready_install": "Đã tải {name} — đang mở Cài mod...",
    "online.opened_browser": "Đã mở trang tải trên trình duyệt.",
    "online.ready_toast_title": "Tải xong",
    "online.ready_toast_body": "{name} đã sẵn sàng ở trang Cài mod.",
    "online.missing_file": "Không thấy file đã tải: {path}",
    # Spawn Center
    "spawn.title": "Trung tâm spawn",
    "spawn.subtitle": "Copy mã spawn xe và ped từ các mod đã cài.",
    "spawn.search_ph": "Tìm theo mã hoặc tên mod",
    "spawn.filter_all": "Tất cả",
    "spawn.filter_vehicles": "Xe",
    "spawn.filter_peds": "Ped",
    "spawn.card_codes": "Mã spawn",
    "spawn.col_code": "Mã",
    "spawn.col_kind": "Loại",
    "spawn.col_mod": "Mod",
    "spawn.col_tip": "Cách dùng",
    "spawn.copy": "Copy mã",
    "spawn.copied": "Đã copy '{code}' vào clipboard",
    "spawn.count": "{count} mã spawn",
    "spawn.empty": "Chưa có mã spawn — hãy cài mod xe hoặc ped trước.",
    "spawn.kind_vehicle": "Xe",
    "spawn.kind_ped": "Ped",
    "spawn.card_tips": "Cách spawn",
    "spawn.tips_body": (
        "Xe: mở Menyoo (F8) → Vehicle Spawner → gõ mã, hoặc Simple Trainer → "
        "Spawn Vehicle theo tên.\n\n"
        "Ped / nhân vật: Menyoo → Player → Change model, hoặc PedSelector, "
        "rồi gõ mã ped."
    ),
}

_CATALOGS: Mapping[str, Mapping[str, str]] = {
    "en": _EN,
    "vi": _VI,
}


def get_language() -> str:
    """Return the active language code (``en`` or ``vi``)."""
    return _language


def set_language(code: str) -> str:
    """Activate ``code`` when supported; otherwise keep English.

    Returns:
        The language that is now active.
    """
    global _language
    normalised = (code or _DEFAULT).strip().lower()
    if normalised not in _CATALOGS:
        normalised = _DEFAULT
    _language = normalised
    return _language


def t(key: str, **values: object) -> str:
    """Translate ``key`` for the active language, falling back to English."""
    catalog = _CATALOGS.get(_language, _EN)
    template = catalog.get(key) or _EN.get(key) or key
    if values:
        try:
            return template.format(**values)
        except (KeyError, ValueError):
            return template
    return template


def language_display_name(code: str) -> str:
    """Return the human label for a language code."""
    for item_code, label in SUPPORTED_LANGUAGES:
        if item_code == code:
            return label
    return code
