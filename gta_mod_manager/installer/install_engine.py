"""The install engine: validate, apply, verify, roll back."""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.exceptions import InstallError, ValidationError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.progress import NullProgressReporter
from gta_mod_manager.core.protocols import ProgressReporter
from gta_mod_manager.installer.operations import OperationExecutor
from gta_mod_manager.installer.transaction import Transaction
from gta_mod_manager.models.enums import FileAction, ModKind, ModStatus
from gta_mod_manager.models.install_plan import FileOperation, InstallPlan
from gta_mod_manager.models.mod_package import (
    CachedArchiveMember,
    InstalledFileRecord,
    InstalledMod,
    ModPackage,
)
from gta_mod_manager.models.vehicle import VehicleDefinition
from gta_mod_manager.utils import fs
from gta_mod_manager.validator.plan_validator import PlanValidator

_LOGGER = get_logger("installer.engine")

SCRATCH_DIR_NAME = "install-scratch"
_RPF_MEMBER_CACHE = "rpf-members"


@dataclass(frozen=True, slots=True)
class InstallOutcome:
    """Result of applying a plan.

    Attributes:
        mod: The tracking record describing what was written.
        written_files: Files that ended up on disk.
        skipped: Operations that were not applicable.
    """

    mod: InstalledMod
    written_files: tuple[InstalledFileRecord, ...] = field(default_factory=tuple)
    skipped: int = 0


class InstallEngine:
    """Applies install plans transactionally.

    The engine deliberately knows nothing about *what* is being installed. It
    validates the plan, executes it step by step through a journal and rolls
    everything back on the first failure.
    """

    def __init__(
        self,
        paths: AppPaths,
        validator: PlanValidator | None = None,
        executor: OperationExecutor | None = None,
    ) -> None:
        self._paths = paths
        self._validator = validator or PlanValidator(allowed_external_roots=(paths.root,))
        self._executor = executor or OperationExecutor()

    def apply(
        self,
        plan: InstallPlan,
        package: ModPackage | None = None,
        reporter: ProgressReporter | None = None,
    ) -> InstallOutcome:
        """Execute ``plan`` and return what was installed.

        Args:
            plan: The validated plan to apply.
            package: Source package, used to enrich the tracking record.
            reporter: Optional progress sink.

        Raises:
            ValidationError: When the plan is unsafe; nothing is written.
            InstallError: When a step failed; the transaction was rolled back.
        """
        report = self._validator.validate(plan)
        if not report.is_valid:
            raise ValidationError(
                "The install plan was rejected before any file was touched",
                plan_id=plan.plan_id,
                issues=[issue.message for issue in report.fatal_issues],
            )

        reporter = reporter or NullProgressReporter()
        operation_id = plan.plan_id
        total = len(plan.operations)
        reporter.start(operation_id, f"Installing {plan.display_name}", total=total)

        scratch = self._paths.temp / SCRATCH_DIR_NAME / uuid.uuid4().hex[:10]
        written: list[InstalledFileRecord] = []
        skipped = 0

        with Transaction(scratch_dir=scratch) as transaction:
            for index, operation in enumerate(plan.operations, start=1):
                try:
                    record = self._executor.execute(operation, transaction)
                except InstallError:
                    _LOGGER.error(
                        "Install of %s failed at step %d/%d; rolling back",
                        plan.display_name,
                        index,
                        total,
                    )
                    raise
                if record is None:
                    skipped += 1
                else:
                    written.append(
                        self._with_cached_payloads(plan.package_id, operation, record)
                    )
                reporter.advance(operation_id, index)
            transaction.commit()

        reporter.finish(operation_id, f"Installed {plan.display_name}")
        written_tuple = self._dedupe_written(tuple(written))
        written_bytes = sum(
            item.target_path.stat().st_size
            for item in written_tuple
            if item.target_path.is_file()
        )
        _LOGGER.info(
            "Installed %s: %d file(s), %s",
            plan.display_name,
            len(written_tuple),
            fs.human_size(written_bytes),
        )

        return InstallOutcome(
            mod=self._build_record(plan, package, written_tuple),
            written_files=written_tuple,
            skipped=skipped,
        )

    @staticmethod
    def _dedupe_written(
        written: tuple[InstalledFileRecord, ...]
    ) -> tuple[InstalledFileRecord, ...]:
        """Keep one record per path, preferring shared-archive import details."""
        by_path: dict[str, InstalledFileRecord] = {}
        for record in written:
            key = str(fs.normalise(record.target_path)).lower()
            existing = by_path.get(key)
            if existing is None:
                by_path[key] = record
                continue
            if record.archive_members and not existing.archive_members:
                by_path[key] = record
            elif record.shared_archive and not existing.shared_archive:
                by_path[key] = InstalledFileRecord(
                    target_path=existing.target_path,
                    sha256=record.sha256 or existing.sha256,
                    replaced_existing=existing.replaced_existing or record.replaced_existing,
                    shared_archive=True,
                    archive_members=existing.archive_members or record.archive_members,
                    member_payloads=existing.member_payloads or record.member_payloads,
                )
            elif record.member_payloads and not existing.member_payloads:
                by_path[key] = InstalledFileRecord(
                    target_path=existing.target_path,
                    sha256=record.sha256 or existing.sha256,
                    replaced_existing=existing.replaced_existing or record.replaced_existing,
                    shared_archive=existing.shared_archive or record.shared_archive,
                    archive_members=existing.archive_members or record.archive_members,
                    member_payloads=record.member_payloads,
                )
        return tuple(by_path.values())

    def _with_cached_payloads(
        self,
        mod_id: str,
        operation: FileOperation,
        record: InstalledFileRecord,
    ) -> InstalledFileRecord:
        """Copy RPF member sources into the library cache for later re-enable."""
        if operation.action not in (FileAction.RPF_IMPORT, FileAction.RPF_PED_IMPORT):
            return record
        if not operation.archive_members:
            return record

        safe_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in mod_id) or "mod"
        root = self._paths.library / _RPF_MEMBER_CACHE / safe_id
        root.mkdir(parents=True, exist_ok=True)
        cached: list[CachedArchiveMember] = []
        for member in operation.archive_members:
            source = member.source_path
            if not source.is_file():
                continue
            safe_name = member.member_path.replace("\\", "/").replace("/", "__")
            destination = root / safe_name
            shutil.copy2(source, destination)
            cached.append(
                CachedArchiveMember(
                    member_path=member.member_path,
                    library_relative=f"{_RPF_MEMBER_CACHE}/{safe_id}/{safe_name}",
                )
            )
        if not cached:
            return record
        return InstalledFileRecord(
            target_path=record.target_path,
            sha256=record.sha256,
            replaced_existing=record.replaced_existing,
            shared_archive=record.shared_archive,
            archive_members=record.archive_members,
            member_payloads=tuple(cached),
        )

    @staticmethod
    def _build_record(
        plan: InstallPlan,
        package: ModPackage | None,
        written: tuple[InstalledFileRecord, ...],
    ) -> InstalledMod:
        """Build the library record describing the installation."""
        spawn_codes: tuple[str, ...] = ()
        dlc_packs: tuple[str, ...] = ()
        vehicle_definitions: tuple[VehicleDefinition, ...] = ()
        preview: Path | None = None
        source: Path | None = None
        kind = "unknown"

        if package is not None:
            kind = package.classification.primary.value
            preview = package.preview_image
            source = package.source_path
            if package.classification.primary is not ModKind.PED:
                spawn_codes = package.vehicles.spawn_codes
                dlc_packs = tuple(pack.pack_name for pack in package.vehicles.dlc_packs)
                vehicle_definitions = package.vehicles.vehicles

        return InstalledMod(
            mod_id=plan.package_id,
            display_name=plan.display_name,
            game_root=plan.game_root,
            kind=kind,
            status=ModStatus.INSTALLED,
            installed_files=written,
            created_directories=plan.created_directories,
            source_archive=source,
            preview_image=preview,
            spawn_codes=spawn_codes,
            dlc_packs=dlc_packs,
            vehicle_definitions=vehicle_definitions,
            notes="\n".join(plan.notes),
        )
