# Safety model

The manager is built around one non-negotiable rule: **original game archives
are never modified**. This document describes how that rule is implemented, and
where to look when a plan is refused.

## What is protected

`RootInstallPolicy` (`gta_mod_manager/plugins/gta_v/root_policy.py`) treats two
categories as untouchable:

1. Named originals, from `constants.PROTECTED_ROOT_FILES`: `GTA5.exe`,
   `GTA5_Enhanced.exe`, `PlayGTAV.exe`, `GTAVLauncher.exe`,
   `GTAVLanguageSelect.exe`, `steam_api64.dll`, `GFSDK_ShadowLib.win64.dll`,
   `index.bin`, `common.rpf`.
2. Any `.rpf` archive whose path does not pass through the `mods` folder. This
   covers `update/update.rpf`, `x64a.rpf` … `x64w.rpf`, and every DLC packfile
   shipped with the game.

Additionally, a destination that descends *into* an `.rpf` - for example
`mods/update/update.rpf/common/data/handling.meta` - is refused as a *filesystem*
path, because an RPF is a container, not a directory. Vehicle stream replace
assets (`.yft` / `.ytd`) are handled differently: the manager copies the outer
archive into `mods/` (if missing), then imports members into that **mods copy**
via an out-of-band `archive_member_path`. Original archives under the game root
remain read-only. Assets the manager cannot map automatically still become a
**manual step** in the preview.

## Where mods go

| Content | Destination |
| --- | --- |
| Add-on DLC packs | `mods/update/x64/dlcpacks/<pack>/` |
| Replacement vehicle meshes (`.yft` / `.ytd`) | Auto-imported into `mods/x64e.rpf` → `levels/gta5/vehicles.rpf` |
| Other replacement game assets | Manual OpenIV step (or `mods/` mirroring when already structured) |
| `.NET`/ASI scripts | `scripts/` in the game root |
| ASI plugins and their `.ini` | game root |
| ScriptHookV, ScriptHookVDotNet, ASI loader | game root |
| ReShade / ENB entry points and presets | game root, `reshade*/`, `enbseries/` |
| Lenny's Mod Loader content | `lml/` |

## The root whitelist

Only these may be written to the game root. Everything else must go into
`mods/`. Patterns come from `constants.ALLOWED_ROOT_FILE_PATTERNS`:

```
ScriptHookV.dll        dinput8.dll
ScriptHookVDotNet*.dll ScriptHookVDotNet*.ini ScriptHookVDotNet*.xml
*.asi                  *.ini                  *.log
openIV.asi             PackfileLimitAdjuster.asi  GTAVHeapAdjuster.asi
d3d11.dll  d3d12.dll   dxgi.dll               d3dcompiler_47.dll
ReShade*.ini  ReShadePreset*.ini
enbseries.ini  enblocal.ini  enbhost.exe
```

And these folders, from `constants.ALLOWED_ROOT_DIRECTORIES`:

```
scripts  lml  reshade  reshade-shaders  reshade-presets
enbseries  enbcache  menyoostuff  asi  plugins  openivscripts
```

A protected name always wins over a pattern: `common.rpf` is not installable
even though `*.rpf` never appears in the whitelist, and `dinput8.dll` is allowed
while `steam_api64.dll` is not.

## The five gates a file passes

1. **Extraction** - `TempWorkspace` extracts into an isolated folder under
   `temp/`. `fs.safe_join` rejects any archive entry whose path escapes the
   workspace (zip-slip), aborting the scan with a `SafetyViolationError`.
2. **Mapping** - the plugin's `decide_target` maps each packaged file to a zone
   (`MODS_FOLDER`, `DLC_PACKS`, `SCRIPTS_FOLDER`, `LML_FOLDER`, `GAME_ROOT`) or
   refuses it with a reason shown in the preview.
3. **Plan validation** - `PlanValidator` re-checks every operation
   independently of the plugin. It rejects: an empty plan, a target outside the
   game folder, a protected file, a path inside an `.rpf`, a zone/destination
   mismatch, a root target that is not whitelisted, a missing source file, and -
   at install time - any blocking conflict.
4. **Backup** - `BackupService` snapshots every file the plan would replace
   before the transaction starts. Directory creations are not snapshotted; the
   transaction removes them on rollback instead.
5. **Transaction** - `Transaction` journals each completed step. On any error
   the journal is replayed backwards: created files are deleted, replaced files
   are restored from the scratch copy, and empty created directories are
   removed. A directory that still has content is left alone.

Because gate 3 runs on the finished plan, a buggy or malicious plugin cannot
bypass the safety rule.

## Recovering

- **Undo** in the Backup page restores the snapshot taken before the most recent
  installation.
- **Restore** applies any earlier snapshot.
- **Uninstall** removes exactly the files recorded in the installation, then the
  directories it created, leaving anything it did not create in place.
- If a rollback itself partially fails, a `RollbackError` lists the individual
  failures and the remaining steps are still attempted, so the folder ends up as
  close to the original state as the filesystem permits.

## Why refusals happen

| Issue code | Meaning |
| --- | --- |
| `plan.empty` | Nothing installable was found in the archive |
| `plan.outside_game` | A destination is outside the game folder |
| `plan.protected_target` | A destination is an original game file |
| `plan.inside_archive` | A destination points inside an `.rpf` |
| `plan.zone_mismatch` | Declared as a mods-folder install but targets the root |
| `plan.root_not_whitelisted` | Root destination is not on the whitelist |
| `plan.missing_source` | The extracted source file disappeared |
| `plan.rpf_copy_source` | RPF copy source is not an original under the game root |
| `plan.rpf_copy_target` | RPF copy target is not a mods-folder `.rpf` |
| `plan.rpf_import_target` | RPF import target is not a mods-folder `.rpf` |
| `plan.rpf_import_empty` | RPF import listed no members |
| `plan.rpf_member_path` | Archive member path is invalid |
| `plan.external_target` | Staging outside the application data folder |
| `plan.blocking_conflict` | A blocking conflict must be resolved first |
