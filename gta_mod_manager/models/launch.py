"""Models for the pre-launch health check and game start."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class LaunchIssueSeverity(str, Enum):
    """How urgently a preflight finding should be addressed."""

    WARNING = "warning"
    ERROR = "error"

    @property
    def is_blocking(self) -> bool:
        """Return whether this severity blocks an automatic launch."""
        return self is LaunchIssueSeverity.ERROR


@dataclass(frozen=True, slots=True)
class LaunchIssue:
    """One problem found before launching the game."""

    code: str
    severity: LaunchIssueSeverity
    title: str
    detail: str
    source: str = "diagnostics"


@dataclass(frozen=True, slots=True)
class LaunchPreflightReport:
    """Result of the quick health check before Play."""

    game_root: Path
    executable: Path | None
    issues: tuple[LaunchIssue, ...] = field(default_factory=tuple)

    @property
    def is_clean(self) -> bool:
        """Return whether nothing needs attention."""
        return not self.issues

    @property
    def has_blocking(self) -> bool:
        """Return whether any issue should block auto-launch."""
        return any(item.severity.is_blocking for item in self.issues)

    @property
    def can_launch(self) -> bool:
        """Return whether an executable is available to start."""
        return self.executable is not None and self.executable.is_file()


@dataclass(frozen=True, slots=True)
class LaunchOutcome:
    """Outcome of trying to start GTA V."""

    executable: Path
    message: str
