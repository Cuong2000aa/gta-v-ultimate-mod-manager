"""Composition root: the single place where the object graph is wired.

Everything else in the application receives its dependencies through the
constructor. Only this module knows which concrete adapter implements which
port, which is what makes the rest of the code replaceable in tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from gta_mod_manager.analyzer.dependency_resolver import DependencyResolver
from gta_mod_manager.analyzer.engine import ModAnalyzer
from gta_mod_manager.backup.backup_engine import BackupEngine
from gta_mod_manager.backup.snapshot_store import SnapshotStore
from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.container import Container
from gta_mod_manager.core.events import EventBus
from gta_mod_manager.core.logging_setup import LoggingHandles, configure_logging
from gta_mod_manager.core.progress import EventBusProgressReporter
from gta_mod_manager.detector.component_detector import ComponentDetector
from gta_mod_manager.detector.game_detector import GameDetector
from gta_mod_manager.installer.conflict_detector import ConflictDetector
from gta_mod_manager.installer.install_engine import InstallEngine
from gta_mod_manager.installer.uninstaller import Uninstaller
from gta_mod_manager.plugins.contracts import GamePlugin
from gta_mod_manager.plugins.gta_v.plugin import GtaVPlugin
from gta_mod_manager.plugins.gta_v.root_policy import RootInstallPolicy
from gta_mod_manager.plugins.registry import PluginRegistry, discover_plugins
from gta_mod_manager.repository.backup_repository import JsonBackupRepository
from gta_mod_manager.repository.mod_repository import JsonModRepository
from gta_mod_manager.repository.sqlite_mod_repository import SqliteModRepository
from gta_mod_manager.repository.settings_repository import JsonSettingsRepository
from gta_mod_manager.scanner.extractors import (
    ExtractorRegistry,
    RarExtractor,
    SevenZipExtractor,
    ZipExtractor,
)
from gta_mod_manager.scanner.package_scanner import PackageScanner
from gta_mod_manager.scanner.workspace import purge_stale_workspaces
from gta_mod_manager.services.analysis_service import AnalysisService
from gta_mod_manager.services.backup_service import BackupService
from gta_mod_manager.services.conflict_service import ConflictService
from gta_mod_manager.services.crash_monitor_service import CrashMonitorService
from gta_mod_manager.services.data_directory_service import DataDirectoryService
from gta_mod_manager.services.diagnostics_service import DiagnosticsService
from gta_mod_manager.services.game_service import GameService
from gta_mod_manager.services.install_service import InstallService
from gta_mod_manager.services.launch_service import LaunchService
from gta_mod_manager.services.library_service import LibraryService
from gta_mod_manager.services.graphics_service import GraphicsService
from gta_mod_manager.services.online_mod_service import OnlineModService
from gta_mod_manager.services.spawn_catalog_service import SpawnCatalogService
from gta_mod_manager.services.zombie_mode_service import ZombieModeService
from gta_mod_manager.diagnostics.scanner import DiagnosticsScanner
from gta_mod_manager.validator.game_validator import GameValidator
from gta_mod_manager.validator.plan_validator import PlanValidator
from gta_mod_manager.validator.xml_validator import XmlValidator


@dataclass(frozen=True, slots=True)
class Application:
    """The assembled application, ready to be driven by a UI or a script."""

    paths: AppPaths
    container: Container
    bus: EventBus
    logging: LoggingHandles

    @property
    def game(self) -> GameService:
        """Return the game service."""
        return self.container.resolve(GameService)

    @property
    def analysis(self) -> AnalysisService:
        """Return the analysis service."""
        return self.container.resolve(AnalysisService)

    @property
    def install(self) -> InstallService:
        """Return the install service."""
        return self.container.resolve(InstallService)

    @property
    def library(self) -> LibraryService:
        """Return the library service."""
        return self.container.resolve(LibraryService)

    @property
    def backups(self) -> BackupService:
        """Return the backup service."""
        return self.container.resolve(BackupService)

    @property
    def conflicts(self) -> ConflictService:
        """Return the conflict service."""
        return self.container.resolve(ConflictService)

    @property
    def diagnostics(self) -> DiagnosticsService:
        """Return the game diagnostics service."""
        return self.container.resolve(DiagnosticsService)

    @property
    def crash_monitor(self) -> CrashMonitorService:
        """Return the game crash monitor."""
        return self.container.resolve(CrashMonitorService)

    @property
    def launch(self) -> LaunchService:
        """Return the launch / preflight service."""
        return self.container.resolve(LaunchService)

    @property
    def spawn_catalog(self) -> SpawnCatalogService:
        """Return the spawn-code catalog service."""
        return self.container.resolve(SpawnCatalogService)

    @property
    def online(self) -> OnlineModService:
        """Return the online catalogue / download service."""
        return self.container.resolve(OnlineModService)

    @property
    def graphics(self) -> GraphicsService:
        """Return the CuongVision graphics pack service."""
        return self.container.resolve(GraphicsService)

    @property
    def zombie(self) -> ZombieModeService:
        """Return the managed zombie game-mode service."""
        return self.container.resolve(ZombieModeService)

    @property
    def plugins(self) -> PluginRegistry:
        """Return the plugin registry."""
        return self.container.resolve(PluginRegistry)


def build_application(
    paths: AppPaths | None = None,
    *,
    log_level: int = logging.INFO,
    console_logging: bool = True,
    purge_temp: bool = True,
) -> Application:
    """Wire every component and return the assembled application.

    Args:
        paths: Working directory layout; defaults to the per-user layout.
        log_level: Minimum level captured by the root logger.
        console_logging: Whether log records also go to standard error.
        purge_temp: Delete leftover extraction workspaces on startup.
    """
    resolved_paths = (paths or AppPaths.default()).ensure()
    bus = EventBus()
    handles = configure_logging(
        resolved_paths, bus=bus, level=log_level, console=console_logging
    )
    if purge_temp:
        purge_stale_workspaces(resolved_paths)

    container = Container()
    _register_infrastructure(container, resolved_paths, bus)
    _register_domain_services(container, resolved_paths, bus)

    return Application(
        paths=resolved_paths, container=container, bus=bus, logging=handles
    )


def _register_infrastructure(container: Container, paths: AppPaths, bus: EventBus) -> None:
    """Bind cross-cutting infrastructure and persistence adapters."""
    container.register_instance(AppPaths, paths)
    container.register_instance(EventBus, bus)
    container.register_instance(EventBusProgressReporter, EventBusProgressReporter(bus))

    container.register_factory(
        JsonSettingsRepository, lambda _: JsonSettingsRepository.at(paths.settings_file)
    )
    container.register_factory(
        SqliteModRepository,
        lambda _: SqliteModRepository.at(
            paths.mods_db_file, legacy_json_path=paths.legacy_mods_db_file
        ),
    )
    container.register_factory(
        JsonBackupRepository, lambda _: JsonBackupRepository.at(paths.backup_db_file)
    )

    container.register_factory(PluginRegistry, lambda _: _load_plugins())
    container.register_factory(
        GamePlugin, lambda c: c.resolve(PluginRegistry).all()[0]
    )

    container.register_factory(
        ExtractorRegistry, lambda c: _build_extractors(c.resolve(JsonSettingsRepository))
    )
    container.register_factory(
        PackageScanner, lambda c: PackageScanner(c.resolve(ExtractorRegistry))
    )
    container.register_factory(
        GameDetector, lambda c: GameDetector(c.resolve(GamePlugin).detection_sources())
    )
    container.register_factory(
        ComponentDetector,
        lambda c: ComponentDetector(c.resolve(GamePlugin).component_catalog()),
    )
    container.register_factory(
        ModAnalyzer, lambda c: ModAnalyzer(c.resolve(GamePlugin).analyzer_rules())
    )
    container.register_factory(DependencyResolver, lambda _: DependencyResolver())
    container.register_factory(XmlValidator, lambda _: XmlValidator())
    container.register_factory(GameValidator, lambda _: GameValidator())
    container.register_factory(
        PlanValidator,
        lambda c: PlanValidator(
            policy=_root_policy(c.resolve(GamePlugin)), allowed_external_roots=(paths.root,)
        ),
    )
    container.register_factory(SnapshotStore, lambda _: SnapshotStore(paths))
    container.register_factory(
        BackupEngine,
        lambda c: BackupEngine(
            store=c.resolve(SnapshotStore),
            repository=c.resolve(JsonBackupRepository),
            max_generations=c.resolve(JsonSettingsRepository).load().max_backup_generations,
        ),
    )
    container.register_factory(
        InstallEngine, lambda c: InstallEngine(paths, c.resolve(PlanValidator))
    )
    container.register_factory(Uninstaller, lambda _: Uninstaller())
    container.register_factory(ConflictDetector, lambda _: ConflictDetector())


def _register_domain_services(container: Container, paths: AppPaths, bus: EventBus) -> None:
    """Bind the application services."""
    container.register_factory(DataDirectoryService, lambda _: DataDirectoryService(paths))
    container.register_factory(
        GameService,
        lambda c: GameService(
            detector=c.resolve(GameDetector),
            components=c.resolve(ComponentDetector),
            validator=c.resolve(GameValidator),
            settings=c.resolve(JsonSettingsRepository),
            bus=bus,
        ),
    )
    container.register_factory(
        AnalysisService,
        lambda c: AnalysisService(
            scanner=c.resolve(PackageScanner),
            analyzer=c.resolve(ModAnalyzer),
            resolver=c.resolve(DependencyResolver),
            xml_validator=c.resolve(XmlValidator),
            paths=paths,
            settings=c.resolve(JsonSettingsRepository),
        ),
    )
    container.register_factory(
        BackupService,
        lambda c: BackupService(
            engine=c.resolve(BackupEngine),
            repository=c.resolve(JsonBackupRepository),
            bus=bus,
        ),
    )
    container.register_factory(
        InstallService,
        lambda c: InstallService(
            plugin=c.resolve(GamePlugin),
            engine=c.resolve(InstallEngine),
            conflicts=c.resolve(ConflictDetector),
            validator=c.resolve(PlanValidator),
            backups=c.resolve(BackupService),
            mods=c.resolve(SqliteModRepository),
            backup_repository=c.resolve(JsonBackupRepository),
            settings=c.resolve(JsonSettingsRepository),
            paths=paths,
            bus=bus,
        ),
    )
    container.register_factory(
        LibraryService,
        lambda c: LibraryService(
            mods=c.resolve(SqliteModRepository),
            uninstaller=c.resolve(Uninstaller),
            backups=c.resolve(BackupService),
            backup_repository=c.resolve(JsonBackupRepository),
            bus=bus,
        ),
    )
    container.register_factory(
        ConflictService, lambda c: ConflictService(mods=c.resolve(SqliteModRepository))
    )
    container.register_factory(
        CrashMonitorService,
        lambda c: CrashMonitorService(
            game=c.resolve(GameService),
            mods=c.resolve(SqliteModRepository),
            bus=bus,
            reports_dir=paths.logs / "sessions",
        ),
    )
    container.register_factory(
        DiagnosticsService,
        lambda c: DiagnosticsService(
            game=c.resolve(GameService),
            scanner=DiagnosticsScanner(),
            mods=c.resolve(SqliteModRepository),
            session_findings=_session_findings_provider(c),
        ),
    )
    container.register_factory(
        LaunchService,
        lambda c: LaunchService(
            game=c.resolve(GameService),
            diagnostics=c.resolve(DiagnosticsService),
            conflicts=c.resolve(ConflictService),
            crash_monitor=c.resolve(CrashMonitorService),
        ),
    )
    container.register_factory(
        SpawnCatalogService,
        lambda c: SpawnCatalogService(library=c.resolve(LibraryService)),
    )
    container.register_factory(
        OnlineModService,
        lambda c: OnlineModService(
            paths=paths,
            settings=c.resolve(JsonSettingsRepository),
            progress=c.resolve(EventBusProgressReporter),
        ),
    )
    container.register_factory(
        GraphicsService,
        lambda c: GraphicsService(game=c.resolve(GameService), paths=paths),
    )
    container.register_factory(
        ZombieModeService,
        lambda c: ZombieModeService(game=c.resolve(GameService), paths=paths),
    )


def _session_findings_provider(container: Container):
    """Return a callable exposing the crash monitor's latest findings."""

    def provide():
        monitor = container.resolve(CrashMonitorService)
        report = monitor.last_report
        return report.findings if report is not None else ()

    return provide


def _load_plugins() -> PluginRegistry:
    """Discover plugins, always guaranteeing the built-in GTA V plugin."""
    registry = discover_plugins()
    if not registry:
        registry.register(GtaVPlugin())
    return registry


def _root_policy(plugin: GamePlugin) -> RootInstallPolicy:
    """Return the plugin's root policy, falling back to the GTA V default."""
    policy = getattr(plugin, "root_policy", None)
    if isinstance(policy, RootInstallPolicy):
        return policy
    return RootInstallPolicy()


def _build_extractors(settings: JsonSettingsRepository) -> ExtractorRegistry:
    """Build the extractor registry, honouring the configured archiver paths."""
    current = settings.load()
    return ExtractorRegistry(
        (
            ZipExtractor(),
            SevenZipExtractor(),
            RarExtractor(current.seven_zip_path, current.unrar_path),
        )
    )
