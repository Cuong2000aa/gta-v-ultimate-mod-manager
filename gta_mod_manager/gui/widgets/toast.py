"""Non-blocking toast notifications stacked in a corner of the window."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from gta_mod_manager.core.events import NotificationLevel
from gta_mod_manager.gui.theme.palette import DARK_PALETTE

DEFAULT_DURATION_MS = 6000

_LEVEL_COLOURS: dict[str, str] = {
    NotificationLevel.INFO.value: DARK_PALETTE.accent,
    NotificationLevel.SUCCESS.value: DARK_PALETTE.success,
    NotificationLevel.WARNING.value: DARK_PALETTE.warning,
    NotificationLevel.ERROR.value: DARK_PALETTE.danger,
}


class Toast(QFrame):
    """A single notification card that removes itself after a delay."""

    def __init__(
        self,
        title: str,
        message: str,
        level: str = NotificationLevel.INFO.value,
        duration_ms: int = DEFAULT_DURATION_MS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setFixedWidth(340)
        accent = _LEVEL_COLOURS.get(level, DARK_PALETTE.accent)
        self.setStyleSheet(f"#Toast {{ border-left: 4px solid {accent}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(3)

        heading = QLabel(title)
        heading.setObjectName("ToastTitle")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        body = QLabel(message)
        body.setObjectName("ToastMessage")
        body.setWordWrap(True)
        layout.addWidget(body)

        QTimer.singleShot(duration_ms, self._dismiss)

    def _dismiss(self) -> None:
        """Remove this toast from its host."""
        self.setParent(None)
        self.deleteLater()


class ToastHost(QWidget):
    """Container that stacks toasts at the bottom of its parent."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # The host is a transparent overlay: it must never paint over the page
        # underneath, nor swallow clicks meant for the widgets it covers.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.addStretch(1)

    def show_toast(
        self,
        title: str,
        message: str,
        level: str = NotificationLevel.INFO.value,
        duration_ms: int = DEFAULT_DURATION_MS,
    ) -> Toast:
        """Add a toast and return it.

        Only the three most recent toasts are kept so a burst of events cannot
        cover the whole window.
        """
        toast = Toast(title, message, level, duration_ms, self)
        self._layout.addWidget(toast, alignment=Qt.AlignmentFlag.AlignRight)
        self._trim(limit=3)
        return toast

    def _trim(self, limit: int) -> None:
        """Dismiss the oldest toasts beyond ``limit``."""
        toasts: list[Toast] = []
        for index in range(self._layout.count()):
            item = self._layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, Toast):
                toasts.append(widget)
        for toast in toasts[:-limit] if len(toasts) > limit else []:
            toast.setParent(None)
            toast.deleteLater()
