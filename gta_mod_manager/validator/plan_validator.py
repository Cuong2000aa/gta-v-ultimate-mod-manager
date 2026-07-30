"""Validates an install plan against the absolute safety rule.

This validator is the last gate before anything is written. Even if a plugin
or a future contributor builds a plan that would touch a protected file, the
installer refuses to run it.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.enums import FileAction, InstallTarget
from gta_mod_manager.models.game_install import ValidationIssue, ValidationReport
from gta_mod_manager.models.install_plan import FileOperation, InstallPlan
from gta_mod_manager.plugins.gta_v.root_policy import RootInstallPolicy
from gta_mod_manager.utils import fs

_LOGGER = get_logger("validator.plan")


class PlanValidator:
    """Checks that every operation of a plan is safe to execute."""

    def __init__(
        self,
        policy: RootInstallPolicy | None = None,
        allowed_external_roots: tuple[Path, ...] = (),
    ) -> None:
        self._policy = policy or RootInstallPolicy()
        self._allowed_external_roots = allowed_external_roots

    def validate(
        self, plan: InstallPlan, *, include_conflicts: bool = True
    ) -> ValidationReport:
        """Return every problem found in ``plan``.

        Args:
            plan: The plan to inspect.
            include_conflicts: Treat blocking conflicts as fatal issues. The
                preview step passes ``False``, because a conflict is
                information the user must see and resolve, not a reason to
                refuse building the plan. The installer keeps the default so a
                conflicting plan can never be applied by accident.
        """
        issues: list[ValidationIssue] = []

        if plan.is_empty and not plan.manual_steps:
            issues.append(
                ValidationIssue(
                    code="plan.empty",
                    message="The plan contains no operations; nothing would be installed",
                    is_fatal=True,
                )
            )

        game_root = fs.normalise(plan.game_root)
        mods_root = game_root / constants.MODS_FOLDER_NAME

        for operation in plan.operations:
            issues.extend(self._validate_operation(operation, game_root, mods_root))

        if include_conflicts and plan.conflicts.has_blocking:
            for conflict in plan.conflicts.blocking:
                issues.append(
                    ValidationIssue(
                        code="plan.blocking_conflict",
                        message=f"{conflict.conflict_type.display_name}: {conflict.description}",
                        is_fatal=True,
                    )
                )

        report = ValidationReport(issues=tuple(issues))
        if not report.is_valid:
            _LOGGER.error(
                "Plan %s rejected: %s",
                plan.plan_id,
                "; ".join(issue.message for issue in report.fatal_issues),
            )
        return report

    def _validate_operation(
        self, operation: FileOperation, game_root: Path, mods_root: Path
    ) -> tuple[ValidationIssue, ...]:
        """Check one operation."""
        issues: list[ValidationIssue] = []
        target = fs.normalise(operation.target_path)

        if operation.target_kind is InstallTarget.EXTERNAL:
            if not self._is_allowed_external(target):
                issues.append(
                    ValidationIssue(
                        code="plan.external_target",
                        message="Operation writes outside both the game and the "
                        "application data folder",
                        is_fatal=True,
                        path=target,
                    )
                )
            return tuple(issues)

        if not fs.is_relative_to(target, game_root):
            issues.append(
                ValidationIssue(
                    code="plan.outside_game",
                    message="Operation would write outside the game installation",
                    is_fatal=True,
                    path=target,
                )
            )
            return tuple(issues)

        relative = PurePosixPath(
            str(target)[len(str(game_root)) :].lstrip("\\/").replace("\\", "/")
        )

        if self._policy.is_protected(relative):
            issues.append(
                ValidationIssue(
                    code="plan.protected_target",
                    message=f"{relative} is an original game file and must never be modified",
                    is_fatal=True,
                    path=target,
                )
            )

        if self._writes_into_archive(relative):
            issues.append(
                ValidationIssue(
                    code="plan.inside_archive",
                    message=f"{relative} points inside an .rpf archive, which cannot be edited",
                    is_fatal=True,
                    path=target,
                )
            )

        outside_mods = not fs.is_relative_to(target, mods_root)
        if outside_mods and operation.target_kind is InstallTarget.MODS_FOLDER:
            issues.append(
                ValidationIssue(
                    code="plan.zone_mismatch",
                    message="Operation is declared as a mods-folder install but targets "
                    "the game root",
                    is_fatal=True,
                    path=target,
                )
            )

        if outside_mods and operation.action is not FileAction.CREATE_DIRECTORY:
            verdict = self._policy.evaluate(relative)
            if not verdict.allowed:
                issues.append(
                    ValidationIssue(
                        code="plan.root_not_whitelisted",
                        message=f"{relative} is not on the root install whitelist: "
                        f"{verdict.reason}",
                        is_fatal=True,
                        path=target,
                    )
                )

        reads_a_source = operation.action in (
            FileAction.COPY,
            FileAction.OVERWRITE,
            FileAction.RPF_COPY,
        )
        if reads_a_source and (
            operation.source_path is None or not operation.source_path.is_file()
        ):
            issues.append(
                ValidationIssue(
                    code="plan.missing_source",
                    message="The source file of this operation no longer exists",
                    is_fatal=True,
                    path=operation.source_path or target,
                )
            )

        issues.extend(self._validate_rpf_operation(operation, game_root, mods_root, target))

        return tuple(issues)

    def _validate_rpf_operation(
        self,
        operation: FileOperation,
        game_root: Path,
        mods_root: Path,
        target: Path,
    ) -> tuple[ValidationIssue, ...]:
        """Apply RPF_COPY / RPF_IMPORT specific safety rules."""
        issues: list[ValidationIssue] = []

        if operation.action is FileAction.RPF_COPY:
            source = operation.source_path
            if source is None:
                return tuple(issues)
            source_norm = fs.normalise(source)
            if not fs.is_relative_to(source_norm, game_root):
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_copy_source",
                        message="RPF copy source must be an original archive under the game root",
                        is_fatal=True,
                        path=source,
                    )
                )
            elif fs.is_relative_to(source_norm, mods_root):
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_copy_source",
                        message="RPF copy source must not already be inside the mods folder",
                        is_fatal=True,
                        path=source,
                    )
                )
            if not fs.is_relative_to(target, mods_root):
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_copy_target",
                        message="RPF copies may only be written inside the mods folder",
                        is_fatal=True,
                        path=target,
                    )
                )
            if target.suffix.lower() != constants.PROTECTED_ARCHIVE_SUFFIX:
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_copy_target",
                        message="RPF copy target must be a .rpf file",
                        is_fatal=True,
                        path=target,
                    )
                )

        if operation.action is FileAction.RPF_IMPORT:
            if not fs.is_relative_to(target, mods_root):
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_import_target",
                        message="RPF imports may only edit archives inside the mods folder",
                        is_fatal=True,
                        path=target,
                    )
                )
            if target.suffix.lower() != constants.PROTECTED_ARCHIVE_SUFFIX:
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_import_target",
                        message="RPF import target must be a .rpf file",
                        is_fatal=True,
                        path=target,
                    )
                )
            if not operation.archive_members:
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_import_empty",
                        message="RPF import has no members to write",
                        is_fatal=True,
                        path=target,
                    )
                )
            for member in operation.archive_members:
                if not member.source_path.is_file():
                    issues.append(
                        ValidationIssue(
                            code="plan.missing_source",
                            message="An RPF import source file no longer exists",
                            is_fatal=True,
                            path=member.source_path,
                        )
                    )
                if not member.member_path or member.member_path.startswith("/"):
                    issues.append(
                        ValidationIssue(
                            code="plan.rpf_member_path",
                            message="Archive member path is invalid",
                            is_fatal=True,
                            path=target,
                        )
                    )
            issues.extend(
                self._validate_rpf_import_restorable(operation, game_root, target)
            )

        if operation.action is FileAction.RPF_PED_IMPORT:
            if not fs.is_relative_to(target, mods_root):
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_ped_target",
                        message="Add-on ped imports may only write inside the mods folder",
                        is_fatal=True,
                        path=target,
                    )
                )
            if target.suffix.lower() != constants.PROTECTED_ARCHIVE_SUFFIX:
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_ped_target",
                        message="Add-on ped import target must be a .rpf file",
                        is_fatal=True,
                        path=target,
                    )
                )
            if not operation.archive_members:
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_ped_empty",
                        message="Add-on ped import has no members to write",
                        is_fatal=True,
                        path=target,
                    )
                )
            for member in operation.archive_members:
                if not member.source_path.is_file():
                    issues.append(
                        ValidationIssue(
                            code="plan.missing_source",
                            message="An add-on ped source file no longer exists",
                            is_fatal=True,
                            path=member.source_path,
                        )
                    )

        if operation.action is FileAction.RPF_DLC_REGISTER:
            if not fs.is_relative_to(target, mods_root):
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_dlc_target",
                        message="DLC registration may only edit archives inside the mods folder",
                        is_fatal=True,
                        path=target,
                    )
                )
            if target.suffix.lower() != constants.PROTECTED_ARCHIVE_SUFFIX:
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_dlc_target",
                        message="DLC registration target must be a .rpf file",
                        is_fatal=True,
                        path=target,
                    )
                )
            packs = [
                line.strip()
                for line in (operation.payload or "").splitlines()
                if line.strip()
            ]
            if not packs:
                issues.append(
                    ValidationIssue(
                        code="plan.rpf_dlc_empty",
                        message="DLC registration has no pack names",
                        is_fatal=True,
                        path=target,
                    )
                )

        return tuple(issues)

    def _validate_rpf_import_restorable(
        self,
        operation: FileOperation,
        game_root: Path,
        target: Path,
    ) -> tuple[ValidationIssue, ...]:
        """Warn when imported members are not in the mirrored stock archive.

        Not fatal: uninstall can delete those members so OpenIV falls through.
        """
        from gta_mod_manager.plugins.gta_v.rpf_archive import (
            resolve_stock_members,
            stock_archive_for_mods_copy,
        )

        try:
            stock = stock_archive_for_mods_copy(target, game_root)
        except Exception:  # noqa: BLE001
            return ()
        if not stock.is_file() or not operation.archive_members:
            return ()
        paths = tuple(member.member_path for member in operation.archive_members)
        mirrored = resolve_stock_members(
            stock, game_root, paths, mirrored_only=True
        )
        missing = [path for path in paths if path not in mirrored]
        if not missing:
            return ()
        names = ", ".join(sorted({Path(path).name for path in missing}))
        return (
            ValidationIssue(
                code="plan.rpf_import_not_in_mirrored_stock",
                message=(
                    f"{names} are not in stock {stock.name}. Uninstall will remove "
                    "them from the mods copy (OpenIV fallthrough) rather than "
                    "byte-restoring from x64e. Replace installs are never 100% safe."
                ),
                is_fatal=False,
                path=target,
            ),
        )

    def _is_allowed_external(self, target: Path) -> bool:
        """Return whether an external target is inside an allowed staging root."""
        return any(
            fs.is_relative_to(target, allowed) for allowed in self._allowed_external_roots
        )

    @staticmethod
    def _writes_into_archive(relative: PurePosixPath) -> bool:
        """Return whether the path descends *into* an ``.rpf`` archive."""
        parts = relative.parts
        return any(
            part.lower().endswith(constants.PROTECTED_ARCHIVE_SUFFIX)
            for part in parts[:-1]
        )
