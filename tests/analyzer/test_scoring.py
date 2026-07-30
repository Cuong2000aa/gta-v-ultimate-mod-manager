"""Tests for the confidence scoring that combines rule votes."""

from __future__ import annotations

from gta_mod_manager.analyzer import scoring
from gta_mod_manager.analyzer.rule_base import RuleHit
from gta_mod_manager.models.enums import ConfidenceLevel, ModKind


def test_no_votes_means_unknown() -> None:
    classification = scoring.combine(())

    assert classification.primary is ModKind.UNKNOWN
    assert classification.score == 0.0
    assert not classification.is_reliable


def test_two_weak_votes_reinforce_each_other() -> None:
    hits = (
        RuleHit(kind=ModKind.GRAPHICS, weight=0.4, reason="ENB files", rule_id="a"),
        RuleHit(kind=ModKind.GRAPHICS, weight=0.4, reason="preset ini", rule_id="b"),
    )

    classification = scoring.combine(hits)

    assert classification.primary is ModKind.GRAPHICS
    assert 0.6 < classification.score < 0.7


def test_scores_never_exceed_one() -> None:
    hits = tuple(
        RuleHit(kind=ModKind.MAP, weight=0.9, reason=f"signal {index}", rule_id=str(index))
        for index in range(5)
    )

    assert scoring.combine(hits).score <= 1.0


def test_a_veto_suppresses_a_category() -> None:
    hits = (
        RuleHit(kind=ModKind.VEHICLE_REPLACE, weight=0.8, reason="vehicles.meta", rule_id="a"),
        RuleHit(
            kind=ModKind.VEHICLE_REPLACE,
            weight=-0.9,
            reason="ships its own DLC pack",
            rule_id="b",
        ),
        RuleHit(kind=ModKind.VEHICLE_ADDON, weight=0.7, reason="setup2.xml", rule_id="c"),
    )

    classification = scoring.combine(hits)

    assert classification.primary is ModKind.VEHICLE_ADDON


def test_a_confident_container_outranks_its_content() -> None:
    hits = (
        RuleHit(kind=ModKind.VEHICLE_ADDON, weight=0.95, reason="vehicle pack", rule_id="a"),
        RuleHit(kind=ModKind.OPENIV_PACKAGE, weight=0.85, reason="assembly.xml", rule_id="b"),
    )

    assert scoring.combine(hits).primary is ModKind.OPENIV_PACKAGE


def test_a_weak_container_does_not_override() -> None:
    hits = (
        RuleHit(kind=ModKind.VEHICLE_ADDON, weight=0.9, reason="vehicle pack", rule_id="a"),
        RuleHit(kind=ModKind.OPENIV_PACKAGE, weight=0.3, reason="maybe oiv", rule_id="b"),
    )

    assert scoring.combine(hits).primary is ModKind.VEHICLE_ADDON


def test_a_verdict_below_the_noise_floor_stays_unknown() -> None:
    hits = (RuleHit(kind=ModKind.SOUND, weight=0.1, reason="one .awc", rule_id="a"),)

    classification = scoring.combine(hits)

    assert classification.primary is ModKind.UNKNOWN
    assert classification.candidates[0].kind is ModKind.SOUND


def test_tags_from_every_rule_are_collected() -> None:
    hits = (
        RuleHit(
            kind=ModKind.ASI,
            weight=0.8,
            reason="asi",
            tags=frozenset({"requires_asi_loader"}),
            rule_id="a",
        ),
        RuleHit(
            kind=ModKind.ASI,
            weight=0.2,
            reason="ini",
            tags=frozenset({"root_install"}),
            rule_id="b",
        ),
    )

    assert scoring.combine(hits).tags == frozenset({"requires_asi_loader", "root_install"})


def test_evidence_is_traceable_back_to_its_rule() -> None:
    hits = (RuleHit(kind=ModKind.SCRIPT, weight=0.7, reason="lua files", rule_id="script.lua"),)

    classification = scoring.combine(hits)

    assert classification.evidence[0].rule_id == "script.lua"
    assert classification.confidence is ConfidenceLevel.MEDIUM


def test_a_tie_always_resolves_the_same_way() -> None:
    """A package offering both routes must not change verdict between runs."""
    hits = (
        RuleHit(kind=ModKind.VEHICLE_REPLACE, weight=0.35, reason="replace folder", rule_id="a"),
        RuleHit(kind=ModKind.VEHICLE_ADDON, weight=0.35, reason="add-on folder", rule_id="b"),
    )

    verdicts = {scoring.combine(hits).primary for _ in range(10)}

    assert verdicts == {ModKind.VEHICLE_REPLACE}


def test_secondary_kinds_report_the_runner_ups() -> None:
    hits = (
        RuleHit(kind=ModKind.MAP, weight=0.9, reason="ymap", rule_id="a"),
        RuleHit(kind=ModKind.TEXTURE, weight=0.5, reason="ytd", rule_id="b"),
        RuleHit(kind=ModKind.SOUND, weight=0.1, reason="awc", rule_id="c"),
    )

    classification = scoring.combine(hits)

    assert classification.primary is ModKind.MAP
    assert classification.secondary_kinds == (ModKind.TEXTURE,)
