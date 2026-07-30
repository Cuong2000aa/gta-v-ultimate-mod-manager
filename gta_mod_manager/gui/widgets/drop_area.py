"""Drag-and-drop target for mod archives."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from gta_mod_manager.core import constants
from gta_mod_manager.gui.i18n import t


class DropArea(QFrame):
    """Accepts dropped archives and folders.

    Attributes:
        fileDropped: Emitted with the path the user dropped or picked.
        browseRequested: Emitted when the user clicks the browse button.
    """

    fileDropped = Signal(object)
    browseRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropArea")
        self.setAcceptDrops(True)
        self.setProperty("dragActive", False)
        self.setMinimumHeight(160)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)

        title = QLabel(t("drop.title"))
        title.setObjectName("DropAreaTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        formats = ", ".join(
            sorted(suffix.lstrip(".") for suffix in constants.ARCHIVE_EXTENSIONS)
        )
        hint = QLabel(t("drop.hint", formats=formats))
        hint.setObjectName("Hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        browse = QPushButton(t("common.browse"))
        browse.clicked.connect(self.browseRequested)
        layout.addWidget(browse, alignment=Qt.AlignmentFlag.AlignCenter)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt override
        """Accept the drag when it carries local paths."""
        if self._first_local_path(event) is not None:
            self._set_drag_active(True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802 - Qt override
        """Reset the highlight when the drag leaves."""
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt override
        """Emit :attr:`fileDropped` for the first dropped path."""
        self._set_drag_active(False)
        path = self._first_local_path(event)
        if path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self.fileDropped.emit(path)

    def _set_drag_active(self, active: bool) -> None:
        """Toggle the highlight styling."""
        self.setProperty("dragActive", active)
        style = self.style()
        style.unpolish(self)
        style.polish(self)

    @staticmethod
    def _first_local_path(event: QDragEnterEvent | QDropEvent) -> Path | None:
        """Return the first local file or folder carried by ``event``."""
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            if url.isLocalFile():
                candidate = Path(url.toLocalFile())
                if candidate.exists():
                    return candidate
        return None
