"""The core use-case: scan, analyse, preview, confirm, install, roll back.

The service enforces the pipeline described in the architecture. Nothing is
ever installed blindly: :meth:`InstallService.preview` produces a plan the user
must confirm, and :meth:`InstallService.install` refuses any plan it did not
validate itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.events import (
    EventBus,
    ModLibraryChangedEvent,
    NotificationEvent,
    NotificationLevel,
    new_operation_id,
)
from gta_mod_manager.core.exceptions import InstallError, ValidationError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.protocols import ProgressReporter
from gta_mod_manager.core.result import Result
from gta_mod_manager.installer.conflict_detector import ConflictDetector
from gta_mod_manager.installer.install_engine import InstallEngine
from gta_mod_manager.models.backup_snapshot import BackupSnapshot, OperationRecord
from gta_mod_manager.models.component import ComponentReport
from gta_mod_manager.models.enums import OperationKind, OperationStatus
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.install_plan import InstallPlan
from gta_mod_manager.models.mod_package import InstalledMod, ModPackage
from gta_mod_manager.models.variant_selection import VariantSelection
from gta_mod_manager.plugins.contracts import GamePlugin, PlanRequest
from gta_mod_manager.plugins.gta_v.layout import PackageLayout
from gta_mod_manager.repository.backup_repository import JsonBackupRepository
from gta_mod_manager.repository.mod_repository import JsonModRepository
from gta_mod_manager.repository.settings_repository import JsonSettingsRepository
from gta_mod_manager.services.backup_service import BackupService
from gta_mod_manager.validator.plan_validator import PlanValidator

_LOGGER = get_logger("services.install")


@dataclass(frozen=True, slots=True)
class InstallPreview:
    """A plan plus everything the confirmation dialog needs to show."""

    package: ModPackage
    plan: InstallPlan
    install: GameInstall
    variants: VariantSelection = field(default_factory=VariantSelection)
    has_addon_variant: bool = False
    has_replace_variant: bool = False

    @property
    def needs_variant_choice(self) -> bool:
        """Return whether the user must pick Add-On and/or Replace."""
        return self.has_addon_variant and self.has_replace_variant

    @property
    def is_installable(self) -> bool:
        """Return whether the plan may be applied as-is."""
        if self.needs_variant_choice and not self.variants.any_selected:
            return False
        return not self.plan.conflicts.has_blocking and not self.plan.is_empty

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        """Return why the plan cannot be applied, when it cannot."""
        if self.needs_variant_choice and not self.variants.any_selected:
            return ("Choose Add-On, Replace, or both before installing.",)
        if self.plan.is_empty:
            return ("The package contains nothing this manager can install.",)
        return tuple(
            f"{conflict.conflict_type.display_name}: {conflict.description}"
            for conflict in self.plan.conflicts.blocking
        )


@dataclass(frozen=True, slots=True)
class InstallReport:
    """Outcome of a completed installation."""

    mod: InstalledMod
    snapshot: BackupSnapshot | None
    file_count: int
    manual_steps: int

    @property
    def needs_user_action(self) -> bool:
        """Return whether the user still has manual OpenIV work to do."""
        return self.manual_steps > 0


class InstallService:
    """Orchestrates the full installation pipeline."""

    def __init__(
        self,
        plugin: GamePlugin,
        engine: InstallEngine,
        conflicts: ConflictDetector,
        validator: PlanValidator,
        backups: BackupService,
        mods: JsonModRepository,
        backup_repository: JsonBackupRepository,
        settings: JsonSettingsRepository,
        paths: AppPaths,
        bus: EventBus,
    ) -> None:
        self._plugin = plugin
        self._engine = engine
        self._conflicts = conflicts
        self._validator = validator
        self._backups = backups
        self._mods = mods
        self._backup_repository = backup_repository
        self._settings = settings
        self._paths = paths
        self._bus = bus

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    def preview(
        self,
        package: ModPackage,
        install: GameInstall,
        components: ComponentReport | None = None,
        variants: VariantSelection | None = None,
    ) -> Result[InstallPreview]:
        """Build the plan for ``package`` and evaluate it.

        No file is written. The returned preview tells the UI exactly what
        would happen, including conflicts and manual OpenIV steps.
        """
        settings = self._settings.load()
        layout = PackageLayout.detect(package.inventory, package.display_name)
        chosen = variants or VariantSelection.for_package(
            has_addon=layout.has_addon_variant,
            has_replace=layout.has_replace_variant,
        )
        enriched = replace(
            package, vehicles=self._plugin.parse_vehicles(package, variants=chosen)
        )

        request = PlanRequest(
            package=enriched,
            install=install,
            paths=self._paths,
            allow_root_install=True,
            overwrite_existing=True,
            variants=chosen,
        )
        plan = self._plugin.build_install_plan(request)
        plan = replace(plan, dependency_warnings=self._dependency_warnings(enriched, components))

        report = self._conflicts.detect(
            plan, install, self._mods.list_for_game(install.root_path), enriched
        )
        plan = plan.with_conflicts(report)

        validation = self._validator.validate(plan, include_conflicts=False)
        if not validation.is_valid:
            return Result.fail(
                "The generated plan is unsafe: "
                + "; ".join(issue.message for issue in validation.fatal_issues),
                code="install.unsafe_plan",
            )

        warnings = [issue.message for issue in validation.warnings]
        if not settings.auto_backup:
            warnings.append("Automatic backup is disabled in the settings")

        return Result(
            value=InstallPreview(
                package=enriched,
                plan=plan,
                install=install,
                variants=chosen,
                has_addon_variant=layout.has_addon_variant,
                has_replace_variant=layout.has_replace_variant,
            ),
            warnings=tuple(warnings),
        )

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------
    def install(
        self, preview: InstallPreview, reporter: ProgressReporter | None = None
    ) -> Result[InstallReport]:
        """Apply a previously confirmed ``preview``.

        The sequence is: audit record, backup, apply, register, notify. Any
        failure rolls the transaction back and restores the snapshot.
        """
        if not preview.is_installable:
            return Result.fail(
                "; ".join(preview.blocking_reasons), code="install.blocked"
            )

        plan = preview.plan
        operation_id = new_operation_id()
        record = OperationRecord(
            operation_id=operation_id,
            kind=OperationKind.INSTALL,
            status=OperationStatus.RUNNING,
            description=f"Install {plan.display_name}",
            mod_id=plan.package_id,
        )
        self._backup_repository.add_operation(record)

        snapshot: BackupSnapshot | None = None
        if self._settings.load().auto_backup:
            snapshot = self._backups.snapshot_for_plan(plan, operation_id, reporter)
            record = replace(record, snapshot_id=snapshot.snapshot_id if snapshot else None)

        try:
            outcome = self._engine.apply(plan, preview.package, reporter)
        except (InstallError, ValidationError) as error:
            self._recover(snapshot, record, error)
            return Result.fail(str(error), code="install.failed")

        installed = replace(
            outcome.mod,
            backup_id=snapshot.snapshot_id if snapshot else None,
        )
        self._mods.add(installed)
        self._backup_repository.add_operation(record.completed(OperationStatus.SUCCEEDED))
        self._bus.publish(ModLibraryChangedEvent(reason="installed"))
        self._notify_success(plan, len(outcome.written_files))

        return Result.ok(
            InstallReport(
                mod=installed,
                snapshot=snapshot,
                file_count=len(outcome.written_files),
                manual_steps=len(plan.manual_steps),
            )
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _recover(
        self,
        snapshot: BackupSnapshot | None,
        record: OperationRecord,
        error: Exception,
    ) -> None:
        """Restore the snapshot and record the failure."""
        _LOGGER.error("Installation failed: %s", error)
        status = OperationStatus.FAILED
        if snapshot is not None:
            try:
                self._backups.restore(snapshot)
                status = OperationStatus.ROLLED_BACK
            except Exception as restore_error:  # noqa: BLE001 - reported to the user
                _LOGGER.critical("Rollback failed as well: %s", restore_error)
        self._backup_repository.add_operation(record.completed(status, str(error)))
        self._bus.publish(
            NotificationEvent(
                title="Installation failed",
                message=str(error),
                level=NotificationLevel.ERROR,
            )
        )

    def _notify_success(self, plan: InstallPlan, file_count: int) -> None:
        """Publish the success toast."""
        message = f"{file_count} file(s) installed"
        if plan.manual_steps:
            message += f"; {len(plan.manual_steps)} manual OpenIV step(s) remain"
        self._bus.publish(
            NotificationEvent(
                title=f"{plan.display_name} installed",
                message=message,
                level=NotificationLevel.WARNING if plan.manual_steps else NotificationLevel.SUCCESS,
            )
        )

    @staticmethod
    def _dependency_warnings(
        package: ModPackage, components: ComponentReport | None
    ) -> tuple[str, ...]:
        """Return a warning for every required component that is missing."""
        if components is None:
            return ()
        return tuple(
            f"{dependency.display_name} is not installed - {dependency.reason}"
            for dependency in package.required_dependencies
            if not components.has(dependency.component_id)
        )
