"""Deeper validation of an installation, beyond what detection checks."""

from __future__ import annotations

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.component import ComponentReport
from gta_mod_manager.models.game_install import GameInstall, ValidationIssue, ValidationReport
from gta_mod_manager.utils import fs

_LOGGER = get_logger("validator.game")

#: A ``mods`` folder without these mirrors is usually an incomplete setup.
_EXPECTED_MODS_MIRRORS: tuple[str, ...] = ("update", "x64a.rpf", "common.rpf")


class GameValidator:
    """Reports problems that would make installations unreliable."""

    def validate(
        self, install: GameInstall, components: ComponentReport | None = None
    ) -> ValidationReport:
        """Return warnings and fatal issues for ``install``."""
        issues: list[ValidationIssue] = []

        if install.executable is None:
            issues.append(
                ValidationIssue(
                    code="game.no_executable",
                    message=f"{constants.PRIMARY_EXECUTABLE} is missing",
                    is_fatal=True,
                    path=install.root_path,
                )
            )

        issues.extend(self._validate_mods_folder(install))
        if components is not None:
            issues.extend(self._validate_components(components))

        report = ValidationReport(issues=tuple(issues))
        _LOGGER.debug(
            "Validated %s: %d warning(s), %d fatal",
            install.root_path,
            len(report.warnings),
            len(report.fatal_issues),
        )
        return report

    @staticmethod
    def _validate_mods_folder(install: GameInstall) -> tuple[ValidationIssue, ...]:
        """Check the state of the ``mods`` folder."""
        mods = install.mods_path
        if not mods.is_dir():
            return (
                ValidationIssue(
                    code="mods.absent",
                    message="No 'mods' folder yet; it will be created on the first install",
                    path=mods,
                ),
            )

        missing = [name for name in _EXPECTED_MODS_MIRRORS if not (mods / name).exists()]
        if len(missing) == len(_EXPECTED_MODS_MIRRORS):
            return (
                ValidationIssue(
                    code="mods.empty",
                    message="The 'mods' folder is empty. Copy update.rpf, common.rpf and the "
                    "x64 archives into it with OpenIV before installing asset mods",
                    path=mods,
                ),
            )
        if missing:
            return (
                ValidationIssue(
                    code="mods.partial",
                    message="The 'mods' folder does not mirror: " + ", ".join(missing),
                    path=mods,
                ),
            )
        return ()

    @staticmethod
    def _validate_components(report: ComponentReport) -> tuple[ValidationIssue, ...]:
        """Turn missing essential components into validation warnings."""
        return tuple(
            ValidationIssue(
                code=f"component.missing.{component.component_id}",
                message=f"{component.display_name} is not installed "
                f"(needed by: {', '.join(component.spec.required_by) or 'core setup'})",
            )
            for component in report.missing_dependencies
        )

    @staticmethod
    def describe_disk_space(install: GameInstall) -> str:
        """Return a short human readable summary of the installation size."""
        return fs.human_size(fs.directory_size(install.mods_path))
