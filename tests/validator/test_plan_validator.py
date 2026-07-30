"""Tests for the last safety gate before anything is written."""

from __future__ import annotations

from pathlib import Path

import pytest

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.models.conflict import Conflict, ConflictReport
from gta_mod_manager.models.enums import (
    ConflictSeverity,
    ConflictType,
    FileAction,
    InstallTarget,
)
from gta_mod_manager.models.install_plan import FileOperation, InstallPlan, ManualStep
from gta_mod_manager.validator.plan_validator import PlanValidator


@pytest.fixture()
def source_file(tmp_path: Path) -> Path:
    """Return an existing file usable as an operation source."""
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"payload")
    return payload


def _plan(game_root: Path, *operations: FileOperation, **kwargs: object) -> InstallPlan:
    """Return a plan carrying ``operations``."""
    return InstallPlan(
        plan_id="plan-1",
        package_id="pkg-1",
        display_name="Test Mod",
        game_root=game_root,
        operations=operations,
        **kwargs,  # type: ignore[arg-type]
    )


def _copy(target: Path, source: Path, kind: InstallTarget) -> FileOperation:
    """Return a copy operation."""
    return FileOperation(
        action=FileAction.COPY, target_path=target, source_path=source, target_kind=kind
    )


def test_a_mods_folder_install_is_accepted(game_root: Path, source_file: Path) -> None:
    plan = _plan(
        game_root,
        _copy(
            game_root / "mods" / "update" / "x64" / "dlcpacks" / "p" / "dlc.rpf",
            source_file,
            InstallTarget.DLC_PACKS,
        ),
    )

    assert PlanValidator().validate(plan).is_valid


def test_an_empty_plan_is_rejected(game_root: Path) -> None:
    report = PlanValidator().validate(_plan(game_root))

    assert not report.is_valid
    assert report.fatal_issues[0].code == "plan.empty"


def test_a_plan_with_only_manual_steps_is_accepted(game_root: Path) -> None:
    plan = _plan(
        game_root,
        manual_steps=(
            ManualStep(title="Register in dlclist.xml", instruction="Use OpenIV"),
        ),
    )

    assert PlanValidator().validate(plan).is_valid


@pytest.mark.parametrize("name", ["GTA5.exe", "common.rpf", "x64a.rpf"])
def test_protected_game_files_are_refused(
    game_root: Path, source_file: Path, name: str
) -> None:
    plan = _plan(game_root, _copy(game_root / name, source_file, InstallTarget.GAME_ROOT))

    report = PlanValidator().validate(plan)

    assert not report.is_valid
    assert any(issue.code == "plan.protected_target" for issue in report.fatal_issues)


def test_writing_inside_an_rpf_archive_is_refused(
    game_root: Path, source_file: Path
) -> None:
    target = game_root / "mods" / "update" / "update.rpf" / "common" / "data" / "handling.meta"
    plan = _plan(game_root, _copy(target, source_file, InstallTarget.MODS_FOLDER))

    report = PlanValidator().validate(plan)

    assert any(issue.code == "plan.inside_archive" for issue in report.fatal_issues)


def test_writing_outside_the_game_folder_is_refused(
    game_root: Path, source_file: Path, tmp_path: Path
) -> None:
    plan = _plan(
        game_root,
        _copy(tmp_path / "elsewhere" / "mod.dll", source_file, InstallTarget.GAME_ROOT),
    )

    report = PlanValidator().validate(plan)

    assert any(issue.code == "plan.outside_game" for issue in report.fatal_issues)


def test_a_non_whitelisted_root_file_is_refused(
    game_root: Path, source_file: Path
) -> None:
    plan = _plan(
        game_root, _copy(game_root / "vehicles.meta", source_file, InstallTarget.GAME_ROOT)
    )

    report = PlanValidator().validate(plan)

    assert any(issue.code == "plan.root_not_whitelisted" for issue in report.fatal_issues)


def test_a_zone_mismatch_is_refused(game_root: Path, source_file: Path) -> None:
    plan = _plan(
        game_root,
        _copy(game_root / "scripts" / "Cool.dll", source_file, InstallTarget.MODS_FOLDER),
    )

    report = PlanValidator().validate(plan)

    assert any(issue.code == "plan.zone_mismatch" for issue in report.fatal_issues)


def test_a_missing_source_is_refused(game_root: Path, tmp_path: Path) -> None:
    plan = _plan(
        game_root,
        _copy(game_root / "mods" / "a.rpf", tmp_path / "gone.bin", InstallTarget.MODS_FOLDER),
    )

    report = PlanValidator().validate(plan)

    assert any(issue.code == "plan.missing_source" for issue in report.fatal_issues)


def test_external_staging_is_only_allowed_inside_the_app_folder(
    app_paths: AppPaths, game_root: Path, source_file: Path, tmp_path: Path
) -> None:
    validator = PlanValidator(allowed_external_roots=(app_paths.root,))

    allowed = _plan(
        game_root,
        _copy(app_paths.temp / "staged" / "dlc.rpf", source_file, InstallTarget.EXTERNAL),
    )
    refused = _plan(
        game_root,
        _copy(tmp_path / "anywhere" / "dlc.rpf", source_file, InstallTarget.EXTERNAL),
    )

    assert validator.validate(allowed).is_valid
    assert any(
        issue.code == "plan.external_target"
        for issue in validator.validate(refused).fatal_issues
    )


def test_blocking_conflicts_only_fail_when_requested(
    game_root: Path, source_file: Path
) -> None:
    plan = _plan(
        game_root,
        _copy(game_root / "mods" / "a.rpf", source_file, InstallTarget.MODS_FOLDER),
        conflicts=ConflictReport(
            conflicts=(
                Conflict(
                    conflict_type=ConflictType.DUPLICATE_DLC,
                    severity=ConflictSeverity.BLOCKING,
                    key="adder2",
                    description="already registered",
                ),
            )
        ),
    )
    validator = PlanValidator()

    assert validator.validate(plan, include_conflicts=False).is_valid
    assert not validator.validate(plan).is_valid


def test_rpf_import_into_mods_copy_is_accepted(game_root: Path, source_file: Path) -> None:
    from gta_mod_manager.models.install_plan import ArchiveMemberImport

    mods_archive = game_root / "mods" / "x64e.rpf"
    mods_archive.parent.mkdir(parents=True, exist_ok=True)
    mods_archive.write_bytes(b"mods copy")
    plan = _plan(
        game_root,
        FileOperation(
            action=FileAction.RPF_IMPORT,
            target_path=mods_archive,
            target_kind=InstallTarget.MODS_FOLDER,
            archive_members=(
                ArchiveMemberImport(
                    source_path=source_file,
                    member_path="levels/gta5/vehicles.rpf/gauntlet.yft",
                ),
            ),
        ),
    )

    assert PlanValidator().validate(plan).is_valid


def test_rpf_import_targeting_original_archive_is_refused(
    game_root: Path, source_file: Path
) -> None:
    from gta_mod_manager.models.install_plan import ArchiveMemberImport

    original = game_root / "x64e.rpf"
    original.write_bytes(b"original")
    plan = _plan(
        game_root,
        FileOperation(
            action=FileAction.RPF_IMPORT,
            target_path=original,
            target_kind=InstallTarget.MODS_FOLDER,
            archive_members=(
                ArchiveMemberImport(
                    source_path=source_file,
                    member_path="levels/gta5/vehicles.rpf/gauntlet.yft",
                ),
            ),
        ),
    )

    report = PlanValidator().validate(plan)
    assert not report.is_valid
    assert any(
        issue.code in {"plan.rpf_import_target", "plan.protected_target", "plan.zone_mismatch"}
        for issue in report.fatal_issues
    )
