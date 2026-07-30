"""Base contract for analyzer rules and the hit objects they produce."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable

from gta_mod_manager.analyzer.context import AnalysisContext
from gta_mod_manager.models.enums import ModKind


@dataclass(frozen=True, slots=True)
class RuleHit:
    """A rule's vote for one category.

    Attributes:
        kind: Category the rule votes for.
        weight: Strength of the vote in ``[-1, 1]``; negative votes veto.
        reason: Short explanation surfaced in the preview dialog.
        tags: Extra labels attached to the final classification.
        rule_id: Stamped by the engine so evidence can be traced back.
    """

    kind: ModKind
    weight: float
    reason: str
    tags: frozenset[str] = frozenset()
    rule_id: str = ""

    def stamped(self, rule_id: str) -> "RuleHit":
        """Return a copy of this hit attributed to ``rule_id``."""
        return RuleHit(
            kind=self.kind,
            weight=self.weight,
            reason=self.reason,
            tags=self.tags,
            rule_id=rule_id,
        )


class AnalyzerRule(ABC):
    """One independent classification heuristic.

    Rules are pure functions of an :class:`AnalysisContext`, which makes each
    of them trivially unit-testable with a synthetic inventory.
    """

    #: Stable identifier used in evidence and log output.
    rule_id: str = "rule"

    #: Human readable name shown in the analysis report.
    display_name: str = "Rule"

    @abstractmethod
    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return the votes this rule casts for ``context``."""


class KeywordRule(AnalyzerRule):
    """Votes for a category when known keywords appear in the package paths.

    Naming is a weak but broad signal, so keyword rules deliberately use small
    weights and only ever reinforce a structural rule's verdict.
    """

    #: Keywords that trigger this rule.
    keywords: tuple[str, ...] = ()

    #: Category the keywords point at.
    kind: ModKind = ModKind.UNKNOWN

    #: Weight applied for the first match.
    base_weight: float = 0.2

    def evaluate(self, context: AnalysisContext) -> Iterable[RuleHit]:
        """Return one hit when at least one keyword matched."""
        matched = context.matched_keywords(self.keywords)
        if not matched:
            return ()
        weight = min(0.6, self.base_weight * len(matched))
        return (
            RuleHit(
                kind=self.kind,
                weight=weight,
                reason=f"Name mentions {', '.join(matched[:3])}",
            ),
        )
