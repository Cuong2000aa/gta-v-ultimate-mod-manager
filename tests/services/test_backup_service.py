"""Tests for slim pre-install snapshots (no full shared RPF copies)."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.models.enums import FileAction, InstallTarget
from gta_mod_manager.models.install_plan import FileOperation, InstallPlan
from gta_mod_manager.services.backup_service import BackupService


class _Bus:
    def publish(self, _event: object) -> None:
        return None


def test_snapshot_for_plan_skips_in_place_archive_edits(tmp_path: Path) -> None:
    """A replace import into x64e.rpf must not be full-copied; the script is."""
    game = tmp_path / "game"
    rpf = game / "mods" / "x64e.rpf"
    script = game / "scripts" / "Cool.dll"
    rpf.parent.mkdir(parents=True)
    script.parent.mkdir(parents=True)
    rpf.write_bytes(b"huge")
    script.write_bytes(b"dll")

    captured: dict[str, object] = {}

    class _Engine:
        def create(self, **kwargs):  # noqa: ANN003
            captured.update(kwargs)
            return "snap"

    service = BackupService(_Engine(), object(), _Bus())  # type: ignore[arg-type]
    plan = InstallPlan(
        plan_id="p1",
        package_id="mod1",
        display_name="Cool",
        game_root=game,
        operations=(
            FileOperation(
                action=FileAction.RPF_IMPORT,
                target_path=rpf,
                target_kind=InstallTarget.MODS_FOLDER,
                description="import",
            ),
            FileOperation(
                action=FileAction.COPY,
                target_path=script,
                source_path=script,
                target_kind=InstallTarget.SCRIPTS_FOLDER,
                description="script",
            ),
        ),
    )

    result = service.snapshot_for_plan(plan, "op1")

    assert result == "snap"
    assert captured["paths"] == [script]


def test_snapshot_for_plan_still_backs_up_a_copied_dlc_pack(tmp_path: Path) -> None:
    """A freshly copied dlc.rpf pack under mods/ is small and must be backed up."""
    game = tmp_path / "game"
    pack = game / "mods" / "update" / "x64" / "dlcpacks" / "adder2" / "dlc.rpf"
    update = game / "mods" / "update" / "update.rpf"
    pack.parent.mkdir(parents=True)
    update.parent.mkdir(parents=True, exist_ok=True)
    pack.write_bytes(b"pack")
    update.write_bytes(b"huge")

    captured: dict[str, object] = {}

    class _Engine:
        def create(self, **kwargs):  # noqa: ANN003
            captured.update(kwargs)
            return "snap"

    service = BackupService(_Engine(), object(), _Bus())  # type: ignore[arg-type]
    plan = InstallPlan(
        plan_id="p1",
        package_id="car",
        display_name="Adder2",
        game_root=game,
        operations=(
            FileOperation(
                action=FileAction.COPY,
                target_path=pack,
                source_path=pack,
                target_kind=InstallTarget.DLC_PACKS,
                description="copy pack",
            ),
            FileOperation(
                action=FileAction.RPF_DLC_REGISTER,
                target_path=update,
                target_kind=InstallTarget.MODS_FOLDER,
                description="dlclist",
            ),
        ),
    )

    assert service.snapshot_for_plan(plan, "op1") == "snap"
    assert captured["paths"] == [pack]  # update.rpf skipped, pack kept


def test_snapshot_for_plan_returns_none_when_only_in_place_edits(
    tmp_path: Path,
) -> None:
    game = tmp_path / "game"
    rpf = game / "mods" / "update" / "update.rpf"
    rpf.parent.mkdir(parents=True)
    rpf.write_bytes(b"huge")

    class _Engine:
        def create(self, **_kwargs):  # noqa: ANN003
            raise AssertionError("must not create a snapshot")

    service = BackupService(_Engine(), object(), _Bus())  # type: ignore[arg-type]
    plan = InstallPlan(
        plan_id="p1",
        package_id="car",
        display_name="Car",
        game_root=game,
        operations=(
            FileOperation(
                action=FileAction.RPF_DLC_REGISTER,
                target_path=rpf,
                target_kind=InstallTarget.MODS_FOLDER,
                description="dlclist",
            ),
        ),
    )

    assert service.snapshot_for_plan(plan, "op1") is None
