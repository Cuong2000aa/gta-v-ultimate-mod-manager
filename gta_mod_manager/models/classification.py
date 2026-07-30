"""Classification result produced by the smart mod analyzer."""

from __future__ import annotations

from dataclasses import dataclass, field

from gta_mod_manager.models.enums import ConfidenceLevel, ModKind


@dataclass(frozen=True, slots=True)
class Evidence:
    """A single observation that supports (or weakens) a classification.

    Attributes:
        rule_id: Identifier of the analyzer rule that produced the evidence.
        description: Human readable explanation shown in the preview dialog.
        weight: Contribution to the score; may be negative.
    """

    rule_id: str
    description: str
    weight: float

    def __post_init__(self) -> None:
        """Validate the weight range."""
        if not -1.0 <= self.weight <= 1.0:
            raise ValueError(f"Evidence weight must be within [-1, 1], got {self.weight}")


@dataclass(frozen=True, slots=True)
class KindScore:
    """Accumulated score for one candidate :class:`ModKind`."""

    kind: ModKind
    score: float
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)

    @property
    def confidence(self) -> ConfidenceLevel:
        """Return the bucketed confidence for this score."""
        return ConfidenceLevel.from_score(self.score)


@dataclass(frozen=True, slots=True)
class ModClassification:
    """Final verdict of the analyzer for one mod package.

    Attributes:
        primary: Winning category.
        score: Normalised confidence of :attr:`primary` in ``0.0`` - ``1.0``.
        candidates: Every scored category, best first.
        tags: Free-form labels such as ``addon`` or ``requires_scripthook``.
    """

    primary: ModKind
    score: float
    candidates: tuple[KindScore, ...] = field(default_factory=tuple)
    tags: frozenset[str] = field(default_factory=frozenset)

    @property
    def confidence(self) -> ConfidenceLevel:
        """Return the bucketed confidence of the primary category."""
        return ConfidenceLevel.from_score(self.score)

    @property
    def is_reliable(self) -> bool:
        """Return whether the verdict is trustworthy enough to auto-install."""
        return self.score >= 0.5 and self.primary is not ModKind.UNKNOWN

    @property
    def evidence(self) -> tuple[Evidence, ...]:
        """Return the evidence backing the primary category."""
        for candidate in self.candidates:
            if candidate.kind is self.primary:
                return candidate.evidence
        return ()

    @property
    def secondary_kinds(self) -> tuple[ModKind, ...]:
        """Return other categories that also scored above the noise floor."""
        return tuple(
            candidate.kind
            for candidate in self.candidates
            if candidate.kind is not self.primary and candidate.score >= 0.25
        )

    @staticmethod
    def unknown() -> "ModClassification":
        """Return the neutral classification used when nothing matched."""
        return ModClassification(primary=ModKind.UNKNOWN, score=0.0)
