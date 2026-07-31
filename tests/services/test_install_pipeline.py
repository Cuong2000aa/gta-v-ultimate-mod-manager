"""End-to-end tests of the scan/analyze/preview/install/undo pipeline."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.bootstrap import Application
from gta_mod_manager.models.enums import ConflictType, ModKind


def _install(application: Application, archive: Path, game_root: Path):
    """Run the whole pipeline for one archive and return the install report."""
    game = application.game.select(game_root).unwrap()
    status = application.game.status(game).unwrap()

    workspace = application.analysis.create_workspace()
    try:
        package = application.analysis.analyze(archive, workspace).unwrap()
        preview = application.install.preview(package, game, status.components).unwrap()
        assert preview.is_installable, preview.blocking_reasons
        return application.install.install(preview).unwrap(), preview
    finally:
        workspace.dispose()


def test_addon_vehicle_installs_into_dlcpacks(
    application: Application, addon_vehicle_zip: Path, game_root: Path
) -> None:
    report, preview = _install(application, addon_vehicle_zip, game_root)

    assert preview.package.classification.primary is ModKind.VEHICLE_ADDON
    assert preview.package.vehicles.spawn_codes == ("adder2",)

    pack_root = game_root / "mods" / "update" / "x64" / "dlcpacks" / "adder2"
    assert (pack_root / "dlc.rpf").is_file()
    assert (pack_root / "setup2.xml").is_file()
    assert report.file_count >= 4

    # Add-on registration is automatic — no OpenIV manual step for dlclist.
    assert not any("dlclist" in step.title.lower() for step in preview.plan.manual_steps)
    assert any(
        op.action.value == "rpf_dlc_register" for op in preview.plan.operations
    )
    mods_update = game_root / "mods" / "update" / "update.rpf"
    assert mods_update.is_file()
    from fivefury import RpfArchive

    with RpfArchive.from_path(str(mods_update)) as archive:
        entry = archive.find_entry("common/data/dlclist.xml")
        assert entry is not None
        text = archive.read_entry_bytes(entry).decode("utf-8", errors="replace")
    assert "dlcpacks:/adder2/" in text


def test_addon_weapon_installs_into_dlcpacks(
    application: Application, addon_weapon_zip: Path, game_root: Path
) -> None:
    report, preview = _install(application, addon_weapon_zip, game_root)

    assert preview.package.classification.primary is ModKind.WEAPON
    pack_root = game_root / "mods" / "update" / "x64" / "dlcpacks" / "demogun"
    assert (pack_root / "dlc.rpf").is_file()
    assert (pack_root / "data" / "weapons.meta").is_file()
    assert report.file_count >= 3
    assert any(op.action.value == "rpf_dlc_register" for op in preview.plan.operations)
    assert not any("dlclist" in step.title.lower() for step in preview.plan.manual_steps)


def test_addon_map_installs_into_dlcpacks(
    application: Application, addon_map_zip: Path, game_root: Path
) -> None:
    report, preview = _install(application, addon_map_zip, game_root)

    assert preview.package.classification.primary is ModKind.MAP
    pack_root = game_root / "mods" / "update" / "x64" / "dlcpacks" / "demomap"
    assert (pack_root / "dlc.rpf").is_file()
    assert (
        pack_root / "x64" / "levels" / "gta5" / "custom_maps" / "demo.ymap"
    ).is_file()
    assert report.file_count >= 3
    assert any(op.action.value == "rpf_dlc_register" for op in preview.plan.operations)
    assert not any("dlclist" in step.title.lower() for step in preview.plan.manual_steps)


def test_addon_vehicle_never_touches_the_game_root(
    application: Application, addon_vehicle_zip: Path, game_root: Path
) -> None:
    before = {item.name for item in game_root.iterdir()}
    _install(application, addon_vehicle_zip, game_root)
    after = {item.name for item in game_root.iterdir()}

    assert after - before == {"mods"}
    assert (game_root / "common.rpf").read_bytes() == b"fake archive"


def test_script_mod_installs_into_scripts_folder(
    application: Application, script_mod_zip: Path, game_root: Path
) -> None:
    report, preview = _install(application, script_mod_zip, game_root)

    assert preview.package.classification.primary is ModKind.SCRIPT_HOOK_DOTNET
    assert (game_root / "scripts" / "CoolScript.dll").is_file()
    assert (game_root / "scripts" / "CoolScript.ini").is_file()
    assert report.file_count >= 2


def test_asi_plugin_installs_into_game_root(
    application: Application, asi_mod_zip: Path, game_root: Path
) -> None:
    _report, preview = _install(application, asi_mod_zip, game_root)

    assert preview.package.classification.primary is ModKind.ASI
    assert (game_root / "SuperPlugin.asi").is_file()
    assert (game_root / "SuperPlugin.ini").is_file()


def test_second_mod_claiming_the_same_dlc_pack_is_blocked(
    application: Application, addon_vehicle_zip: Path, game_root: Path
) -> None:
    _install(application, addon_vehicle_zip, game_root)

    # A different archive shipping the same pack folder is a different mod.
    rival = addon_vehicle_zip.with_name("Another Adder2 Pack.zip")
    rival.write_bytes(addon_vehicle_zip.read_bytes() + b"\x00")

    game = application.game.select(game_root).unwrap()
    workspace = application.analysis.create_workspace()
    try:
        package = application.analysis.analyze(rival, workspace).unwrap()
        second = application.install.preview(package, game).unwrap()
    finally:
        workspace.dispose()

    duplicates = second.plan.conflicts.by_type(ConflictType.DUPLICATE_DLC)
    assert duplicates
    assert not second.is_installable


def test_reinstalling_the_same_mod_is_allowed(
    application: Application, addon_vehicle_zip: Path, game_root: Path
) -> None:
    _install(application, addon_vehicle_zip, game_root)
    second_report, second_preview = _install(application, addon_vehicle_zip, game_root)

    assert not second_preview.plan.conflicts.has_blocking
    assert second_report.file_count >= 4


def test_uninstall_removes_every_installed_file(
    application: Application, addon_vehicle_zip: Path, game_root: Path
) -> None:
    report, _preview = _install(application, addon_vehicle_zip, game_root)

    removed = application.library.uninstall(report.mod.mod_id).unwrap()

    assert removed == report.file_count
    assert not (game_root / "mods" / "update" / "x64" / "dlcpacks" / "adder2").exists()
    assert application.library.get(report.mod.mod_id) is None


def test_uninstall_reports_progress_for_each_phase(
    application: Application, addon_vehicle_zip: Path, game_root: Path
) -> None:
    report, _preview = _install(application, addon_vehicle_zip, game_root)
    reporter = _RecordingReporter()

    application.library.uninstall(report.mod.mod_id, reporter=reporter).unwrap()

    labels = [label for _operation, label in reporter.events]
    assert any("Backing up" in label for label in labels)
    assert any("Deleting the files" in label for label in labels)
    assert reporter.finished


class _RecordingReporter:
    """Collects every progress call so tests can assert on the phases."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []
        self.finished: list[str] = []

    def start(self, operation_id: str, label: str, total: int = 0) -> None:
        self.events.append((operation_id, label))

    def advance(self, operation_id: str, current: int, label: str | None = None) -> None:
        self.events.append((operation_id, label or ""))

    def finish(self, operation_id: str, label: str | None = None) -> None:
        self.finished.append(operation_id)


def test_undo_restores_the_state_before_installation(
    application: Application, addon_vehicle_zip: Path, game_root: Path
) -> None:
    _install(application, addon_vehicle_zip, game_root)
    pack_root = game_root / "mods" / "update" / "x64" / "dlcpacks" / "adder2"
    assert pack_root.is_dir()

    application.backups.undo_last().unwrap()

    assert not (pack_root / "dlc.rpf").exists()


def test_library_lists_and_searches_installed_mods(
    application: Application, addon_vehicle_zip: Path, game_root: Path
) -> None:
    report, _preview = _install(application, addon_vehicle_zip, game_root)
    game = application.game.select(game_root).unwrap()

    installed = application.library.list_installed(game)
    assert [item.mod_id for item in installed] == [report.mod.mod_id]
    assert application.library.search("adder2", game)
    assert not application.library.search("no such mod", game)


def test_conflict_center_audit_is_clean_for_a_single_mod(
    application: Application, addon_vehicle_zip: Path, game_root: Path
) -> None:
    _install(application, addon_vehicle_zip, game_root)
    game = application.game.select(game_root).unwrap()

    report = application.conflicts.audit(game)

    assert not report.has_blocking
