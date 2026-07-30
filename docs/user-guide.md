# User guide

## First run

The Dashboard opens on the installation the detector considers most credible. It
shows the platform (Steam, Epic, Rockstar or manual), the executable version, the
components it found, and the ones that are missing. If detection picked the wrong
folder, choose the right one in Settings - a folder is only accepted when it
contains `GTA5.exe`, `common.rpf`, `x64a.rpf`, `update/` and `x64/`.

Install the essentials before installing mods. ScriptHookV and the ASI loader
(`dinput8.dll`) are prerequisites for almost everything; a missing one shows up
as a dependency warning on every plan that needs it.

## Installing a mod

Drop an archive anywhere in the window, or use the Install page. The manager
extracts it into a temporary workspace and analyses it before showing you
anything. The preview then tells you:

- **Classification and confidence** - what kind of mod this is, plus the evidence
  each rule contributed. Low confidence means the archive is unusual, not that
  installation will fail.
- **File operations** - every destination, marked as a new file or a replacement.
- **Vehicles** - spawn codes, manufacturer, handling ids and DLC packs. The spawn
  code is what you type in a trainer, and it is also shown as a column on the
  Installed Mods page. See [Finding the spawn code](#finding-the-spawn-code).
- **Conflicts** - see below.
- **Manual steps** - anything the manager cannot do safely by itself, such as
  importing meta files into an archive that has no automatic mapping.

Nothing is written until you confirm. On confirmation a backup snapshot is taken,
then the operations run inside a transaction that rolls back completely if any
step fails.

## Mod types

**Add-on vehicles** ship their own DLC pack (a folder with `setup2.xml` and
`content.xml`). They install to `mods/update/x64/dlcpacks/<pack>/`. The manager
also copies `update/update.rpf` into `mods/` if needed and appends the pack to
`dlclist.xml` automatically. Uninstall removes that entry (or restores the
mods copy of `update.rpf` when no other mod still shares it).

**Replace vehicles** overwrite an existing model's stream assets (`.yft` /
`.ytd`). The manager copies `x64e.rpf` into `mods/` if needed, then imports the
meshes into that mods copy (`levels/gta5/vehicles.rpf`). The original archive
under the game root stays untouched. Meta files that still need OpenIV remain
manual steps. OpenIV.asi must be present for the game to load the mods copy.

### Finding the spawn code

The spawn code is the model name, not the mod title: the "W-Motors Lykan
Hypersport" pack spawns as `lykan`. The manager looks for it in this order:

1. Phrases in the packaged ReadMe / INSTALL / INSTRUCTION text
   (`spawn by name: hellcat`, `[spawncode] = amrevu23mg`, `type "fpino"`...).
2. `vehicles.meta`, when the package ships a real one.
3. Model file names (``.yft``) and names still readable inside `dlc.rpf`.
4. The DLC pack folder name.

A package that offers both an add-on and a replacement variant installs the
**Replace** half and skips the Add-On half (no `dlclist` registration). The
spawn code shown is then the vanilla car being replaced (for example
`gauntlet`, not `hellcat`).

The Install preview shows the code in the summary, in the Vehicles tab (with a
Source column), and again at the top of the Readme tab. Installed Mods keeps a
Spawn code column too.

**Scripts** (`.dll` written for ScriptHookVDotNet, or `.cs`/`.vb`/`.lua` sources)
go to `scripts/` in the game root along with their `.ini` configuration.

**ASI plugins** install to the game root next to `dinput8.dll`.

**Graphics mods** (ReShade, ENB) install their entry point DLLs and presets to the
game root and the whitelisted `reshade*/` and `enbseries/` folders.

**OpenIV packages** (`.oiv`) are read from `package.xml` / `assembly.xml`. Steps
that copy files into `mods/` are performed automatically. Vehicle stream replace
and add-on `dlclist.xml` registration edit the **mods copy** of the archive
(never the original under the game root). Steps that still need OpenIV (unmapped
meta inside other archives) are listed as manual instructions.

**Map mods** vary the most. Expect manual OpenIV steps for content the manager
cannot map automatically.

## Conflicts

| Severity | Meaning |
| --- | --- |
| Blocking | Installation is refused until resolved |
| Warning | Installation proceeds; read it first |
| Info | Worth knowing, harmless |

Blocking conflicts are the ones that break a save or the game itself: a spawn
code already used by another mod, a DLC pack name already registered, a second
custom `gameconfig.xml`, or a destination that is an original game file.

Warnings include files that will be replaced (with the owning mod named), a
handling id declared twice in the same archive, several files targeting the same
destination, and missing dependencies.

The Conflict Center audits everything currently installed, so you can find a
clash that only appeared after two separately safe installations.

## Undo, restore and uninstall

- **Undo** reverts the most recent installation using the snapshot taken before
  it, including files it replaced.
- **Restore** applies any earlier snapshot, listed with its timestamp and the
  files it holds.
- **Uninstall** removes exactly what the installation recorded, then the
  directories it created. Files it did not create are left alone.
- Snapshots are pruned by generation count, configurable in Settings.

## Settings

| Setting | Effect |
| --- | --- |
| Game folder | The active installation |
| Auto backup | Snapshot before every mutating operation (leave on) |
| Confirm root installs | Ask before writing anything outside `mods/` |
| Keep extracted temp | Keep extraction workspaces for debugging |
| Backup generations | How many snapshots to keep per mod |
| 7-Zip path | External `7z.exe`, used as a fallback for `.rar` archives |
| UnRAR path | External `UnRAR.exe`, only needed for a portable WinRAR |

## Troubleshooting

**A plan is refused.** The issue code says why; the table at the end of
[safety.md](safety.md) explains each one. The usual cause is an archive that
expects to be installed over the original files rather than into `mods/`.

**A `.rar` archive will not extract.** RAR is the one format Python cannot open
on its own. A normal WinRAR or 7-Zip installation is found automatically; if
you use a portable copy, point Settings at its `UnRAR.exe` or `7z.exe`.
Repacking the archive as `.zip` always works too.

**The game crashes after installing several mods.** Check the Conflict Center
first, then the component list on the Dashboard - a large add-on collection
usually needs a Packfile Limit Adjuster, a Heap Adjuster and a custom
`gameconfig.xml`. Use Undo to remove the most recent change and confirm.

**Something went wrong and the log matters.** The Log Viewer shows the live ring
buffer with filtering; the full rotating log is in the `logs/` folder of the data
directory, whose location is shown in Settings. Start with `--debug` for more
detail.
