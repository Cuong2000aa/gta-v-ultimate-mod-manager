"""Turns independent rule votes into one confidence-scored classification.

Positive votes are combined with a *noisy-OR*: two weak signals reinforce each
other without ever exceeding ``1.0``. Negative votes (vetoes, such as "this
ships its own DLC pack so it cannot be a replacement") are applied afterwards
as a multiplicative penalty.
"""

from __future__ import annotations

from collections import defaultdict

from gta_mod_manager.analyzer.rule_base import RuleHit
from gta_mod_manager.models.classification import Evidence, KindScore, ModClassification
from gta_mod_manager.models.enums import ModKind

#: Categories that describe a container and should win over their content.
_CONTAINER_PRIORITY: tuple[ModKind, ...] = (ModKind.OPENIV_PACKAGE, ModKind.LML)

#: How much a container category must score to override a content category.
_CONTAINER_OVERRIDE_THRESHOLD = 0.7

#: Below this score the analyzer refuses to name a category.
_MINIMUM_ACCEPTED_SCORE = 0.2

#: Order used when two categories score exactly the same. Packages that ship
#: both an add-on and a replacement variant are common; Replace wins the tie
#: because it needs no ``dlclist`` registration and is the user's preference.
_TIE_BREAK_ORDER: tuple[ModKind, ...] = (
    ModKind.OPENIV_PACKAGE,
    ModKind.LML,
    ModKind.VEHICLE_REPLACE,
    ModKind.VEHICLE_ADDON,
)


def combine(hits: tuple[RuleHit, ...]) -> ModClassification:
    """Aggregate ``hits`` into a final :class:`ModClassification`.

    Args:
        hits: Every vote produced by the rule set.

    Returns:
        The classification, including per-category scores and evidence.
    """
    if not hits:
        return ModClassification.unknown()

    positive: dict[ModKind, list[RuleHit]] = defaultdict(list)
    negative: dict[ModKind, list[RuleHit]] = defaultdict(list)
    tags: set[str] = set()

    for hit in hits:
        tags.update(hit.tags)
        if hit.weight > 0:
            positive[hit.kind].append(hit)
        elif hit.weight < 0:
            negative[hit.kind].append(hit)

    scored: list[KindScore] = []
    for kind in sorted(set(positive) | set(negative), key=_tie_break_rank):
        if kind is ModKind.UNKNOWN:
            continue
        score = _noisy_or(positive.get(kind, ()))
        score *= _penalty(negative.get(kind, ()))
        evidence = tuple(
            Evidence(
                rule_id=hit.rule_id or "rule", description=hit.reason, weight=hit.weight
            )
            for hit in (*positive.get(kind, ()), *negative.get(kind, ()))
        )
        scored.append(KindScore(kind=kind, score=round(score, 4), evidence=evidence))

    if not scored:
        return ModClassification(primary=ModKind.UNKNOWN, score=0.0, tags=frozenset(tags))

    scored.sort(key=lambda item: (-item.score, _tie_break_rank(item.kind)))
    winner = _pick_winner(scored)

    if winner.score < _MINIMUM_ACCEPTED_SCORE:
        return ModClassification(
            primary=ModKind.UNKNOWN,
            score=winner.score,
            candidates=tuple(scored),
            tags=frozenset(tags),
        )

    return ModClassification(
        primary=winner.kind,
        score=winner.score,
        candidates=tuple(scored),
        tags=frozenset(tags),
    )


def _tie_break_rank(kind: ModKind) -> tuple[int, str]:
    """Return the ordering key that keeps equally scored verdicts stable.

    Without it the winner depends on set iteration order, so the very same
    package could be reported as add-on on one run and replacement on the next.
    """
    if kind in _TIE_BREAK_ORDER:
        return (_TIE_BREAK_ORDER.index(kind), kind.value)
    return (len(_TIE_BREAK_ORDER), kind.value)


def _noisy_or(hits: tuple[RuleHit, ...] | list[RuleHit]) -> float:
    """Combine positive weights so more evidence means more confidence."""
    remaining = 1.0
    for hit in hits:
        remaining *= 1.0 - min(1.0, hit.weight)
    return 1.0 - remaining


def _penalty(hits: tuple[RuleHit, ...] | list[RuleHit]) -> float:
    """Combine veto weights into a multiplicative penalty factor."""
    factor = 1.0
    for hit in hits:
        factor *= 1.0 - min(1.0, abs(hit.weight))
    return factor


def _pick_winner(scored: list[KindScore]) -> KindScore:
    """Return the winning category, honouring container priority.

    An ``.oiv`` package that happens to contain a vehicle must be installed
    using the OpenIV rules, not the vehicle rules, so a confident container
    verdict outranks a slightly higher content verdict.
    """
    best = scored[0]
    for candidate in scored:
        if (
            candidate.kind in _CONTAINER_PRIORITY
            and candidate.score >= _CONTAINER_OVERRIDE_THRESHOLD
        ):
            return candidate
    return best


def evidence_for(hits: tuple[RuleHit, ...], kind: ModKind) -> tuple[Evidence, ...]:
    """Return the evidence entries of ``hits`` that concern ``kind``."""
    return tuple(
        Evidence(rule_id=hit.rule_id or "rule", description=hit.reason, weight=hit.weight)
        for hit in hits
        if hit.kind is kind
    )
