# GTA V Ultimate Mod Manager

A safety-first Story Mode mod manager for *Grand Theft Auto V*, built on Python
and PySide6. It detects your installation, analyses an archive before touching
anything, shows exactly what will be written, and keeps a reversible snapshot of
every file it replaces.

The manager does **not** copy files blindly. Every archive goes through the same
pipeline: extract into a temporary workspace, build a file inventory, classify
the mod, resolve dependencies, map every file to a destination, validate the plan
against the safety rules, and only then write — inside a journalled transaction
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
| Essentials + Stability Kit | Creates `mods/`, auto-installs pinned ScriptHookVDotNet + NativeUI, and opens download pages for ScriptHookV, OpenIV.asi, Packfile Limit Adjuster, Heap Adjuster, and a build-matched gameconfig |
| Mod analysis | Extracts `zip`, `7z`, `rar` and `oiv`, walks the tree, and classifies the mod with a confidence score and the evidence behind it |
| Vehicle / weapon / map packs | Recognises replace vs add-on DLC, spawn codes, and common meta; registers add-on packs in `dlclist` when safe |
| Physical enable / disable | Quarantines loose files and reverts shared archive members; re-enable restores loose files and re-applies cached RPF payloads when available |
| Conflict Center | Audits duplicate spawn codes, DLC packs, shared files and gameconfigs; one-click disable for conflicting mods |
| Backup and restore | Snapshot per installation, undo, restore, delete, and pruning by generation count |
| Online Mods | Browse / search GTA5-Mods and Nexus (API key optional), then hand off to the same safe install pipeline |
| Spawn Center | Lists spawn codes from installed vehicle / ped mods for trainers |
| NCCVision Ultimate | Depth-free cinematic ReShade profile (lighter filmic grade + scene micro-detail, color-edge SMAA, AMD CAS), optional verified 2K roads, and in-app **Update ReShade** from reshade.me |
| Zombie Mode | Managed install of pinned Simple Zombies Reborn (SHA-256 verified) with dependency checks |
| Game Diagnostics | Crash / log / ASI / ENB leftover / orphan DLC / vehicle stream checks with one-click repairs where safe |
| Plugin system | Game-specific knowledge lives in a plugin; the core knows nothing about GTA V |

## Requirements

- Windows 10 or 11 (the detector and root-policy logic are Windows-specific)
- The packaged EXE includes Python; Python 3.11+ is only required for source development
- **7-Zip** on `PATH` or configured in Settings — needed for many `.rar` / `.7z` archives and for **Update ReShade**
- OpenIV.asi in the game root (required for mods-folder archive overrides)
- Story Mode / single-player only — never enter GTA Online with script mods loaded

## Windows download

Download `GtaVUltimateModManager.exe` from the latest [GitHub Release](https://github.com/Cuong2000aa/gta-v-ultimate-mod-manager/releases)
or GitHub Actions artifact and run it directly. Python and `run.bat` are not
required for the packaged application.

Windows may show a SmartScreen warning until releases are code-signed. Verify
that the download came from this repository before choosing **Run anyway**.

## Running from source

```powershell
git clone https://github.com/Cuong2000aa/gta-v-ultimate-mod-manager.git
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

1. **Dashboard** — confirm the detected install, run Essentials + Stability Kit, launch with preflight.
2. **Install a Mod** — drop an archive; preview operations, conflicts and manual OpenIV steps before confirming.
3. **Online Mods** — search GTA5-Mods / Nexus, download when possible, then install through the same pipeline.
4. **Installed Mods** — search, verify integrity, physically enable/disable, or uninstall.
5. **Spawn Center** — copy vehicle / ped spawn codes from installed mods.
6. **Graphics Mods** — install NCCVision Ultimate, optional 2K roads, or **Update ReShade** (needs 7-Zip).
7. **Conflict Center** — audit the whole library; disable conflicting mods in one click.
8. **Zombie Mode** — install / update / remove Simple Zombies Reborn (`F10` or controller `LB + B` for the menu).
9. **Backup & Restore** — undo the last install or restore an earlier snapshot.
10. **Game Diagnostics** — scan logs and the game folder; apply safe one-click repairs.
11. **Log Viewer** — live, filterable application log.
12. **Settings** — game folder, backups, language, Nexus API key, 7-Zip / UnRAR paths.

[docs/user-guide.md](docs/user-guide.md) covers mod types, conflict severities and troubleshooting in more detail.

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
  graphics/     NCCVision pack helpers and ReShade updater
  resources/    bundled graphics pack (NCCVision injector + shaders)
  gui/          PySide6 shell: theme, widgets, view models, views, main window
  bootstrap.py  composition root — the only module that wires the graph
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
end-to-end install pipeline, graphics / ReShade helpers, and a GUI smoke test
that builds the window and visits every page on the offscreen Qt platform.

```powershell
python -m pytest --cov=gta_mod_manager        # coverage
python -m ruff check gta_mod_manager tests    # lint
python -m mypy gta_mod_manager                # type check
python tools\launch_check.py                  # start the real GUI offscreen and quit
```

`tools/launch_check.py` is the release smoke check: it runs the actual entry
point against a throwaway data directory, builds the window on the offscreen Qt
platform and shuts down, so a startup or shutdown regression fails loudly
instead of only on a developer's desktop.

## License

The application source is available under the [MIT License](LICENSE).

Third-party shader notices are kept in
[`THIRD_PARTY_LICENSES.txt`](gta_mod_manager/resources/graphics/nccvision/THIRD_PARTY_LICENSES.txt).
NCCVision downloads the optional road texture archive from its original
GTA5-Mods source and verifies its SHA-256 hash; that archive and Rockstar game
assets are not distributed in this repository. **Update ReShade** fetches the
signed installer from [reshade.me](https://reshade.me/) and extracts the injector
locally (7-Zip required).

This project is an independent community tool. It is not affiliated with,
endorsed by, or sponsored by Rockstar Games, Take-Two Interactive, ReShade,
Nexus Mods, or GTA5-Mods.com. Use game modifications in single-player only.
