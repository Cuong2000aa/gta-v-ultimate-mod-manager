"""The smart mod analyzer: runs every rule and aggregates the verdict."""

from __future__ import annotations

from dataclasses import dataclass, field

from gta_mod_manager.analyzer import scoring
from gta_mod_manager.analyzer.context import AnalysisContext
from gta_mod_manager.analyzer.rule_base import AnalyzerRule, RuleHit
from gta_mod_manager.analyzer.rules import default_rules
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.classification import ModClassification
from gta_mod_manager.models.mod_file import FileInventory

_LOGGER = get_logger("analyzer.engine")


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """The classification plus the raw votes that produced it."""

    classification: ModClassification
    hits: tuple[RuleHit, ...] = field(default_factory=tuple)

    @property
    def tags(self) -> frozenset[str]:
        """Return the tags collected from every rule."""
        return self.classification.tags


class ModAnalyzer:
    """Classifies an extracted package by running independent rules.

    The analyzer never mutates anything and never guesses silently: an
    unconvincing verdict is reported as :attr:`ModKind.UNKNOWN` with a low
    score so the UI can ask the user instead of installing blindly.
    """

    def __init__(self, rules: tuple[AnalyzerRule, ...] | None = None) -> None:
        self._rules = rules if rules is not None else default_rules()

    @property
    def rules(self) -> tuple[AnalyzerRule, ...]:
        """Return the rule set in use."""
        return self._rules

    def analyze(self, inventory: FileInventory, source_name: str = "") -> ModClassification:
        """Return the classification of ``inventory``."""
        return self.analyze_detailed(inventory, source_name).classification

    def analyze_detailed(
        self, inventory: FileInventory, source_name: str = ""
    ) -> AnalysisResult:
        """Return the classification together with every rule vote."""
        context = AnalysisContext(inventory=inventory, source_name=source_name)
        hits = self._collect_hits(context)
        classification = scoring.combine(hits)
        _LOGGER.info(
            "Analyzed %s: %s (score %.2f, %d rule hit(s))",
            source_name or inventory.root.name,
            classification.primary.display_name,
            classification.score,
            len(hits),
        )
        return AnalysisResult(classification=classification, hits=hits)

    def _collect_hits(self, context: AnalysisContext) -> tuple[RuleHit, ...]:
        """Run every rule, stamping hits with their rule identifier."""
        collected: list[RuleHit] = []
        for rule in self._rules:
            try:
                votes = tuple(rule.evaluate(context))
            except Exception as error:  # noqa: BLE001 - a broken rule must not abort analysis
                _LOGGER.warning("Analyzer rule %s failed: %s", rule.rule_id, error)
                continue
            collected.extend(vote.stamped(rule.rule_id) for vote in votes)
        return tuple(collected)
