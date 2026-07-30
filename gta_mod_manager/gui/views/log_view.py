"""Log viewer: the in-memory ring buffer with filters."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gta_mod_manager.core.logging_setup import LogRecordView
from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.theme.palette import DARK_PALETTE
from gta_mod_manager.gui.viewmodels.log_vm import LOG_LEVELS, LogViewModel
from gta_mod_manager.gui.widgets.cards import Card, page_header

_LEVEL_COLOURS: dict[str, str] = {
    "DEBUG": DARK_PALETTE.text_muted,
    "INFO": DARK_PALETTE.text,
    "WARNING": DARK_PALETTE.warning,
    "ERROR": DARK_PALETTE.danger,
    "CRITICAL": DARK_PALETTE.danger,
}


class LogView(QWidget):
    """Shows the application log without leaving the window."""

    def __init__(
        self,
        view_model: LogViewModel,
        log_file: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._log_file = log_file
        self._build()

        self._vm.recordsLoaded.connect(self._render)

    def refresh(self) -> None:
        """Re-read the buffer."""
        self._vm.refresh()

    def append_live(self, level: str, logger: str, message: str) -> None:
        """Append one live record without re-reading the whole buffer."""
        if not self._follow.isChecked():
            return
        self._add_row(level, logger, message, timestamp="")
        self._trim_to_visible_limit()
        self._tree.scrollToBottom()

    def _build(self) -> None:
        """Compose the page."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)

        layout.addWidget(
            page_header(t("logs.title"), t("logs.subtitle"))
        )

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        toolbar.addWidget(QLabel(t("logs.level")))
        self._level = QComboBox()
        self._level.addItems(LOG_LEVELS)
        self._level.currentTextChanged.connect(self._vm.set_level)
        toolbar.addWidget(self._level)

        self._search = QLineEdit()
        self._search.setPlaceholderText(t("logs.filter_ph"))
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._vm.search)
        toolbar.addWidget(self._search, 1)

        self._follow = QCheckBox(t("logs.follow"))
        self._follow.setChecked(True)
        toolbar.addWidget(self._follow)

        reload_button = QPushButton(t("logs.reload"))
        reload_button.clicked.connect(self._vm.refresh)
        toolbar.addWidget(reload_button)

        clear_button = QPushButton(t("logs.clear"))
        clear_button.clicked.connect(self._vm.clear)
        toolbar.addWidget(clear_button)

        open_button = QPushButton(t("logs.open_file"))
        open_button.clicked.connect(self._open_log_file)
        toolbar.addWidget(open_button)
        layout.addLayout(toolbar)

        card = Card(t("logs.card_records"))
        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(
            [
                t("logs.col_time"),
                t("logs.col_level"),
                t("logs.col_logger"),
                t("logs.col_message"),
            ]
        )
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setUniformRowHeights(True)
        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        card.body.addWidget(self._tree)
        layout.addWidget(card, 1)

    def _render(self, records: tuple[LogRecordView, ...]) -> None:
        """Rebuild the table from ``records``."""
        self._tree.clear()
        for record in records:
            self._add_row(
                record.level,
                record.logger,
                record.message,
                timestamp=f"{record.timestamp:%H:%M:%S}",
            )
        self._tree.scrollToBottom()

    def _add_row(self, level: str, logger: str, message: str, timestamp: str) -> None:
        """Append one row to the table."""
        item = QTreeWidgetItem([timestamp, level, logger, message])
        colour = _LEVEL_COLOURS.get(level)
        if colour is not None:
            item.setForeground(1, QBrush(QColor(colour)))
            item.setForeground(3, QBrush(QColor(colour)))
        self._tree.addTopLevelItem(item)

    def _trim_to_visible_limit(self, limit: int = 2000) -> None:
        """Drop the oldest rows so live following cannot grow without bound."""
        excess = self._tree.topLevelItemCount() - limit
        for _ in range(max(0, excess)):
            self._tree.takeTopLevelItem(0)

    def _open_log_file(self) -> None:
        """Open the rotating log file in the system default editor."""
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._log_file)))
