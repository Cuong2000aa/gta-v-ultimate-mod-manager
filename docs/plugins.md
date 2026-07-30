# Writing a game plugin

The core contains no GTA V knowledge. It asks the active plugin where mods go,
which components matter, which analyzer rules to run and how to turn a package
into an install plan. Supporting another game means writing one plugin.

## Discovery

`discover_plugins()` walks the subpackages of `gta_mod_manager.plugins` and calls
the module-level `create_plugin()` factory found in the subpackage's `__init__`
or in its `plugin` submodule. The factory must return a `GamePlugin`; anything
else raises `PluginLoadError` with the offending module named.

```
gta_mod_manager/plugins/
  rdr2/
    __init__.py      -> from .plugin import create_plugin
    plugin.py        -> def create_plugin() -> GamePlugin
    root_policy.py
    path_mapper.py
    plan_builder.py
```

The registry keys plugins by `metadata.game_id`, so registering a second plugin
with the same id replaces the first - which is how you would override the
built-in GTA V behaviour without editing it.

## The contract

```python
class GamePlugin(ABC):
    @property
    def metadata(self) -> PluginMetadata: ...
    def detection_sources(self) -> tuple[DetectionSource, ...]: ...
    def component_catalog(self) -> tuple[ComponentProbe, ...]: ...
    def analyzer_rules(self) -> tuple[AnalyzerRule, ...]: ...
    def mods_root(self, install: GameInstall) -> Path: ...
    def decide_target(self, package: ModPackage, relative_path: Path) -> TargetDecision: ...
    def build_install_plan(self, request: PlanRequest) -> InstallPlan: ...
    def parse_vehicles(self, package: ModPackage) -> VehicleManifest: ...  # optional
```

### `detection_sources`

Each source subclasses `DetectionSource` and yields candidate root folders. Keep
them independent and cheap; `GameDetector` merges and validates the results, so a
source may return false positives. Registry access goes through
`utils.windows`, which is a no-op off Windows.

### `component_catalog`

A `ComponentProbe` names a component, the file or folder that proves it is
installed, whether it is essential, and optionally how to read its version.
Missing essential components are surfaced on the Dashboard and become dependency
warnings on a plan.

### `analyzer_rules`

Subclass `AnalyzerRule` and return `RuleHit`s:

```python
class MyVehicleRule(AnalyzerRule):
    rule_id = "rdr2.vehicle"
    display_name = "Wagon detection"

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        if not context.has_file("wagons.meta"):
            return ()
        return (RuleHit(kind=ModKind.VEHICLE_ADDON, weight=0.9,
                        reason="wagons.meta present"),)
```

A rule is a pure function of the context, so it can be unit-tested with a
synthetic inventory. Weights live in `[-1, 1]`; a negative weight vetoes a
category. Structural evidence (a file that must exist) deserves a high weight;
naming evidence deserves `KeywordRule`'s small weights, which only reinforce a
structural verdict rather than deciding on their own.

### `decide_target`

Return a `TargetDecision` for one packaged file: the zone it belongs to, the path
relative to that zone, and a `reason` shown in the preview. Return
`TargetDecision(target=None, reason=...)` to refuse a file, or set
`needs_archive_editor=True` when the content belongs inside a container archive -
the plan builder turns those into `ManualStep`s instead of silent skips.

### `build_install_plan`

Turn a `PlanRequest` into an `InstallPlan`: a tuple of `FileOperation`s, the
`ManualStep`s the user must perform, and any `dependency_warnings`. Honour
`request.allow_root_install` and `request.overwrite_existing`, and stage payloads
under `request.paths.temp` rather than anywhere else - `PlanValidator` only
accepts external targets inside the application data folder.

Never assume your plan will be executed as written. `PlanValidator` re-checks
every operation, so an unsafe plan is refused with a specific issue code rather
than silently corrupting an installation.

## Safety obligations

A plugin for a game with archive containers should provide its own policy object
exposed as a `root_policy` attribute; `bootstrap._root_policy` picks it up and
hands it to the validator. At minimum, decide:

- which files are original game content and therefore never writable,
- which container extension must never be written into,
- the small whitelist of files and folders allowed outside the mods folder.

## Testing a plugin

Mirror the package layout under `tests/plugins/<game>/`. The existing fixtures in
`tests/conftest.py` show the pattern: build a fake installation with `tmp_path`,
build sample archives with `zipfile`, and assert on the plan rather than on the
filesystem wherever possible. Then add one end-to-end test that installs into the
fake installation and asserts the original archives are untouched.
