"""Findings produced by the game diagnostics scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DiagnosticSeverity(str, Enum):
    """How urgently a finding should be addressed."""

    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    def rank(self) -> int:
        """Sort key — errors first."""
        return {
            DiagnosticSeverity.ERROR: 0,
            DiagnosticSeverity.WARNING: 1,
            DiagnosticSeverity.INFO: 2,
            DiagnosticSeverity.OK: 3,
        }[self]


@dataclass(frozen=True, slots=True)
class DiagnosticFinding:
    """One check result the diagnostics page can show.

    Attributes:
        code: Stable id, e.g. ``gfx.d3d_init`` or ``asi.openiv_missing``.
        severity: Urgency.
        title: Short headline (already translated or English catalog text).
        detail: Longer explanation.
        fix: Suggested remediation.
        evidence: Optional log snippet or path that triggered the finding.
        category: Grouping key for the UI tree.
        fix_action: Optional one-click repair id (see ``diagnostics.actions``).
        fix_targets: Pack names or archive member paths for ``fix_action``.
    """

    code: str
    severity: DiagnosticSeverity
    title: str
    detail: str
    fix: str = ""
    evidence: str = ""
    category: str = "general"
    fix_action: str = ""
    fix_targets: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_problem(self) -> bool:
        """Return whether this finding needs attention."""
        return self.severity in (DiagnosticSeverity.WARNING, DiagnosticSeverity.ERROR)

    @property
    def is_fixable(self) -> bool:
        """Return whether a safe one-click repair is available."""
        return bool(self.fix_action and self.fix_targets)


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    """Full scan of one installation."""

    game_root: Path
    findings: tuple[DiagnosticFinding, ...] = field(default_factory=tuple)

    @property
    def error_count(self) -> int:
        """How many error-level findings."""
        return sum(1 for item in self.findings if item.severity is DiagnosticSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """How many warning-level findings."""
        return sum(1 for item in self.findings if item.severity is DiagnosticSeverity.WARNING)

    @property
    def problem_count(self) -> int:
        """Errors + warnings."""
        return self.error_count + self.warning_count

    def by_category(self) -> dict[str, tuple[DiagnosticFinding, ...]]:
        """Group findings for the tree view."""
        groups: dict[str, list[DiagnosticFinding]] = {}
        for finding in sorted(self.findings, key=lambda item: (item.severity.rank, item.code)):
            groups.setdefault(finding.category, []).append(finding)
        return {key: tuple(items) for key, items in groups.items()}
