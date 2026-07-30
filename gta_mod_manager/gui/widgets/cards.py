"""Small presentational widgets: cards, stat tiles and status badges."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

BADGE_OK = "BadgeOk"
BADGE_WARNING = "BadgeWarn"
BADGE_ERROR = "BadgeError"
BADGE_NEUTRAL = "BadgeNeutral"


class Card(QFrame):
    """A rounded panel used to group related content."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(10)

        self._title = QLabel(title.upper())
        self._title.setObjectName("CardTitle")
        self._title.setVisible(bool(title))
        self._layout.addWidget(self._title)

    @property
    def body(self) -> QVBoxLayout:
        """Return the layout content should be added to."""
        return self._layout

    def set_title(self, title: str) -> None:
        """Change the card heading."""
        self._title.setText(title.upper())
        self._title.setVisible(bool(title))

    def add(self, widget: QWidget) -> QWidget:
        """Append ``widget`` to the card body and return it."""
        self._layout.addWidget(widget)
        return widget


class StatCard(Card):
    """A card showing one headline number plus a caption."""

    def __init__(
        self, title: str, value: str = "-", caption: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(title, parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._value = QLabel(value)
        self._value.setObjectName("CardValue")
        self._layout.addWidget(self._value)

        self._caption = QLabel(caption)
        self._caption.setObjectName("Hint")
        self._caption.setWordWrap(True)
        self._caption.setVisible(bool(caption))
        self._layout.addWidget(self._caption)

    def set_value(self, value: str, caption: str = "") -> None:
        """Update the headline number and its caption."""
        self._value.setText(value)
        self._caption.setText(caption)
        self._caption.setVisible(bool(caption))


class Badge(QLabel):
    """A small coloured pill communicating a status."""

    def __init__(self, text: str = "", kind: str = BADGE_OK, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName(kind)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

    def set_state(self, text: str, kind: str) -> None:
        """Change both the label and the colour of the badge."""
        self.setText(text)
        self.setObjectName(kind)
        # Re-polish so the new object name picks up its stylesheet rule.
        style = self.style()
        style.unpolish(self)
        style.polish(self)


def page_header(title: str, subtitle: str = "") -> QWidget:
    """Return a standard page heading with an optional subtitle."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    heading = QLabel(title)
    heading.setObjectName("PageTitle")
    layout.addWidget(heading)

    if subtitle:
        caption = QLabel(subtitle)
        caption.setObjectName("PageSubtitle")
        caption.setWordWrap(True)
        layout.addWidget(caption)
    return container
