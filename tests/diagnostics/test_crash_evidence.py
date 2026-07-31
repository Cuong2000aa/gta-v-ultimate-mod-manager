"""Tests for the game-session crash evidence collector."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from gta_mod_manager.diagnostics.crash_evidence import collect_session_evidence
from gta_mod_manager.models.diagnostic import DiagnosticSeverity
from gta_mod_manager.models.mod_package import InstalledFileRecord, InstalledMod

_SHVDN_LOG = """\
[12:00:01] [INFO] Loading scripts from 'scripts' ...
[12:00:02] [INFO] Started script ZombiesMod.Main.
[12:05:44] [ERROR] The exception was thrown while executing the script \
ZombiesMod.Main from "G:\\Game\\GTAV\\scripts\\ZombiesMod.dll".
System.NullReferenceException: Object reference not set to an instance of an object.
   at GTA.Native.NativeMemory+FwScriptGuidPoolTask.Run()
[12:05:44] [ERROR] Aborted script ZombiesMod.Main.
[12:05:50] [WARNING] Failed to load script assembly PedSelector.dll (missing \
dependency ScriptHookVDotNet3).
"""


def _mod(
    name: str, game_root: Path, files: tuple[Path, ...], installed_at: datetime
) -> InstalledMod:
    return InstalledMod(
        mod_id=name.lower(),
        display_name=name,
        game_root=game_root,
        kind="script",
        installed_at=installed_at,
        installed_files=tuple(InstalledFileRecord(target_path=path) for path in files),
    )


def _codes(report) -> set[str]:
    return {finding.code for finding in report.findings}


def test_clean_exit_produces_an_ok_finding(tmp_path: Path) -> None:
    started = datetime.now(timezone.utc) - timedelta(minutes=30)
    ended = datetime.now(timezone.utc)

    report = collect_session_evidence(
        game_root=tmp_path,
        process_name="GTA5.exe",
        installed=(),
        started_at=started,
        ended_at=ended,
        exit_code=0,
        dump_dir=tmp_path / "no_dumps",
    )

    assert not report.crashed
    assert "crash.session_ok" in _codes(report)
    assert report.top_suspect is None


def test_nonzero_exit_code_marks_the_session_as_crashed(tmp_path: Path) -> None:
    started = datetime.now(timezone.utc) - timedelta(minutes=10)
    ended = datetime.now(timezone.utc)

    report = collect_session_evidence(
        game_root=tmp_path,
        process_name="GTA5.exe",
        installed=(),
        started_at=started,
        ended_at=ended,
        exit_code=0xC0000005,
        dump_dir=tmp_path / "no_dumps",
    )

    assert report.crashed
    codes = _codes(report)
    assert "crash.exit_code" in codes
    finding = next(f for f in report.findings if f.code == "crash.exit_code")
    assert "0xC0000005" in finding.title
    assert finding.fix_targets == ("0xC0000005",)


def test_status_breakpoint_exit_code_is_a_crash(tmp_path: Path) -> None:
    """GTA crash reports can exit with STATUS_BREAKPOINT (0x80000003)."""
    started = datetime.now(timezone.utc) - timedelta(minutes=3)
    ended = datetime.now(timezone.utc)

    report = collect_session_evidence(
        game_root=tmp_path,
        process_name="GTA5.exe",
        installed=(),
        started_at=started,
        ended_at=ended,
        exit_code=0x80000003,
        dump_dir=tmp_path / "no_dumps",
    )

    assert report.crashed
    finding = next(f for f in report.findings if f.code == "crash.exit_code")
    assert finding.fix_targets == ("0x80000003",)


def test_small_nonzero_exit_codes_are_treated_as_a_normal_quit(tmp_path: Path) -> None:
    """GTA V often returns 9 (and similar) when the player quits cleanly."""
    started = datetime.now(timezone.utc) - timedelta(minutes=10)
    ended = datetime.now(timezone.utc)

    report = collect_session_evidence(
        game_root=tmp_path,
        process_name="GTA5.exe",
        installed=(),
        started_at=started,
        ended_at=ended,
        exit_code=9,
        dump_dir=tmp_path / "no_dumps",
    )

    assert not report.crashed
    assert "crash.exit_code" not in _codes(report)
    assert "crash.session_ok" in _codes(report)


def test_new_crash_dump_is_detected(tmp_path: Path) -> None:
    dumps = tmp_path / "CrashDumps"
    dumps.mkdir()
    (dumps / "GTA5.exe.1234.dmp").write_bytes(b"MDMP")
    started = datetime.now(timezone.utc) - timedelta(minutes=5)

    report = collect_session_evidence(
        game_root=tmp_path,
        process_name="GTA5.exe",
        installed=(),
        started_at=started,
        ended_at=datetime.now(timezone.utc),
        exit_code=0,  # WER can catch a crash even with a clean-looking exit
        dump_dir=dumps,
    )

    assert report.crashed
    assert "crash.dump" in _codes(report)


def test_old_crash_dumps_are_ignored(tmp_path: Path) -> None:
    import os

    dumps = tmp_path / "CrashDumps"
    dumps.mkdir()
    stale = dumps / "GTA5.exe.999.dmp"
    stale.write_bytes(b"MDMP")
    old = (datetime.now(timezone.utc) - timedelta(days=3)).timestamp()
    os.utime(stale, (old, old))

    report = collect_session_evidence(
        game_root=tmp_path,
        process_name="GTA5.exe",
        installed=(),
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ended_at=datetime.now(timezone.utc),
        exit_code=0,
        dump_dir=dumps,
    )

    assert not report.crashed
    assert "crash.dump" not in _codes(report)


def test_script_errors_are_mapped_to_the_owning_mod(tmp_path: Path) -> None:
    (tmp_path / "ScriptHookVDotNet.log").write_text(_SHVDN_LOG, encoding="utf-8")
    now = datetime.now(timezone.utc)
    zombie = _mod(
        "Simple Zombie Mod",
        tmp_path,
        (tmp_path / "scripts" / "ZombiesMod.dll",),
        installed_at=now - timedelta(days=10),
    )

    report = collect_session_evidence(
        game_root=tmp_path,
        process_name="GTA5.exe",
        installed=(zombie,),
        started_at=now - timedelta(minutes=20),
        ended_at=now,
        exit_code=0xC0000005,
        dump_dir=tmp_path / "no_dumps",
    )

    errors = [f for f in report.findings if f.code == "crash.script_error"]
    assert len(errors) == 1
    assert "ZombiesMod.dll" in errors[0].title
    assert "Simple Zombie Mod" in errors[0].title
    assert errors[0].severity is DiagnosticSeverity.ERROR
    assert "NullReferenceException" in errors[0].evidence
    assert errors[0].fix_action == "disable_mods"
    assert errors[0].fix_targets == ("simple zombie mod",)

    loads = [f for f in report.findings if f.code == "crash.script_load"]
    assert len(loads) == 1
    assert "PedSelector.dll" in loads[0].title
    assert loads[0].fix_action == ""
    assert loads[0].fix_targets == ()

    # The most urgent suspect should be the crashing script, not the load failure.
    assert report.top_suspect is not None
    assert report.top_suspect.code in {"crash.script_error", "crash.exit_code"}


def test_stale_shvdn_log_from_an_earlier_session_is_ignored(tmp_path: Path) -> None:
    import os

    log = tmp_path / "ScriptHookVDotNet.log"
    log.write_text(_SHVDN_LOG, encoding="utf-8")
    old = (datetime.now(timezone.utc) - timedelta(days=2)).timestamp()
    os.utime(log, (old, old))

    report = collect_session_evidence(
        game_root=tmp_path,
        process_name="GTA5.exe",
        installed=(),
        started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        ended_at=datetime.now(timezone.utc),
        exit_code=0,
        dump_dir=tmp_path / "no_dumps",
    )

    assert "crash.script_error" not in _codes(report)


def test_recently_installed_mods_are_listed_as_suspects(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    fresh = _mod("Fresh Mod", tmp_path, (), installed_at=now - timedelta(hours=2))
    ancient = _mod("Ancient Mod", tmp_path, (), installed_at=now - timedelta(days=30))

    report = collect_session_evidence(
        game_root=tmp_path,
        process_name="GTA5.exe",
        installed=(fresh, ancient),
        started_at=now - timedelta(minutes=5),
        ended_at=now,
        exit_code=0,
        dump_dir=tmp_path / "no_dumps",
    )

    recent = [f for f in report.findings if f.code == "crash.recent_mods"]
    assert len(recent) == 1
    assert recent[0].fix_action == "disable_mods"
    assert "fresh mod" in recent[0].fix_targets
    assert "ancient mod" not in recent[0].fix_targets
    assert "Fresh Mod" in recent[0].detail


def test_crash_without_evidence_yields_isolation_advice(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)

    report = collect_session_evidence(
        game_root=tmp_path,
        process_name="GTA5.exe",
        installed=(),
        started_at=now - timedelta(hours=1),
        ended_at=now,
        exit_code=0xC0000005,
        dump_dir=tmp_path / "no_dumps",
    )

    assert report.crashed
    assert "crash.no_evidence" in _codes(report)
