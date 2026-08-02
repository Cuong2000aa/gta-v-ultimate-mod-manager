"""Builds the install plan for a GTA V mod package."""

from __future__ import annotations

import uuid
from pathlib import Path, PurePosixPath

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.enums import FileAction, InstallTarget, ModKind
from gta_mod_manager.models.install_plan import (
    ArchiveMemberImport,
    FileOperation,
    InstallPlan,
    ManualStep,
)
from gta_mod_manager.models.mod_file import ModFile
from gta_mod_manager.plugins.contracts import PlanRequest, TargetDecision
from gta_mod_manager.plugins.gta_v.layout import PackageLayout
from gta_mod_manager.plugins.gta_v.oiv_package import OivPackageParser
from gta_mod_manager.plugins.gta_v.path_mapper import (
    GtaVPathMapper,
    path_looks_like_backup_folder,
)

_LOGGER = get_logger("plugins.gta_v.plan")

#: Folder inside the application library that holds OpenIV-only payloads.
OPENIV_PAYLOAD_DIR = "openiv-payload"


class GtaVPlanBuilder:
    """Turns an analysed package into a reviewable list of file operations."""

    def __init__(
        self,
        mapper: GtaVPathMapper | None = None,
        oiv_parser: OivPackageParser | None = None,
    ) -> None:
        self._mapper = mapper or GtaVPathMapper()
        self._oiv_parser = oiv_parser or OivPackageParser()

    def build(self, request: PlanRequest) -> InstallPlan:
        """Return the plan that installs ``request.package`` safely."""
        package = request.package
        layout = PackageLayout.detect(
            package.inventory, package.display_name, selection=request.variants
        )
        oiv = self._oiv_parser.try_parse(package.inventory)

        operations: list[FileOperation] = []
        manual_steps: list[ManualStep] = []
        notes: list[str] = []
        archive_only: list[ModFile] = []
        archive_imports: list[tuple[ModFile, TargetDecision]] = []
        skipped_root = 0

        operations.extend(self._directory_operations(request, layout))

        if oiv is not None:
            oiv_ops, oiv_steps, oiv_notes, oiv_skipped = self._oiv_operations(request, oiv)
            operations.extend(oiv_ops)
            manual_steps.extend(oiv_steps)
            notes.extend(oiv_notes)
            skipped_root += oiv_skipped

        for file in package.files:
            if oiv is not None and self._is_oiv_internal(file, oiv):
                continue
            relative = PurePosixPath(file.relative_path.as_posix())
            if layout.is_skipped_variant_path(relative):
                continue
            decision = self._mapper.decide(layout, relative)
            if decision.is_archive_import:
                archive_imports.append((file, decision))
                continue
            if decision.target is None:
                if decision.needs_archive_editor:
                    archive_only.append(file)
                continue
            leaves_mods_folder = decision.target not in (
                InstallTarget.MODS_FOLDER,
                InstallTarget.DLC_PACKS,
            )
            if leaves_mods_folder and not request.allow_root_install:
                skipped_root += 1
                continue
            operation = self._file_operation(request, file, decision)
            if operation is not None:
                operations.append(operation)

        archive_ops, restore_notes = self._archive_import_operations(
            request, archive_imports
        )
        operations.extend(archive_ops)
        notes.extend(restore_notes)

        if archive_only:
            ped_ops, staged, steps = self._stage_archive_payload(
                request, archive_only, layout
            )
            operations.extend(ped_ops)
            operations.extend(staged)
            manual_steps.extend(steps)

        operations.extend(self._dlc_registration_operations(request, layout))
        operations.extend(self._addon_peds_dlc_registration(request, operations))
        notes.extend(self._notes(package, layout, skipped_root, archive_imports))

        plan = InstallPlan(
            plan_id=uuid.uuid4().hex[:12],
            package_id=package.package_id,
            display_name=package.display_name,
            game_root=request.install.root_path,
            operations=tuple(operations),
            notes=tuple(notes),
            manual_steps=tuple(manual_steps),
            requires_openiv=bool(manual_steps),
        )
        _LOGGER.info(
            "Built plan for %s: %d operation(s), %d manual step(s)",
            package.display_name,
            len(plan.operations),
            len(plan.manual_steps),
        )
        return plan

    # ------------------------------------------------------------------
    # Operation construction
    # ------------------------------------------------------------------
    def _file_operation(
        self, request: PlanRequest, file: ModFile, decision: TargetDecision
    ) -> FileOperation | None:
        """Return the copy/overwrite operation for one file."""
        if decision.relative_target is None:  # pragma: no cover - mapper guarantees this
            return None
        zone_root = self._zone_root(request, decision.target)
        target = zone_root / decision.relative_target

        if target.exists() and not request.overwrite_existing:
            return None

        action = FileAction.OVERWRITE if target.is_file() else FileAction.COPY
        return FileOperation(
            action=action,
            target_path=target,
            source_path=file.absolute_path,
            target_kind=decision.target or InstallTarget.MODS_FOLDER,
            description=decision.reason,
        )

    def _archive_import_operations(
        self,
        request: PlanRequest,
        imports: list[tuple[ModFile, TargetDecision]],
    ) -> tuple[tuple[FileOperation, ...], tuple[str, ...]]:
        """Build RPF_COPY + batched RPF_IMPORT operations for auto-replace."""
        if not imports:
            return (), ()

        # Deduplicate by member path; prefer Replace/ over Backup/original/stock.
        chosen: dict[tuple[Path, str], tuple[ModFile, TargetDecision, int]] = {}
        for file, decision in imports:
            if decision.relative_target is None or decision.archive_member_path is None:
                continue  # pragma: no cover
            archive = request.install.mods_path / decision.relative_target
            key = (archive, decision.archive_member_path.replace("\\", "/").lower())
            score = _stream_source_preference(file.relative_path)
            previous = chosen.get(key)
            if previous is None or score > previous[2]:
                chosen[key] = (file, decision, score)

        by_archive: dict[Path, list[ArchiveMemberImport]] = {}
        descriptions: dict[Path, str] = {}
        for (archive, _member), (file, decision, _score) in chosen.items():
            assert decision.archive_member_path is not None  # for type checkers
            by_archive.setdefault(archive, []).append(
                ArchiveMemberImport(
                    source_path=file.absolute_path,
                    member_path=decision.archive_member_path,
                )
            )
            descriptions.setdefault(archive, decision.reason)

        operations: list[FileOperation] = []
        restore_notes: list[str] = []
        # Preferred archive may be missing on modern installs (e.g. mpbusiness
        # folded into patchday). Retarget those members before emitting ops.
        resolved_archives: dict[Path, list[ArchiveMemberImport]] = {}
        for archive, members in by_archive.items():
            try:
                relative = archive.relative_to(request.install.mods_path)
            except ValueError:
                relative = Path(archive.name)
            original = request.install.root_path / relative
            if archive.is_file() or original.is_file():
                resolved_archives.setdefault(archive, []).extend(members)
                continue
            remapped, note = self._remap_imports_to_available_stock(
                request.install.root_path,
                request.install.mods_path,
                preferred=relative.as_posix(),
                members=members,
            )
            if note:
                restore_notes.append(note)
            for target_archive, remapped_members in remapped.items():
                resolved_archives.setdefault(target_archive, []).extend(remapped_members)

        for archive, members in resolved_archives.items():
            try:
                relative = archive.relative_to(request.install.mods_path)
            except ValueError:
                relative = Path(archive.name)
            original = request.install.root_path / relative
            if not archive.is_file():
                if not original.is_file():
                    _LOGGER.warning(
                        "Cannot auto-import into %s; original %s is missing",
                        relative.as_posix(),
                        original,
                    )
                    continue
                parent = archive.parent
                if not parent.is_dir():
                    try:
                        parent_label = parent.relative_to(request.install.mods_path).as_posix()
                    except ValueError:
                        parent_label = parent.name
                    operations.append(
                        FileOperation(
                            action=FileAction.CREATE_DIRECTORY,
                            target_path=parent,
                            target_kind=InstallTarget.MODS_FOLDER,
                            description=(
                                f"Create {constants.MODS_FOLDER_NAME}/{parent_label} "
                                "for the replace archive"
                            ),
                        )
                    )
                operations.append(
                    FileOperation(
                        action=FileAction.RPF_COPY,
                        target_path=archive,
                        source_path=original,
                        target_kind=InstallTarget.MODS_FOLDER,
                        description=(
                            f"Copy {relative.as_posix()} into {constants.MODS_FOLDER_NAME}/ "
                            "(original stays read-only)"
                        ),
                    )
                )
            operations.append(
                FileOperation(
                    action=FileAction.RPF_IMPORT,
                    target_path=archive,
                    target_kind=InstallTarget.MODS_FOLDER,
                    description=(
                        f"Import {len(members)} replace asset(s) into the mods copy of "
                        f"{relative.as_posix()}; original untouched"
                    ),
                    archive_members=tuple(members),
                )
            )
            restore_notes.extend(
                self._restore_safety_notes(
                    request.install.root_path, original, members
                )
            )
        return tuple(operations), tuple(restore_notes)

    @classmethod
    def _remap_imports_to_available_stock(
        cls,
        game_root: Path,
        mods_path: Path,
        *,
        preferred: str,
        members: list[ArchiveMemberImport],
    ) -> tuple[dict[Path, list[ArchiveMemberImport]], str]:
        """Retarget imports when the preferred DLC ``dlc.rpf`` is not on disk.

        Modern GTA V often ships Turismo R inside a late ``patchday*`` pack
        instead of legacy ``mpbusiness``. Fall back to that location, then to
        classic ``mods/x64e.rpf`` overrides.
        """
        from gta_mod_manager.plugins.gta_v.rpf_archive import resolve_stock_members

        remapped: dict[Path, list[ArchiveMemberImport]] = {}
        probe_root = game_root / constants.VEHICLE_STREAM_ARCHIVE
        used_sources: set[str] = set()
        for member in members:
            leaf = Path(member.member_path.replace("\\", "/")).name
            probes = (
                member.member_path.replace("\\", "/"),
                f"{constants.VEHICLE_STREAM_NESTED_RPF}/{leaf}",
                f"x64/{constants.VEHICLE_STREAM_NESTED_RPF}/{leaf}",
            )
            found = resolve_stock_members(probe_root, game_root, probes)
            source = next((found[path] for path in probes if path in found), None)
            if source is not None:
                try:
                    stock_relative = source.archive_path.resolve().relative_to(
                        game_root.resolve()
                    )
                except ValueError:
                    stock_relative = Path(source.archive_path.name)
                target_archive = mods_path / stock_relative
                nested = (source.nested_path or "").replace("\\", "/").strip("/")
                new_member = f"{nested}/{source.leaf}" if nested else source.leaf
                remapped.setdefault(target_archive, []).append(
                    ArchiveMemberImport(
                        source_path=member.source_path,
                        member_path=new_member,
                    )
                )
                used_sources.add(
                    f"{source.archive_path.parent.name}/{source.archive_path.name}"
                )
                continue

            # Last resort: OpenIV.asi override in mods/x64e.rpf.
            fallback = mods_path / constants.VEHICLE_STREAM_ARCHIVE
            remapped.setdefault(fallback, []).append(
                ArchiveMemberImport(
                    source_path=member.source_path,
                    member_path=f"{constants.VEHICLE_STREAM_NESTED_RPF}/{leaf}",
                )
            )
            used_sources.add(constants.VEHICLE_STREAM_ARCHIVE)

        _LOGGER.warning(
            "Preferred replace archive %s is missing; retargeted to %s",
            preferred,
            ", ".join(sorted(used_sources)) or "nowhere",
        )
        note = (
            f"Preferred archive {preferred} is not in this game install; "
            f"replace assets were retargeted to {', '.join(sorted(used_sources))}."
        )
        return remapped, note

    @staticmethod
    def _restore_safety_notes(
        game_root: Path,
        stock_archive: Path,
        members: list[ArchiveMemberImport],
    ) -> list[str]:
        """Warn when a replace import is not mirrored in stock x64e."""
        from gta_mod_manager.plugins.gta_v.rpf_archive import resolve_stock_members

        paths = tuple(member.member_path for member in members)
        if not paths or not stock_archive.is_file():
            return []
        mirrored = resolve_stock_members(
            stock_archive, game_root, paths, mirrored_only=True
        )
        outside = [path for path in paths if path not in mirrored]
        if not outside:
            return []
        # Confirm the vanilla model exists somewhere (patchday etc.) — read-only.
        alternate = resolve_stock_members(stock_archive, game_root, tuple(outside))
        names = ", ".join(sorted({Path(path).name for path in outside}))
        if alternate:
            sources = sorted(
                {
                    f"{source.archive_path.parent.name}/{source.archive_path.name}"
                    for source in alternate.values()
                }
            )
            return [
                f"Replace targets {names} are not in stock {stock_archive.name}; "
                f"vanilla lives in {', '.join(sources)}. Install is allowed; "
                "uninstall will remove these members from the mods copy so the "
                "game falls through to DLC (not a byte-perfect x64e restore). "
                "100% crash-proof replace installs are not guaranteed."
            ]
        return [
            f"Replace targets {names} were not found in stock {stock_archive.name} "
            "or patchday vehicle archives. Install is allowed, but uninstall can "
            "only delete the override from the mods copy. Prefer Add-On packs for "
            "non-vanilla models. 100% crash-proof installs are not guaranteed."
        ]

    @staticmethod
    def _zone_root(request: PlanRequest, target: InstallTarget | None) -> Path:
        """Return the base folder of an install zone."""
        install = request.install
        if target in (InstallTarget.MODS_FOLDER, InstallTarget.DLC_PACKS):
            return install.mods_path
        if target is InstallTarget.EXTERNAL:
            return request.paths.library
        return install.root_path

    def _directory_operations(
        self, request: PlanRequest, layout: PackageLayout
    ) -> tuple[FileOperation, ...]:
        """Return the directory creations the plan needs up front."""
        required: list[Path] = [request.install.mods_path]
        if layout.active_dlc_packs:
            required.append(request.install.dlc_packs_path)

        return tuple(
            FileOperation(
                action=FileAction.CREATE_DIRECTORY,
                target_path=directory,
                target_kind=InstallTarget.MODS_FOLDER,
                description="Create the safe installation folder",
            )
            for directory in required
            if not directory.is_dir()
        )

    def _stage_archive_payload(
        self, request: PlanRequest, files: list[ModFile], layout: PackageLayout
    ) -> tuple[tuple[FileOperation, ...], tuple[FileOperation, ...], tuple[ManualStep, ...]]:
        """Install ped models automatically; stage anything else for OpenIV.

        Ped ``.ydd``/``.yft``/``.ymt``/``.ytd`` sets are written into the
        manager-owned ``umm_peds`` DLC pack (the native replacement for
        AddonPeds Rebuild). Remaining archive-only assets are still staged
        outside the game with a manual OpenIV step.
        """
        ped_paths = {
            file.relative_path
            for file in files
            if layout.is_ped_asset(PurePosixPath(file.relative_path.as_posix()))
        }
        ped_files = [file for file in files if file.relative_path in ped_paths]
        other_files = [file for file in files if file.relative_path not in ped_paths]

        ped_ops = self._ped_import_operations(request, ped_files)

        staging_root = request.paths.library / request.package.package_id / OPENIV_PAYLOAD_DIR
        staged = tuple(
            FileOperation(
                action=FileAction.COPY,
                target_path=staging_root / Path(*file.relative_path.parts),
                source_path=file.absolute_path,
                target_kind=InstallTarget.EXTERNAL,
                description="Staged for manual import with OpenIV",
            )
            for file in other_files
        )

        steps: list[ManualStep] = []
        if other_files:
            steps.append(
                ManualStep(
                    title=f"Import {len(other_files)} file(s) with OpenIV",
                    instruction=(
                        "These files belong inside a game archive that this manager "
                        "cannot edit automatically. Open OpenIV in edit mode, navigate "
                        f"to the matching '{constants.MODS_FOLDER_NAME}' archive and "
                        "drag the staged files in."
                    ),
                    payload_path=staging_root,
                    target_hint=(
                        f"{constants.MODS_FOLDER_NAME}/update/update.rpf "
                        "or the matching .rpf"
                    ),
                )
            )
        return ped_ops, staged, tuple(steps)

    def _ped_import_operations(
        self, request: PlanRequest, files: list[ModFile]
    ) -> tuple[FileOperation, ...]:
        """Build the operations that install character models into ``umm_peds``."""
        if not files:
            return ()

        pack_dir = (
            request.install.mods_path
            / Path(*constants.DLC_PACKS_RELATIVE.split("/"))
            / constants.ADDON_PEDS_PACK_NAME
        )
        dlc_path = pack_dir / "dlc.rpf"
        members = tuple(
            ArchiveMemberImport(
                source_path=file.absolute_path,
                member_path=(
                    f"{constants.ADDON_PEDS_STREAM_ARCHIVE}/"
                    f"{PurePosixPath(file.relative_path.as_posix()).name}"
                ),
            )
            for file in files
        )
        operations: list[FileOperation] = []
        if not pack_dir.is_dir():
            operations.append(
                FileOperation(
                    action=FileAction.CREATE_DIRECTORY,
                    target_path=pack_dir,
                    target_kind=InstallTarget.DLC_PACKS,
                    description=(
                        f"Create {constants.MODS_FOLDER_NAME}/"
                        f"{constants.DLC_PACKS_RELATIVE}/{constants.ADDON_PEDS_PACK_NAME}"
                    ),
                )
            )
        operations.append(
            FileOperation(
                action=FileAction.RPF_PED_IMPORT,
                target_path=dlc_path,
                target_kind=InstallTarget.DLC_PACKS,
                description=(
                    f"Import {len(files)} character model file(s) into "
                    f"{constants.ADDON_PEDS_PACK_NAME}/dlc.rpf "
                    f"(auto add-on ped; no AddonPeds Rebuild)"
                ),
                archive_members=members,
            )
        )
        return tuple(operations)

    def _addon_peds_dlc_registration(
        self, request: PlanRequest, operations: list[FileOperation]
    ) -> tuple[FileOperation, ...]:
        """Register ``umm_peds`` in dlclist when this plan imports ped models."""
        if not any(op.action is FileAction.RPF_PED_IMPORT for op in operations):
            return ()
        from gta_mod_manager.plugins.gta_v.layout import DlcPackLayout, PackageLayout

        layout = PackageLayout(
            dlc_packs=(
                DlcPackLayout(
                    pack_name=constants.ADDON_PEDS_PACK_NAME,
                    root=PurePosixPath(constants.ADDON_PEDS_PACK_NAME),
                ),
            )
        )
        return self._dlc_registration_operations(request, layout)

    @staticmethod
    def _ped_manual_step(files: list[ModFile], staging_root: Path) -> ManualStep:
        """Describe how to import character models, which archive varies per ped."""
        models = sorted({PurePosixPath(file.relative_path.as_posix()).stem for file in files})
        listed = ", ".join(models[:6]) + (", ..." if len(models) > 6 else "")
        return ManualStep(
            title=f"Import {len(files)} character (ped) file(s) with OpenIV",
            instruction=(
                "Character models were kept out of the vehicle archive on purpose: "
                "every ped lives in a different archive, so the manager will not "
                "guess one. Open OpenIV in edit mode, press Ctrl+F and search for the "
                f"model name ({listed}) to find where the original is stored, then "
                f"drag the staged files into the '{constants.MODS_FOLDER_NAME}' copy "
                "of that archive."
            ),
            payload_path=staging_root,
            target_hint=(
                f"{constants.MODS_FOLDER_NAME}/x64*.rpf → models/cdimages/... "
                "(search the model name in OpenIV)"
            ),
        )

    def _dlc_registration_operations(
        self, request: PlanRequest, layout: PackageLayout
    ) -> tuple[FileOperation, ...]:
        """Copy mods ``update.rpf`` if needed and register add-on packs in dlclist."""
        packs = layout.active_dlc_packs
        if not packs:
            return ()

        pack_names = tuple(pack.pack_name for pack in packs)
        mods_archive = request.install.mods_path.joinpath(
            *constants.UPDATE_ARCHIVE_RELATIVE.split("/")
        )
        stock_archive = request.install.root_path.joinpath(
            *constants.UPDATE_ARCHIVE_RELATIVE.split("/")
        )
        operations: list[FileOperation] = []

        update_dir = mods_archive.parent
        if not update_dir.is_dir():
            operations.append(
                FileOperation(
                    action=FileAction.CREATE_DIRECTORY,
                    target_path=update_dir,
                    target_kind=InstallTarget.MODS_FOLDER,
                    description="Create mods/update for the dlclist archive",
                )
            )

        if not mods_archive.is_file():
            if not stock_archive.is_file():
                _LOGGER.warning(
                    "Cannot auto-register DLC packs; stock %s is missing",
                    stock_archive,
                )
                return ()
            operations.append(
                FileOperation(
                    action=FileAction.RPF_COPY,
                    target_path=mods_archive,
                    source_path=stock_archive,
                    target_kind=InstallTarget.MODS_FOLDER,
                    description=(
                        f"Copy {constants.UPDATE_ARCHIVE_RELATIVE} into "
                        f"{constants.MODS_FOLDER_NAME}/ (original stays read-only)"
                    ),
                )
            )

        operations.append(
            FileOperation(
                action=FileAction.RPF_DLC_REGISTER,
                target_path=mods_archive,
                target_kind=InstallTarget.MODS_FOLDER,
                payload="\n".join(pack_names),
                description=(
                    f"Register DLC pack(s) in dlclist.xml: {', '.join(pack_names)}"
                ),
            )
        )
        return tuple(operations)

    def _notes(
        self,
        package: object,
        layout: PackageLayout,
        skipped_root: int,
        archive_imports: list[tuple[ModFile, TargetDecision]],
    ) -> tuple[str, ...]:
        """Return informational notes shown in the preview dialog."""
        notes: list[str] = []
        classification = getattr(package, "classification", None)
        if classification is not None:
            notes.append(
                f"Detected as {classification.primary.display_name} "
                f"({classification.score:.0%} confidence)"
            )
            if classification.primary is ModKind.UNKNOWN:
                notes.append(
                    "The category could not be determined; review the file list carefully."
                )
            if "gameconfig" in classification.tags:
                notes.append(
                    "This package replaces gameconfig.xml, which conflicts with every "
                    "other gameconfig mod."
                )
        if layout.ped_model_names:
            names = ", ".join(sorted(layout.ped_model_names)[:6])
            notes.append(
                f"Character model(s) detected ({names}). They will be installed "
                f"automatically into mods/.../dlcpacks/{constants.ADDON_PEDS_PACK_NAME}/ "
                "(no AddonPeds Rebuild required)."
            )
        if layout.is_dual_variant:
            chosen: list[str] = []
            if layout.selection.addon:
                chosen.append("Add-On")
            if layout.selection.replace:
                chosen.append("Replace")
            if not chosen:
                notes.append(
                    "Package ships both Add-On and Replace. Choose at least one "
                    "before installing."
                )
            else:
                notes.append(
                    "Package ships both Add-On and Replace; installing: "
                    + " + ".join(chosen)
                    + "."
                )
            if layout.prefer_legacy_edition:
                notes.append(
                    "Enhanced and Legacy folders both present; Legacy is used "
                    "and Enhanced is skipped."
                )
        if layout.active_dlc_packs:
            names = ", ".join(pack.pack_name for pack in layout.active_dlc_packs)
            notes.append(
                f"Add-on DLC pack(s): {names}. "
                "dlclist.xml in mods/update/update.rpf will be updated automatically."
            )
        if archive_imports:
            notes.append(
                f"{len(archive_imports)} vehicle stream asset(s) will be written into the "
                f"mods copy of {constants.VEHICLE_STREAM_ARCHIVE} (original untouched). "
                "Requires OpenIV.asi."
            )
        if skipped_root:
            notes.append(
                f"{skipped_root} file(s) were skipped because root installation is disabled."
            )
        return tuple(notes)

    # ------------------------------------------------------------------
    # OpenIV (.oiv) package handling
    # ------------------------------------------------------------------
    def _oiv_operations(
        self, request: PlanRequest, oiv: object
    ) -> tuple[tuple[FileOperation, ...], tuple[ManualStep, ...], tuple[str, ...], int]:
        """Turn an OIV descriptor's ``<add>`` commands into copy / RPF imports.

        Loose destinations under the root whitelist still copy natively. OpenIV
        virtual roots (``/common/data``, ``/dlc_patch/...``) are imported into
        the matching ``mods/*.rpf`` archive. Remaining archive-only commands
        become a single manual step.
        """
        from gta_mod_manager.plugins.gta_v.oiv_package import OivPackage
        from gta_mod_manager.plugins.gta_v.oiv_targets import resolve_openiv_virtual_path

        assert isinstance(oiv, OivPackage)
        content_root = oiv.content_root
        if content_root is None:
            return (), (), (), 0

        operations: list[FileOperation] = []
        missing: list[str] = []
        not_whitelisted: list[str] = []
        skipped_root = 0
        skipped_dlc_patch = 0
        imports_by_archive: dict[Path, list[ArchiveMemberImport]] = {}

        for command in oiv.installable_commands:
            if command.source is None:
                continue  # pragma: no cover - installable implies a source
            source = content_root / Path(*command.source.parts)
            if not source.is_file():
                missing.append(command.source.as_posix())
                continue
            destination = command.destination
            parts = [part for part in destination.parts if part and part != "/"]
            relative_dest = PurePosixPath(*parts) if parts else PurePosixPath()
            first = parts[0].lower() if parts else ""

            if first == constants.MODS_FOLDER_NAME:
                target = request.install.root_path / Path(*parts)
                if target.exists() and not request.overwrite_existing:
                    continue
                action = FileAction.OVERWRITE if target.is_file() else FileAction.COPY
                operations.append(
                    FileOperation(
                        action=action,
                        target_path=target,
                        source_path=source,
                        target_kind=InstallTarget.MODS_FOLDER,
                        description=(
                            f"OpenIV package '{oiv.display_name}': install "
                            f"{relative_dest.as_posix()}"
                        ),
                    )
                )
                continue

            verdict = self._mapper.policy.evaluate(relative_dest)
            if verdict.allowed:
                if not request.allow_root_install:
                    skipped_root += 1
                    continue
                target = request.install.root_path / Path(*parts)
                if target.exists() and not request.overwrite_existing:
                    continue
                target_kind = verdict.target or InstallTarget.GAME_ROOT
                action = FileAction.OVERWRITE if target.is_file() else FileAction.COPY
                operations.append(
                    FileOperation(
                        action=action,
                        target_path=target,
                        source_path=source,
                        target_kind=target_kind,
                        description=(
                            f"OpenIV package '{oiv.display_name}': install "
                            f"{relative_dest.as_posix()}"
                        ),
                    )
                )
                continue

            mapped = resolve_openiv_virtual_path(destination)
            if mapped is None:
                not_whitelisted.append(destination.as_posix())
                continue
            if mapped.is_dlc_patch:
                # Mirroring every Rockstar DLC pack is huge; only patch packs
                # that already have a mods copy (user already touched them).
                mods_archive = request.install.mods_path / mapped.relative_archive
                if not mods_archive.is_file():
                    skipped_dlc_patch += 1
                    continue
            imports_by_archive.setdefault(
                request.install.mods_path / mapped.relative_archive, []
            ).append(
                ArchiveMemberImport(
                    source_path=source,
                    member_path=mapped.member_path,
                )
            )

        for archive, members in sorted(
            imports_by_archive.items(), key=lambda item: str(item[0]).lower()
        ):
            relative = archive.relative_to(request.install.mods_path)
            original = request.install.root_path / relative
            if not archive.is_file():
                parent = archive.parent
                if not parent.is_dir():
                    operations.append(
                        FileOperation(
                            action=FileAction.CREATE_DIRECTORY,
                            target_path=parent,
                            target_kind=InstallTarget.MODS_FOLDER,
                            description=(
                                f"Create {constants.MODS_FOLDER_NAME}/"
                                f"{parent.relative_to(request.install.mods_path).as_posix()}"
                            ),
                        )
                    )
                operations.append(
                    FileOperation(
                        action=FileAction.RPF_COPY,
                        target_path=archive,
                        source_path=original,
                        target_kind=InstallTarget.MODS_FOLDER,
                        description=(
                            f"Copy {relative.as_posix()} into {constants.MODS_FOLDER_NAME}/ "
                            "(original stays read-only)"
                        ),
                    )
                )
            operations.append(
                FileOperation(
                    action=FileAction.RPF_IMPORT,
                    target_path=archive,
                    target_kind=InstallTarget.MODS_FOLDER,
                    description=(
                        f"OpenIV package '{oiv.display_name}': import {len(members)} "
                        f"file(s) into mods/{relative.as_posix()}"
                    ),
                    archive_members=tuple(members),
                )
            )

        steps: list[ManualStep] = []
        if oiv.archive_commands:
            steps.append(self._oiv_archive_step(oiv))

        notes: list[str] = []
        if operations:
            notes.append(
                f"OpenIV package '{oiv.display_name}': {len(operations)} operation(s) "
                "prepared (game root / scripts / mods RPF imports)."
            )
        if missing:
            preview = ", ".join(missing[:4]) + (", ..." if len(missing) > 4 else "")
            notes.append(
                f"OpenIV package '{oiv.display_name}': {len(missing)} declared file(s) "
                f"were missing from the package and skipped ({preview})."
            )
        if skipped_dlc_patch:
            notes.append(
                f"OpenIV package '{oiv.display_name}': skipped {skipped_dlc_patch} DLC "
                "handling patch(es) for packs not already mirrored under mods/ "
                "(base-game handling still installs). For full DLC coverage, run "
                "Install.oiv once in OpenIV Package Installer."
            )
        if not_whitelisted:
            preview = ", ".join(not_whitelisted[:4]) + (
                ", ..." if len(not_whitelisted) > 4 else ""
            )
            notes.append(
                f"OpenIV package '{oiv.display_name}': {len(not_whitelisted)} file(s) "
                f"were skipped because they are not on the root whitelist ({preview})."
            )
        return tuple(operations), tuple(steps), tuple(notes), skipped_root

    @staticmethod
    def _oiv_archive_step(oiv: object) -> ManualStep:
        """Describe the OIV commands that still require OpenIV itself."""
        from gta_mod_manager.plugins.gta_v.oiv_package import OivPackage

        assert isinstance(oiv, OivPackage)
        targets = sorted({command.destination.as_posix() for command in oiv.archive_commands})
        listed = "\n".join(f"  - {target}" for target in targets[:12])
        more = "\n  - ..." if len(targets) > 12 else ""
        return ManualStep(
            title=(
                f"OpenIV package '{oiv.display_name}': {len(oiv.archive_commands)} "
                "command(s) need OpenIV"
            ),
            instruction=(
                "These commands write inside .rpf archives, which this manager never "
                "edits automatically. Install the .oiv with OpenIV (Tools > Package "
                "installer) and choose the 'mods' folder, or import the listed targets "
                f"by hand:\n{listed}{more}"
            ),
            target_hint=f"{constants.MODS_FOLDER_NAME}/... (via OpenIV Package installer)",
        )

    @staticmethod
    def _is_oiv_internal(file: ModFile, oiv: object) -> bool:
        """Return whether ``file`` is OIV metadata or packaged content.

        Descriptor, ``icon.png`` and everything under ``content/`` are package
        internals: they are either applied through :meth:`_oiv_operations` or are
        payloads for OpenIV, so they must not be routed as loose files.
        """
        from gta_mod_manager.plugins.gta_v.oiv_package import OivPackage

        assert isinstance(oiv, OivPackage)
        absolute = file.absolute_path
        if absolute == oiv.descriptor:
            return True
        descriptor_dir = oiv.descriptor.parent
        if file.relative_path.name.lower() == "icon.png" and absolute.parent == descriptor_dir:
            return True
        content_root = oiv.content_root
        return content_root is not None and absolute.is_relative_to(content_root)


def _stream_source_preference(relative_path: PurePosixPath) -> int:
    """Higher score wins when multiple package files map to the same RPF member.

    Prefer ``Replace/`` trees over ambiguous roots, and never prefer backup folders
    (those should already be skipped by the path mapper).
    """
    if path_looks_like_backup_folder(relative_path):
        return -100
    lowered = [part.lower() for part in relative_path.parts[:-1]]
    if any(part in {"replace", "replacement", "replacements"} for part in lowered):
        return 100
    if any(part in {"addon", "add-on", "add_on"} for part in lowered):
        return 10
    return 50
