"""The outcome of one monitored game session."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from gta_mod_manager.models.diagnostic import DiagnosticFinding


@dataclass(frozen=True, slots=True)
class GameSessionReport:
    """What the crash monitor observed during one run of the game.

    Attributes:
        game_root: Installation the session belongs to.
        process_name: Executable that was watched, e.g. ``GTA5.exe``.
        started_at: When the game process appeared (UTC).
        ended_at: When the game process exited (UTC).
        exit_code: Process exit code, or ``None`` when it could not be read.
        crashed: Whether the exit looks abnormal (non-zero code or crash dump).
        findings: Evidence collected from logs, dumps and the mod library.
    """

    game_root: Path
    process_name: str
    started_at: datetime
    ended_at: datetime
    exit_code: int | None
    crashed: bool
    findings: tuple[DiagnosticFinding, ...] = field(default_factory=tuple)

    @property
    def duration_seconds(self) -> int:
        """How long the session lasted."""
        return max(0, int((self.ended_at - self.started_at).total_seconds()))

    @property
    def top_suspect(self) -> DiagnosticFinding | None:
        """Return the most urgent problem finding, if any."""
        problems = sorted(
            (item for item in self.findings if item.is_problem),
            key=lambda item: item.severity.rank,
        )
        return problems[0] if problems else None
