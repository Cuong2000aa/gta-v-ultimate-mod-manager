"""Turns the traces of one game session into diagnostic findings.

After the watched game process exits, this module answers the question the
user actually asks: *did it crash, and which mod did it?* Evidence comes from
three sources:

1. The process exit code — NTSTATUS warning/error exceptions
   (``0x8xxxxxxx`` / ``0xCxxxxxxx``) count. GTA V routinely returns small
   non-zero codes such as ``9`` on a normal quit, so those must not be
   treated as crashes.
2. Windows crash dumps (``%LOCALAPPDATA%/CrashDumps/GTA5.exe*.dmp``).
3. ``ScriptHookVDotNet.log``, which names the exact script ``.dll`` that threw.

Script files are mapped back to the installed mod that shipped them, so the
report can say "ZombiesMod.dll (mod: Simple Zombie Mod)" instead of a bare
file name.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.crash_report import GameSessionReport
from gta_mod_manager.diagnostics.actions import FIX_DISABLE_MODS
from gta_mod_manager.models.diagnostic import DiagnosticFinding, DiagnosticSeverity
from gta_mod_manager.models.mod_package import InstalledMod

_LOGGER = get_logger("diagnostics.crash_evidence")

#: Log written by ScriptHookVDotNet next to the game executable.
_SHVDN_LOG = "ScriptHookVDotNet.log"

#: Grace period for file timestamps: logs are written slightly after launch.
_MTIME_SLACK = timedelta(seconds=90)

#: Mods installed within this window before the crash count as "recent".
_RECENT_INSTALL_WINDOW = timedelta(hours=48)

#: `[ERROR] The exception was thrown while executing the script X from "path"`.
_SCRIPT_ERROR_PATTERN = re.compile(
    r"exception was thrown while executing the script .+? from \"(?P<path>[^\"]+)\"",
    re.IGNORECASE,
)

#: `Failed to load script assembly X ...`.
_SCRIPT_LOAD_PATTERN = re.compile(
    r"Failed to load script assembly (?P<name>[\w .\-]+\.dll)", re.IGNORECASE
)

def is_crash_like_exit_code(exit_code: int | None) -> bool:
    """Return whether ``exit_code`` looks like a real process crash.

    Rockstar / GTA V often exits with small integers (``1``, ``9``, …) when
    the player quits from the pause menu. Those are not crashes. Real native
    crashes commonly surface as NTSTATUS warning/error codes
    (``0x80000003`` breakpoint, ``0xC0000005`` access violation,
    ``0xC0000409`` stack buffer overrun, …).
    """
    if exit_code is None:
        return False
    code = exit_code & 0xFFFFFFFF
    return code >= 0x80000000


def default_crash_dump_dir() -> Path | None:
    """Return ``%LOCALAPPDATA%/CrashDumps``, where Windows drops user dumps."""
    base = os.environ.get("LOCALAPPDATA")
    return Path(base) / "CrashDumps" if base else None


def collect_session_evidence(
    game_root: Path,
    process_name: str,
    installed: Sequence[InstalledMod],
    started_at: datetime,
    ended_at: datetime,
    exit_code: int | None,
    dump_dir: Path | None = None,
) -> GameSessionReport:
    """Build the report for one finished game session.

    Args:
        game_root: Folder holding ``GTA5.exe`` and the ScriptHook logs.
        process_name: Watched executable name.
        installed: Mods currently tracked for this installation.
        started_at: Session start (UTC).
        ended_at: Session end (UTC).
        exit_code: Exit code of the game process, or ``None`` when unknown.
        dump_dir: Override of the Windows crash dump folder (for tests).
    """
    findings: list[DiagnosticFinding] = []

    dumps = _new_crash_dumps(dump_dir or default_crash_dump_dir(), process_name, started_at)
    fatal_exit = is_crash_like_exit_code(exit_code)
    crashed = bool(dumps) or fatal_exit

    if fatal_exit and exit_code is not None:
        code_hex = f"0x{exit_code & 0xFFFFFFFF:08X}"
        findings.append(
            DiagnosticFinding(
                code="crash.exit_code",
                severity=DiagnosticSeverity.ERROR,
                title=f"The game exited abnormally (code {code_hex})",
                detail=(
                    "The exit code is an NTSTATUS warning/error exception "
                    "(0x8xxxxxxx or 0xCxxxxxxx), which means the game process "
                    "crashed rather than being closed normally."
                ),
                category="crash",
                fix_targets=(code_hex,),
            )
        )

    if dumps:
        names = tuple(dump.name for dump in dumps)
        findings.append(
            DiagnosticFinding(
                code="crash.dump",
                severity=DiagnosticSeverity.ERROR,
                title=f"Windows wrote {len(dumps)} crash dump(s) during this session",
                detail="A crash dump is definite proof the game crashed.",
                evidence="\n".join(str(dump) for dump in dumps[:5]),
                category="crash",
                fix_targets=names,
            )
        )

    script_findings = _script_findings(game_root, installed, started_at)
    findings.extend(script_findings)
    findings.extend(_recent_install_findings(installed, ended_at))

    if crashed and not script_findings:
        findings.append(
            DiagnosticFinding(
                code="crash.no_evidence",
                severity=DiagnosticSeverity.WARNING,
                title="The game crashed but no script left evidence",
                detail=(
                    "No script errors were logged. Typical causes are native "
                    ".asi plugins, texture/vehicle mods exceeding memory pools, "
                    "or an outdated ScriptHookV after a game update."
                ),
                fix=(
                    "Rename dinput8.dll to dinput8.dll.off and start the game; "
                    "if it stops crashing, re-enable mods in small groups."
                ),
                category="crash",
            )
        )
    if not crashed and not any(item.is_problem for item in findings):
        findings.append(
            DiagnosticFinding(
                code="crash.session_ok",
                severity=DiagnosticSeverity.OK,
                title="Last game session ended normally",
                detail="No crash dump and a clean exit code were observed.",
                category="crash",
            )
        )

    report = GameSessionReport(
        game_root=game_root,
        process_name=process_name,
        started_at=started_at,
        ended_at=ended_at,
        exit_code=exit_code,
        crashed=crashed,
        findings=tuple(findings),
    )
    _LOGGER.info(
        "Session report: crashed=%s exit_code=%s duration=%ss findings=%d",
        report.crashed,
        report.exit_code,
        report.duration_seconds,
        len(report.findings),
    )
    return report


def _new_crash_dumps(
    dump_dir: Path | None, process_name: str, started_at: datetime
) -> tuple[Path, ...]:
    """Return crash dumps for ``process_name`` written since ``started_at``."""
    if dump_dir is None or not dump_dir.is_dir():
        return ()
    stem = Path(process_name).stem.lower()
    threshold = (started_at - _MTIME_SLACK).timestamp()
    dumps: list[Path] = []
    try:
        for item in dump_dir.iterdir():
            if not item.name.lower().startswith(stem):
                continue
            if item.suffix.lower() != ".dmp":
                continue
            try:
                if item.stat().st_mtime >= threshold:
                    dumps.append(item)
            except OSError:
                continue
    except OSError as error:
        _LOGGER.debug("Could not list crash dumps in %s: %s", dump_dir, error)
        return ()
    return tuple(sorted(dumps))


def _script_findings(
    game_root: Path, installed: Sequence[InstalledMod], started_at: datetime
) -> tuple[DiagnosticFinding, ...]:
    """Parse the SHVDN log of this session for failing script assemblies."""
    log_path = game_root / _SHVDN_LOG
    if not log_path.is_file():
        return ()
    try:
        if log_path.stat().st_mtime < (started_at - _MTIME_SLACK).timestamp():
            return ()  # stale log from an earlier session
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        _LOGGER.debug("Could not read %s: %s", log_path, error)
        return ()

    owners = _script_owner_index(installed)
    findings: list[DiagnosticFinding] = []

    crashed_scripts = {
        Path(match.group("path")).name for match in _SCRIPT_ERROR_PATTERN.finditer(text)
    }
    for name in sorted(crashed_scripts):
        owner = owners.get(name.lower())
        suffix = f" (mod: {owner.display_name})" if owner else ""
        findings.append(
            DiagnosticFinding(
                code="crash.script_error",
                severity=DiagnosticSeverity.ERROR,
                title=f"Script {name} threw errors and was aborted{suffix}",
                detail=(
                    "ScriptHookVDotNet logged unhandled exceptions from this "
                    "script during the session. The script is either broken or "
                    "incompatible with the current game/SHVDN version."
                ),
                fix=(
                    f"Disable or uninstall the mod that ships {name}, or update "
                    "ScriptHookVDotNet."
                ),
                evidence=_excerpt_for(text, name),
                category="crash",
                fix_action=FIX_DISABLE_MODS if owner is not None else "",
                fix_targets=(owner.mod_id,) if owner is not None else (),
            )
        )

    failed_loads = {
        match.group("name").strip() for match in _SCRIPT_LOAD_PATTERN.finditer(text)
    }
    for name in sorted(failed_loads):
        owner = owners.get(name.lower())
        suffix = f" (mod: {owner.display_name})" if owner else ""
        findings.append(
            DiagnosticFinding(
                code="crash.script_load",
                severity=DiagnosticSeverity.WARNING,
                title=f"Script {name} failed to load{suffix}",
                detail=(
                    "The assembly could not be loaded, usually because a "
                    "dependency (ScriptHookVDotNet version, NativeUI, ...) is "
                    "missing or too old."
                ),
                fix=(
                    "Install/update the dependency named in the log excerpt, "
                    "or disable the owning mod if it is broken."
                ),
                evidence=_excerpt_for(text, name),
                category="crash",
                fix_action=FIX_DISABLE_MODS if owner is not None else "",
                fix_targets=(owner.mod_id,) if owner is not None else (),
            )
        )
    return tuple(findings)


def _recent_install_findings(
    installed: Sequence[InstalledMod], ended_at: datetime
) -> tuple[DiagnosticFinding, ...]:
    """List mods installed shortly before the session ended."""
    threshold = ended_at - _RECENT_INSTALL_WINDOW
    recent = sorted(
        (mod for mod in installed if _as_utc(mod.installed_at) >= threshold),
        key=lambda mod: mod.installed_at,
        reverse=True,
    )
    if not recent:
        return ()
    names = tuple(mod.display_name for mod in recent[:8])
    return (
        DiagnosticFinding(
            code="crash.recent_mods",
            severity=DiagnosticSeverity.INFO,
            title=f"{len(recent)} mod(s) were installed in the last 48 hours",
            detail=(
                "Recently installed mods are the prime suspects after a new "
                "crash: " + ", ".join(names)
            ),
            fix="If the crash started after one of these, disable it first.",
            category="crash",
            fix_action=FIX_DISABLE_MODS,
            fix_targets=tuple(mod.mod_id for mod in recent[:8]),
        ),
    )


def _script_owner_index(installed: Sequence[InstalledMod]) -> dict[str, InstalledMod]:
    """Map lowercase installed file names to the mod that wrote them."""
    index: dict[str, InstalledMod] = {}
    for mod in installed:
        for record in mod.installed_files:
            index.setdefault(record.target_path.name.lower(), mod)
    return index


def _excerpt_for(text: str, needle: str, context: int = 6, limit: int = 900) -> str:
    """Return the log lines around the first mention of ``needle``."""
    lines = text.splitlines()
    for position, line in enumerate(lines):
        if needle.lower() in line.lower():
            start = max(0, position - 1)
            snippet = "\n".join(lines[start : position + context])
            return snippet[:limit]
    return ""


def _as_utc(value: datetime) -> datetime:
    """Return ``value`` as an aware UTC datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
