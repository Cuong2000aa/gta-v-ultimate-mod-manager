"""Scan a GTA V install for common crash causes and log signatures."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.diagnostics.actions import (
    FIX_DELETE_ORPHAN_DLCPACKS,
    FIX_QUARANTINE_ENB_LEFTOVERS,
    FIX_RESTORE_VEHICLE_STREAM,
)
from gta_mod_manager.diagnostics.catalog import KNOWN_ERROR_PATTERNS
from gta_mod_manager.diagnostics.enb import (
    has_enb_config,
    has_enb_proxy_dll,
    list_enb_leftover_files,
)
from gta_mod_manager.diagnostics.vehicle_checks import (
    find_bad_vehicle_stream_entries,
    find_orphan_dlcpacks,
    find_unhealthy_replace_members,
)
from gta_mod_manager.models.component import ComponentReport
from gta_mod_manager.models.diagnostic import (
    DiagnosticFinding,
    DiagnosticReport,
    DiagnosticSeverity,
)
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.mod_package import InstalledMod

_LOGGER = get_logger("diagnostics.scanner")

#: Log files commonly left in the game root by ASI / OpenIV / ScriptHook.
_GAME_LOG_NAMES: tuple[str, ...] = (
    "asiloader.log",
    "ScriptHookV.log",
    "ScriptHookVDotNet.log",
    "OpenIV.log",
    "HeapAdjuster.log",
)


class DiagnosticsScanner:
    """Produces a :class:`DiagnosticReport` for one installation."""

    def scan(
        self,
        install: GameInstall,
        components: ComponentReport | None = None,
        installed_mods: tuple[InstalledMod, ...] | None = None,
    ) -> DiagnosticReport:
        """Run every check against ``install``."""
        findings: list[DiagnosticFinding] = []
        root = install.root_path
        library = installed_mods or ()

        findings.extend(self._scan_logs(root))
        findings.extend(self._scan_enb(root))
        findings.extend(self._scan_asi_stack(root, components))
        findings.extend(self._scan_mods_folder(root))
        findings.extend(self._scan_orphan_dlcpacks(root, library))
        findings.extend(self._scan_vehicle_stream(root, library))
        findings.extend(self._scan_commandline(root))

        if not any(item.is_problem for item in findings):
            findings.append(
                DiagnosticFinding(
                    code="ok.clean",
                    severity=DiagnosticSeverity.OK,
                    title="No known crash signatures found",
                    detail=(
                        "Logs and common graphics-mod pitfalls look clean. "
                        "If the game still fails, try renaming the mods folder and verifying game files."
                    ),
                    category="summary",
                )
            )

        _LOGGER.info(
            "Diagnostics for %s: %d finding(s)",
            root,
            len(findings),
        )
        return DiagnosticReport(game_root=root, findings=tuple(findings))

    def _scan_logs(self, root: Path) -> list[DiagnosticFinding]:
        """Match known error patterns in game-root log files."""
        findings: list[DiagnosticFinding] = []
        seen_codes: set[str] = set()
        for name in _GAME_LOG_NAMES:
            path = root / name
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError as error:
                findings.append(
                    DiagnosticFinding(
                        code=f"log.unreadable.{name}",
                        severity=DiagnosticSeverity.INFO,
                        title=f"Could not read {name}",
                        detail=str(error),
                        category="logs",
                    )
                )
                continue
            # Prefer the tail — recent crashes matter most.
            sample = text[-120_000:] if len(text) > 120_000 else text
            lowered = sample.lower()
            for pattern in KNOWN_ERROR_PATTERNS:
                if pattern.code in seen_codes:
                    continue
                if not any(needle.lower() in lowered for needle in pattern.needles):
                    continue
                seen_codes.add(pattern.code)
                snippet = _snippet_around(sample, pattern.needles[0])
                findings.append(
                    DiagnosticFinding(
                        code=pattern.code,
                        severity=_severity(pattern.severity),
                        title=pattern.title,
                        detail=pattern.detail,
                        fix=pattern.fix,
                        evidence=f"{name}: {snippet}" if snippet else name,
                        category=pattern.category,
                    )
                )
        return findings

    def _scan_enb(self, root: Path) -> list[DiagnosticFinding]:
        """Detect ENB config left behind without the required proxy DLL."""
        if not has_enb_config(root):
            return []
        leftovers = list_enb_leftover_files(root)
        if has_enb_proxy_dll(root):
            return [
                DiagnosticFinding(
                    code="enb.present",
                    severity=DiagnosticSeverity.INFO,
                    title="ENB / graphics proxy detected",
                    detail=(
                        "ENB config and a DirectX proxy DLL are present. "
                        "These often cause ERR_GFX_D3D_INIT when incompatible."
                    ),
                    fix=(
                        "If the game fails to start, use Repair selected to quarantine "
                        "enb*.ini / enb*.fx, or rename d3d11.dll / dxgi.dll manually."
                    ),
                    category="graphics",
                    fix_action=FIX_QUARANTINE_ENB_LEFTOVERS if leftovers else "",
                    fix_targets=leftovers,
                )
            ]
        return [
            DiagnosticFinding(
                code="enb.orphan_config",
                severity=DiagnosticSeverity.WARNING,
                title="ENB config without d3d11.dll / dxgi.dll",
                detail=(
                    "enblocal.ini / enbseries.ini exist but no DirectX proxy DLL was found. "
                    "This leftover setup commonly contributes to ERR_GFX_D3D_INIT."
                ),
                fix=(
                    "Use Repair selected to move enb*.ini / enb*.fx into "
                    f"{constants.ENB_QUARANTINE_FOLDER}/ (reversible). "
                    "Or reinstall ENB fully including d3d11.dll."
                ),
                category="graphics",
                fix_action=FIX_QUARANTINE_ENB_LEFTOVERS if leftovers else "",
                fix_targets=leftovers,
            )
        ]

    def _scan_asi_stack(
        self, root: Path, components: ComponentReport | None
    ) -> list[DiagnosticFinding]:
        """Check ASI loader + OpenIV.asi presence when mods are in use."""
        findings: list[DiagnosticFinding] = []
        has_dinput = (root / "dinput8.dll").is_file()
        has_openiv = (root / "OpenIV.asi").is_file()
        has_scripthook = (root / "ScriptHookV.dll").is_file()
        mods_dir = root / constants.MODS_FOLDER_NAME
        mods_in_use = mods_dir.is_dir() and any(mods_dir.iterdir())

        if mods_in_use and not has_openiv:
            findings.append(
                DiagnosticFinding(
                    code="asi.openiv_missing",
                    severity=DiagnosticSeverity.ERROR,
                    title="OpenIV.asi missing while mods/ has content",
                    detail="The mods folder will be ignored without OpenIV.asi (ASI Loader).",
                    fix="Install OpenIV.asi into the game root (same folder as GTA5.exe).",
                    category="asi",
                )
            )
        if mods_in_use and not has_dinput:
            findings.append(
                DiagnosticFinding(
                    code="asi.dinput_missing",
                    severity=DiagnosticSeverity.ERROR,
                    title="ASI Loader (dinput8.dll) missing",
                    detail="Without dinput8.dll, .asi plugins including OpenIV.asi will not load.",
                    fix="Install the ASI Loader into the game root.",
                    category="asi",
                )
            )
        if not has_scripthook and (
            (root / "Menyoo.asi").is_file() or (root / "ScriptHookVDotNet.asi").is_file()
        ):
            findings.append(
                DiagnosticFinding(
                    code="asi.scripthook_missing",
                    severity=DiagnosticSeverity.WARNING,
                    title="ScriptHookV.dll missing but script ASIs are present",
                    detail="Menyoo / SHVDN need ScriptHookV.dll matching your game build.",
                    fix="Install a compatible ScriptHookV.dll.",
                    category="asi",
                )
            )

        if components is not None:
            for missing in components.missing_dependencies:
                findings.append(
                    DiagnosticFinding(
                        code=f"component.{missing.component_id}",
                        severity=DiagnosticSeverity.WARNING,
                        title=f"Component missing: {missing.display_name}",
                        detail=missing.details or "Required or recommended component not found.",
                        fix="Install the missing component, then re-scan.",
                        category="components",
                    )
                )
        return findings

    def _scan_mods_folder(self, root: Path) -> list[DiagnosticFinding]:
        """Sanity-check the mods folder size / presence of large RPFs."""
        mods = root / constants.MODS_FOLDER_NAME
        if not mods.is_dir():
            return [
                DiagnosticFinding(
                    code="mods.missing",
                    severity=DiagnosticSeverity.INFO,
                    title="No mods folder yet",
                    detail="Safe installs go under mods/. Create it by installing a mod or manually.",
                    category="mods",
                )
            ]
        x64e = mods / "x64e.rpf"
        findings: list[DiagnosticFinding] = []
        if x64e.is_file():
            size_mb = x64e.stat().st_size / (1024 * 1024)
            findings.append(
                DiagnosticFinding(
                    code="mods.x64e_present",
                    severity=DiagnosticSeverity.INFO,
                    title=f"mods/x64e.rpf present ({size_mb:.0f} MB)",
                    detail=(
                        "Replace vehicles are loaded from this OpenIV.asi copy. "
                        "If the game crashes at launch, rename mods to mods_off to test."
                    ),
                    fix="Rename the mods folder temporarily if you need to isolate graphics crashes.",
                    category="mods",
                )
            )
        return findings

    def _scan_orphan_dlcpacks(
        self,
        root: Path,
        installed: tuple[InstalledMod, ...],
    ) -> list[DiagnosticFinding]:
        """Detect dlcpack folders left behind after a bad uninstall."""
        orphans = find_orphan_dlcpacks(root, installed)
        findings: list[DiagnosticFinding] = []
        for orphan in orphans:
            findings.append(
                DiagnosticFinding(
                    code="mods.orphan_dlcpack",
                    severity=DiagnosticSeverity.WARNING,
                    title=f"Orphan DLC pack folder: {orphan.pack_name}",
                    detail=(
                        "This folder sits under mods/update/x64/dlcpacks but is not tracked "
                        "by any installed mod in the library. Leftovers like 'hellcat' after a "
                        "bad uninstall commonly cause ERR_SYS_INVALIDRESOURCE or spawn failures. "
                        "If you installed this pack outside the manager and still want it, "
                        "keep the folder and re-import the mod into the library instead."
                    ),
                    fix=(
                        "Delete this orphan pack folder from mods/update/x64/dlcpacks "
                        "(and remove matching dlclist entries). Use Repair selected for a safe fix."
                    ),
                    evidence=str(orphan.path),
                    category="vehicles",
                    fix_action=FIX_DELETE_ORPHAN_DLCPACKS,
                    fix_targets=(orphan.pack_name,),
                )
            )
        return findings

    def _scan_vehicle_stream(
        self,
        root: Path,
        installed: tuple[InstalledMod, ...],
    ) -> list[DiagnosticFinding]:
        """Detect binary-typed vehicle meshes/textures and unhealthy replace claims."""
        findings: list[DiagnosticFinding] = []
        mods_x64e = root / constants.MODS_FOLDER_NAME / constants.VEHICLE_STREAM_ARCHIVE
        bad = find_bad_vehicle_stream_entries(mods_x64e)
        if bad:
            members = tuple(item.member_path for item in bad)
            short = ", ".join(Path(item.member_path).name for item in bad)
            evidence = "; ".join(
                f"{Path(item.member_path).name} ({item.entry_type}: {item.reason})"
                for item in bad
            )
            findings.append(
                DiagnosticFinding(
                    code="mods.bad_vehicle_stream",
                    severity=DiagnosticSeverity.ERROR,
                    title=f"Broken vehicle stream entries: {short}",
                    detail=(
                        "In mods/x64e.rpf → levels/gta5/vehicles.rpf, one or more .yft/.ytd "
                        "files are stored as binary entries instead of resources (or the body "
                        "looks like RSC7 while typed as binary). This is a known failure after "
                        "a bad replace/uninstall (e.g. gauntlet, baller, f620) and triggers "
                        "ERR_SYS_INVALIDRESOURCE_5."
                    ),
                    fix=(
                        "Restore the listed stock members from the original game x64e.rpf "
                        "into the mods copy. Use Repair selected — originals stay read-only."
                    ),
                    evidence=evidence,
                    category="vehicles",
                    fix_action=FIX_RESTORE_VEHICLE_STREAM,
                    fix_targets=members,
                )
            )

        unhealthy = find_unhealthy_replace_members(mods_x64e, installed)
        # Avoid duplicating members already covered by the stream scan.
        covered = {item.member_path.replace("\\", "/").lower() for item in bad}
        extra = [
            item
            for item in unhealthy
            if item.member_path.replace("\\", "/").lower() not in covered
        ]
        if extra:
            members = tuple(item.member_path for item in extra)
            short = ", ".join(
                f"{item.display_name}:{Path(item.member_path).name}" for item in extra
            )
            evidence = "; ".join(
                f"{item.display_name} → {item.member_path} ({item.reason})"
                for item in extra
            )
            # Missing / corrupt vehicle stream members can be restored from stock.
            restorable = tuple(
                dict.fromkeys(
                    item.member_path
                    for item in extra
                    if Path(item.member_path).suffix.lower()
                    in constants.VEHICLE_STREAM_EXTENSIONS
                    and item.member_path.replace("\\", "/")
                    .lower()
                    .startswith(constants.VEHICLE_STREAM_NESTED_RPF.lower() + "/")
                )
            )
            findings.append(
                DiagnosticFinding(
                    code="mods.replace_members_unhealthy",
                    severity=DiagnosticSeverity.WARNING,
                    title=f"Installed replace assets look unhealthy: {short}",
                    detail=(
                        "One or more library-tracked replace vehicle members are missing "
                        "from mods/x64e.rpf or are no longer valid resource entries."
                    ),
                    fix=(
                        "Restore stock members for the listed paths, or uninstall/reinstall "
                        "the affected replace mod."
                    ),
                    evidence=evidence,
                    category="vehicles",
                    fix_action=FIX_RESTORE_VEHICLE_STREAM if restorable else "",
                    fix_targets=restorable,
                )
            )
        return findings

    def _scan_commandline(self, root: Path) -> list[DiagnosticFinding]:
        """Note useful launch flags."""
        path = root / "commandline.txt"
        args = root / "args.txt"
        findings: list[DiagnosticFinding] = []
        for candidate in (path, args):
            if not candidate.is_file():
                continue
            try:
                text = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            findings.append(
                DiagnosticFinding(
                    code=f"launch.{candidate.stem}",
                    severity=DiagnosticSeverity.INFO,
                    title=f"{candidate.name} is set",
                    detail=text.strip()[:300] or "(empty)",
                    fix="For ERR_GFX_D3D_INIT try adding: -windowed -width 1280 -height 720",
                    category="launch",
                    evidence=str(candidate),
                )
            )
        return findings


def _severity(value: str) -> DiagnosticSeverity:
    try:
        return DiagnosticSeverity(value)
    except ValueError:
        return DiagnosticSeverity.WARNING


def _snippet_around(text: str, needle: str, radius: int = 80) -> str:
    """Return a short excerpt around the first match of ``needle``."""
    lowered = text.lower()
    index = lowered.find(needle.lower())
    if index < 0:
        return ""
    start = max(0, index - radius)
    end = min(len(text), index + len(needle) + radius)
    chunk = " ".join(text[start:end].split())
    return chunk[:200]
