"""Colour tokens and stylesheet loading for the dark theme."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

STYLESHEET_FILE = "dark.qss"


@dataclass(frozen=True, slots=True)
class Palette:
    """Colour tokens substituted into the stylesheet.

    Keeping them in one dataclass means a light theme is a second instance,
    not a second stylesheet.
    """

    bg: str = "#0e1116"
    bg_alt: str = "#12161d"
    bg_elevated: str = "#161b23"
    bg_hover: str = "#1d2430"
    bg_selected: str = "#242d3b"
    border: str = "#232b36"
    border_strong: str = "#374252"
    text: str = "#e6edf5"
    text_muted: str = "#8b97a8"
    text_disabled: str = "#5a6474"
    accent: str = "#4cc2ff"
    accent_hover: str = "#6fd0ff"
    success: str = "#4ade80"
    success_bg: str = "#14361f"
    warning: str = "#fbbf24"
    warning_bg: str = "#3b2c07"
    danger: str = "#f87171"
    danger_bg: str = "#3d1919"

    def as_tokens(self) -> dict[str, str]:
        """Return the palette as ``token -> colour`` pairs."""
        return {key: value for key, value in asdict(self).items()}


DARK_PALETTE = Palette()


def load_stylesheet(palette: Palette = DARK_PALETTE) -> str:
    """Return the stylesheet with every ``@token`` replaced by its colour.

    Longer token names are substituted first so ``@bg_elevated`` is not
    partially replaced by ``@bg``.
    """
    source = Path(__file__).with_name(STYLESHEET_FILE)
    sheet = source.read_text(encoding="utf-8")
    for token, colour in sorted(
        palette.as_tokens().items(), key=lambda item: len(item[0]), reverse=True
    ):
        sheet = sheet.replace(f"@{token}", colour)
    return sheet
