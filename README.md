# GTA V Ultimate Mod Manager

A safety-first mod manager for *Grand Theft Auto V*, built on Python and PySide6.
It detects your installation, analyses an archive before touching anything, shows
you exactly what will be written, and keeps a reversible snapshot of every file
it replaces.

The manager does **not** copy files blindly. Every archive goes through the same
pipeline: extract into a temporary workspace, build a file inventory, classify
the mod, resolve dependencies, map every file to a destination, validate the plan
against the safety rules, and only then write - inside a journalled transaction
that rolls back on the first error.

## The absolute safety rule

Original game archives are never modified. Ever.

1. Mod content is installed into `Grand Theft Auto V/mods/`, so the original
   `update.rpf`, `x64*.rpf` and `common.rpf` stay byte-identical.
2. Only a short whitelist may be written to the game root: `ScriptHookV.dll`,
   `dinput8.dll`, `*.asi`, `ScriptHookVDotNet*`, ReShade/ENB entry points, and
   the `scripts/`, `lml/`, `reshade*/`, `enbseries/` folders. See
   [docs/safety.md](docs/safety.md) for the exact list.
3. Original `.rpf` archives under the game root are never modified. Vehicle
   replace meshes (`.yft` / `.ytd`) are imported into a **mods-folder copy** of
   `x64e.rpf` (created automatically if missing). A filesystem path that
   descends *into* an `.rpf` is still rejected; archive members travel in a
   separate field. Unmapped archive content remains a manual OpenIV step.
4. A backup snapshot is taken before the first byte is overwritten.
5. Every operation is logged and appears in the Backup page, where it can be
   undone or restored.

These rules are enforced by `PlanValidator`, not by convention. Even a
third-party plugin that builds an unsafe plan cannot get it executed.

## Features

| Area | What it does |
| --- | --- |
| Game detection | Registry, Steam (`libraryfolders.vdf`), Epic manifests, Rockstar Launcher and common install folders, plus manual selection with validation |
| Component detection | Finds ScriptHookV, ScriptHookVDotNet, ASI Loader, OpenIV.asi, Packfile Limit Adjuster, Heap Adjuster, gameconfig, LML, NativeUI, Menyoo, ReShade, ENB and reports versions and gaps |
| Mod analysis | Extracts `zip`, `7z`, `rar` and `oiv`, walks the tree, and classifies the mod with a confidence score and the evidence behind it |
| Vehicle support | Parses `vehicles.meta`, `handling.meta`, `carcols.meta`, `carvariations.meta`, `content.xml`, `setup2.xml` to recognise replace vs. add-on, spawn codes, manufacturer and DLC packs; repairs malformed XML |
| OpenIV packages | Reads `package.xml` / `assembly.xml`, installs what it safely can, and lists the remaining steps as explicit manual instructions |
| Conflict detection | Duplicate spawn codes, DLC packs, handling ids, textures, packfiles, a second `gameconfig.xml`, overwritten files with the owning mod named, and missing dependencies |
| Backup and restore | Snapshot per installation, undo, restore, delete, and pruning by generation count |
| Uninstall | Removes exactly the files the installation recorded, then the directories it created |
| CuongVision Ultimate | One depth-free cinematic ReShade profile with highlight protection, color-edge SMAA, AMD CAS clarity, and an optional verified 2K road download |
| Plugin system | Game-specific knowledge lives in a plugin; the core knows nothing about GTA V |

## Requirements

- Windows 10 or 11 (the detector and root-policy logic are Windows-specific)
- The packaged EXE includes Python; Python 3.11+ is only required for source development
- Optional: 7-Zip / WinRAR on `PATH` or configured in Settings, for `.rar` archives
- OpenIV.asi in the game root (required for mods-folder archive overrides)

## Windows download

Download `GtaVUltimateModManager.exe` from the latest GitHub Actions artifact
or tagged GitHub Release and run it directly. Python and `run.bat` are not
required for the packaged application.

Windows may show a SmartScreen warning until releases are code-signed. Verify
that the download came from this repository before choosing **Run anyway**.

## Running from source

```powershell
git clone <repository-url> gta-v-ultimate-mod-manager
cd gta-v-ultimate-mod-manager
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

For development, add the test and lint tooling:

```powershell
pip install -r requirements-dev.txt
```

## Running

```powershell
python -m gta_mod_manager.app
```

Build the standalone Windows EXE locally with:

```powershell
.\tools\build_windows.ps1
```

The result is written to `dist\GtaVUltimateModManager.exe`. Every push to
`main` also builds and tests this artifact through GitHub Actions; tags matching
`v*` publish it to GitHub Releases.

Useful switches:

| Flag | Effect |
| --- | --- |
| `--portable` | Keep logs, backups and settings next to the application instead of in `%LOCALAPPDATA%` |
| `--data-dir <path>` | Use an explicit working directory |
| `--debug` | Log at `DEBUG` level |
| `--keep-temp` | Do not delete leftover extraction workspaces on startup |

Application data lives in `%LOCALAPPDATA%\GtaVUltimateModManager` by default,
split into `logs/`, `temp/`, `backup/`, `cache/`, `config/` and `library/`.

## Using it

1. **Dashboard** - confirm the detected installation, its platform and which
   components are missing.
2. **Install** - drop an archive anywhere in the window. The preview lists every
   file operation, the classification and its confidence, the detected vehicles
   and DLC packs, the conflicts, and any manual steps. Nothing is written until
   you confirm.
3. **Installed Mods** - search, verify on-disk integrity, disable or uninstall.
4. **Conflict Center** - audit everything currently installed, not just the mod
   being added.
5. **Backup** - undo the last installation or restore any earlier snapshot.
6. **Log Viewer** - live, filterable view of the in-memory log ring buffer.
7. **Settings** - game folder, auto-backup, root-install confirmation, backup
   generations, 7-Zip path.

[docs/user-guide.md](docs/user-guide.md) covers the mod types, conflict
severities and troubleshooting in more detail.

## Project layout

```
gta_mod_manager/
  core/         constants, exceptions, Result, events, DI container, logging
  models/       frozen dataclasses for the domain (no I/O, no Qt)
  utils/        filesystem, hashing, glob patterns, XML repair, Windows APIs
  scanner/      temp workspaces, archive extractors, recursive inventory
  detector/     game detection sources, component catalog and detector
  analyzer/     rule engine, confidence scoring, dependency resolver
  plugins/      plugin contracts, registry, and the built-in gta_v plugin
  repository/   crash-safe JSON persistence
  backup/       snapshot store and backup engine
  installer/    transaction, operations, install engine, uninstaller, conflicts
  validator/    plan, game and XML validators
  services/     application use-cases exposed to the UI
  gui/          PySide6 shell: theme, widgets, view models, views, main window
  bootstrap.py  composition root - the only module that wires the graph
  app.py        entry point
```

Architecture notes are in [docs/architecture.md](docs/architecture.md); writing a
plugin for another game is covered in [docs/plugins.md](docs/plugins.md).

## Tests

```powershell
python -m pytest
```

The suite covers the core kernel, utilities, scanner, detectors, analyzer,
repositories, backup engine, transaction, plan validator, conflict rules, the
end-to-end install pipeline, and a GUI smoke test that builds the window and
visits every page on the offscreen Qt platform.

```powershell
python -m pytest --cov=gta_mod_manager        # coverage
python -m ruff check gta_mod_manager tests    # lint (clean)
python -m mypy gta_mod_manager                # type check (strict, clean)
python tools\launch_check.py                  # start the real GUI offscreen and quit
```

`tools/launch_check.py` is the release smoke check: it runs the actual entry
point against a throwaway data directory, builds the window on the offscreen Qt
platform and shuts down, so a startup or shutdown regression fails loudly
instead of only on a developer's desktop.

## License

The application source is available under the [MIT License](LICENSE).

Third-party shader notices are kept in
[`THIRD_PARTY_LICENSES.txt`](gta_mod_manager/resources/graphics/cuongvision/THIRD_PARTY_LICENSES.txt).
CuongVision downloads the optional road texture archive from its original
GTA5-Mods source and verifies its SHA-256 hash; that archive and Rockstar game
assets are not distributed in this repository.

This project is an independent community tool. It is not affiliated with,
endorsed by, or sponsored by Rockstar Games, Take-Two Interactive, ReShade,
Nexus Mods, or GTA5-Mods.com. Use game modifications in single-player only.
