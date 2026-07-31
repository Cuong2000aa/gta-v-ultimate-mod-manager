"""Models for the managed zombie game mode."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ZombieModeStatus:
    """Installed and dependency state for Simple Zombies Reborn."""

    installed: bool
    ready: bool
    version: str | None
    missing_dependencies: tuple[str, ...]
    phone_support: bool
    message: str
