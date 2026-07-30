# Architecture

The project follows Clean Architecture with MVVM in the presentation layer.
Dependencies point inwards only: the GUI depends on services, services depend on
domain models and ports, and the domain depends on nothing.

```
     PySide6 views  ->  view models  ->  services  ->  domain models
                                            |
                                            v
                             infrastructure (scanner, detector,
                             repository, backup, installer)
```

`bootstrap.py` is the only module that knows which concrete class implements
which port. Everything else receives its collaborators through the constructor,
which is what makes the layers independently testable.

## Layers

### `core` - the kernel

No domain knowledge, no I/O policy, just the machinery every layer uses.

- `constants.py` - every literal in the application. No other module hardcodes a
  file name, folder name, registry key or extension list.
- `exceptions.py` - the exception hierarchy rooted at `ModManagerError`.
- `result.py` - `Result[T]`, used by services for *expected* failures. Unexpected
  failures stay exceptions.
- `events.py` - a thread-safe `EventBus` plus the `AppEvent` types. The GUI never
  reaches into services to learn that something changed; it subscribes.
- `container.py` - a small explicit DI container (`register_instance`,
  `register_factory`, `resolve`). Factories are memoised.
- `app_paths.py` - the working-directory layout, injected everywhere so tests can
  redirect all I/O into `tmp_path`.
- `logging_setup.py` - rotating file log, optional console log, a ring buffer for
  the Log Viewer, and a handler that mirrors records onto the event bus.
- `progress.py`, `protocols.py` - progress reporting and the port definitions.

### `models` - the domain

Frozen dataclasses, no I/O, no Qt imports. `GameInstall`, `ModFile`,
`FileInventory`, `ModClassification`, `VehicleManifest`, `ModPackage`,
`InstalledMod`, `InstallPlan`, `FileOperation`, `ManualStep`, `Conflict`,
`ConflictReport`, `BackupSnapshot`, `OperationRecord`, `AppSettings` and the
enums they use. Derived facts are properties (`GameInstall.dlc_packs_path`,
`VehicleManifest.spawn_codes`, `ConflictReport.has_blocking`), so the same
question is never answered twice in two places.

### `utils` - stateless helpers

`fs` (safe joins, atomic writes, tree operations), `hashing`, `patterns`
(glob matching for the whitelist), `xml_tools` (tolerant parsing plus repair of
BOMs, control characters, stray ampersands and unclosed tags), `windows`
(registry and file-version wrappers, all no-ops off Windows).

### `scanner` - getting content onto disk

`TempWorkspace` owns a disposable folder under `temp/`. `ExtractorRegistry`
picks an extractor by suffix (`zip`, `7z`, `rar`, `oiv`). `InventoryBuilder`
walks the result into a `FileInventory` with sizes and hashes. `PackageScanner`
orchestrates the two and flattens a pointless single wrapper folder - but never
flattens a structural folder (`scripts`, `mods`, `update`, `x64`, `dlcpacks`,
`common`, `data`) or a DLC pack root marked by `setup2.xml`/`content.xml`.

### `detector` - finding the game and its components

`GameDetector` merges candidates from independent `DetectionSource`
implementations (registry, Steam library manifests, Epic manifests, common
folders), keeping the most authoritative platform for duplicates and validating
each candidate against `GAME_SIGNATURE_ENTRIES`. `ComponentDetector` runs the
`ComponentProbe` catalog to report which components are installed, their
versions, and which essential ones are missing.

### `analyzer` - deciding what a mod is

`ModAnalyzer` runs every `AnalyzerRule` against an `AnalysisContext`. A rule
returns `Evidence` with a weight and an explanation; `scoring.py` turns the
evidence into per-kind scores and a confidence level. The result is a
`ModClassification` that carries *why* it decided, which the preview shows.
`DependencyResolver` maps the classification onto required components.

### `plugins` - game-specific knowledge

`GamePlugin` is the contract: detection sources, component catalog, analyzer
rules, mods root, `decide_target` for one file, and `build_install_plan`. The
GTA V plugin implements it with `RootInstallPolicy` (the whitelist),
`layout.py` (recognising common archive shapes), `path_mapper.py`,
`vehicle_meta.py` (vehicle/handling/DLC parsing and XML repair),
`oiv_package.py` (OpenIV `package.xml`) and `plan_builder.py`.

### `repository` - persistence

`JsonStore` writes to a temporary file and replaces atomically, so a crash mid-
write cannot corrupt the database. `codecs.py` converts domain models to and from
plain JSON. Three repositories sit on top: installed mods, backups, settings.

### `backup` - reversibility

`SnapshotStore` copies files into `backup/<snapshot>/` and refuses to snapshot
directories. `BackupEngine` creates, restores, deletes and prunes snapshots by
generation count.

### `installer` - doing the work

`Transaction` journals every completed step and replays it backwards on failure.
`OperationExecutor` performs one `FileOperation`. `InstallEngine` validates,
executes and commits or rolls back. `Uninstaller` removes recorded files then
created directories. `ConflictDetector` runs the `ConflictRule` set; a crashing
rule is logged and skipped so it cannot hide the others.

### `validator` - the last gate

`PlanValidator` re-checks a finished plan against the safety rules
(see [safety.md](safety.md)). `GameValidator` inspects an installation more
deeply. `XmlValidator` checks and repairs XML documents.

### `services` - use-cases

The only API the GUI calls. Each method returns a `Result`, publishes events, and
performs no Qt work: `GameService`, `AnalysisService`, `InstallService`,
`BackupService`, `LibraryService`, `ConflictService`.

### `gui` - presentation

`TaskRunner` runs service calls on a `QThreadPool` so the window never blocks.
`EventRelay` turns bus events into Qt signals on the GUI thread. One view model
per page exposes signals and slots; views only build widgets and bind to them.
The dark theme lives in `theme/dark.qss` with tokens in `theme/palette.py`.

## The install pipeline

```
archive
  -> AnalysisService.analyze          extract, inventory, classify, repair XML
  -> InstallService.preview           plugin builds the plan
                                      conflicts detected (non-fatal here)
                                      plan validated (conflicts excluded)
  -> user confirms in the preview
  -> InstallService.apply             plan validated again (conflicts fatal)
                                      BackupService snapshots replaced files
                                      Transaction executes each operation
                                      commit, or roll back on the first error
                                      InstalledMod recorded in the repository
```

`preview` deliberately validates with `include_conflicts=False`: a conflict is
information the user must see and resolve, not a reason to refuse building the
plan. `apply` keeps the default, so a conflicting plan can never run by accident.

## Conventions

- Type hints everywhere; `mypy --strict` is the target.
- `pathlib` only, never `os.path`.
- Docstrings on every public class and method, in Google style.
- No literal file or folder names outside `core/constants.py`.
- Frozen dataclasses for domain state; mutation returns a copy.
- One responsibility per module; no giant files.
- Tests mirror the package layout under `tests/`.
