"""Runs every conflict rule and aggregates a report."""

from __future__ import annotations

from collections.abc import Iterable

from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.installer.conflict_rules import (
    ConflictContext,
    ConflictRule,
    default_conflict_rules,
)
from gta_mod_manager.models.conflict import Conflict, ConflictReport
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.install_plan import InstallPlan
from gta_mod_manager.models.mod_package import InstalledMod, ModPackage

_LOGGER = get_logger("installer.conflicts")


class ConflictDetector:
    """Compares a plan with the current game state and the mod library."""

    def __init__(self, rules: tuple[ConflictRule, ...] | None = None) -> None:
        self._rules = rules if rules is not None else default_conflict_rules()

    def detect(
        self,
        plan: InstallPlan,
        install: GameInstall,
        installed: Iterable[InstalledMod] = (),
        package: ModPackage | None = None,
    ) -> ConflictReport:
        """Return every conflict the plan would cause."""
        context = ConflictContext(
            plan=plan,
            install=install,
            package=package,
            installed=tuple(installed),
        )
        collected: list[Conflict] = []
        for rule in self._rules:
            try:
                collected.extend(rule.evaluate(context))
            except Exception as error:  # noqa: BLE001 - one rule must not hide the others
                _LOGGER.warning("Conflict rule %s failed: %s", rule.rule_id, error)

        report = ConflictReport(conflicts=tuple(collected))
        _LOGGER.info(
            "Conflict scan for %s: %d total, %d blocking",
            plan.display_name,
            len(report.conflicts),
            len(report.blocking),
        )
        return report
