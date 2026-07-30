"""Backup and restore page: snapshots, undo and version history."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.viewmodels.backup_vm import BackupViewModel
from gta_mod_manager.gui.widgets.cards import Card, page_header
from gta_mod_manager.services.backup_service import SnapshotSummary

_SNAPSHOT_ID_ROLE = Qt.ItemDataRole.UserRole


class BackupView(QWidget):
    """Lists restore points and offers undo, restore and delete."""

    def __init__(self, view_model: BackupViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._summaries: dict[str, SnapshotSummary] = {}
        self._build()

        self._vm.snapshotsLoaded.connect(self._render)

    def refresh(self) -> None:
        """Reload the snapshot list."""
        self._vm.refresh()

    def _build(self) -> None:
        """Compose the page."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)

        layout.addWidget(
            page_header(t("backup.title"), t("backup.subtitle"))
        )

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._undo_button = QPushButton(t("backup.undo_last"))
        self._undo_button.setObjectName("PrimaryButton")
        self._undo_button.clicked.connect(self._undo)
        toolbar.addWidget(self._undo_button)

        refresh_button = QPushButton(t("common.refresh"))
        refresh_button.clicked.connect(self._vm.refresh)
        toolbar.addWidget(refresh_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_table())
        splitter.addWidget(self._build_details())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

    def _build_table(self) -> QWidget:
        """Build the snapshot table."""
        card = Card(t("backup.card_points"))
        self._table = QTreeWidget()
        self._table.setColumnCount(4)
        self._table.setHeaderLabels(
            [
                t("backup.col_created"),
                t("backup.col_reason"),
                t("backup.col_files"),
                t("backup.col_size"),
            ]
        )
        self._table.setRootIsDecorated(False)
        self._table.setAlternatingRowColors(True)
        self._table.currentItemChanged.connect(self._on_selection)
        header = self._table.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        card.body.addWidget(self._table)
        return card

    def _build_details(self) -> QWidget:
        """Build the snapshot detail panel."""
        card = Card(t("backup.card_content"))

        self._label = QLabel(t("backup.select_point"))
        self._label.setObjectName("CardValue")
        self._label.setWordWrap(True)
        card.body.addWidget(self._label)

        self._meta = QLabel("")
        self._meta.setObjectName("Hint")
        self._meta.setWordWrap(True)
        card.body.addWidget(self._meta)

        self._entries = QListWidget()
        card.body.addWidget(self._entries, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self._restore_button = QPushButton(t("backup.restore_this"))
        self._restore_button.clicked.connect(self._restore)
        actions.addWidget(self._restore_button)

        self._delete_button = QPushButton(t("backup.delete"))
        self._delete_button.setObjectName("DangerButton")
        self._delete_button.clicked.connect(self._delete)
        actions.addWidget(self._delete_button)
        actions.addStretch(1)
        card.body.addLayout(actions)

        self._set_actions_enabled(False)
        return card

    def _render(self, summaries: tuple[SnapshotSummary, ...]) -> None:
        """Rebuild the table from ``summaries``."""
        selected = self._selected_id()
        self._summaries = {summary.snapshot_id: summary for summary in summaries}
        self._table.clear()

        for summary in summaries:
            snapshot = summary.snapshot
            item = QTreeWidgetItem(
                [
                    f"{snapshot.created_at:%Y-%m-%d %H:%M:%S}",
                    snapshot.reason,
                    str(snapshot.file_count),
                    summary.size_label,
                ]
            )
            item.setData(0, _SNAPSHOT_ID_ROLE, summary.snapshot_id)
            self._table.addTopLevelItem(item)
            if summary.snapshot_id == selected:
                self._table.setCurrentItem(item)

        self._undo_button.setEnabled(bool(summaries))
        if self._selected_id() is None:
            self._clear_details()

    def _on_selection(self, current: QTreeWidgetItem | None, _previous: object = None) -> None:
        """Show the entries of the selected snapshot."""
        summary = (
            None if current is None else self._summaries.get(current.data(0, _SNAPSHOT_ID_ROLE))
        )
        if summary is None:
            self._clear_details()
            return

        snapshot = summary.snapshot
        self._label.setText(snapshot.display_label)
        self._meta.setText(
            t(
                "backup.meta",
                files=snapshot.file_count,
                size=summary.size_label,
                root=snapshot.game_root,
            )
            + (t("backup.meta_mod", mod=snapshot.mod_id) if snapshot.mod_id else "")
        )
        self._entries.clear()
        for entry in snapshot.entries:
            marker = t("backup.marker_restore") if entry.existed else t("backup.marker_delete")
            self._entries.addItem(f"[{marker}] {entry.original_path}")
        self._set_actions_enabled(True)

    def _undo(self) -> None:
        """Undo the most recent operation after confirming."""
        answer = QMessageBox.question(
            self,
            t("backup.undo_title"),
            t("backup.undo_body"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if int(answer) == int(QMessageBox.StandardButton.Yes):
            self._vm.undo_last()

    def _restore(self) -> None:
        """Restore the selected snapshot after confirming."""
        snapshot_id = self._selected_id()
        summary = self._summaries.get(snapshot_id or "")
        if snapshot_id is None or summary is None:
            return

        answer = QMessageBox.question(
            self,
            t("backup.restore_title"),
            t(
                "backup.restore_body",
                count=summary.snapshot.file_count,
                label=summary.snapshot.display_label,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if int(answer) == int(QMessageBox.StandardButton.Yes):
            self._vm.restore(snapshot_id)

    def _delete(self) -> None:
        """Delete the selected snapshot after confirming."""
        snapshot_id = self._selected_id()
        if snapshot_id is None:
            return
        answer = QMessageBox.question(
            self,
            t("backup.delete_title"),
            t("backup.delete_body"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if int(answer) == int(QMessageBox.StandardButton.Yes):
            self._vm.delete(snapshot_id)

    def _selected_id(self) -> str | None:
        """Return the identifier of the selected snapshot."""
        item = self._table.currentItem()
        if item is None:
            return None
        snapshot_id = item.data(0, _SNAPSHOT_ID_ROLE)
        return str(snapshot_id) if snapshot_id is not None else None

    def _clear_details(self) -> None:
        """Reset the detail panel."""
        self._label.setText(t("backup.select_point"))
        self._meta.clear()
        self._entries.clear()
        self._set_actions_enabled(False)

    def _set_actions_enabled(self, enabled: bool) -> None:
        """Enable or disable the per-snapshot buttons."""
        self._restore_button.setEnabled(enabled)
        self._delete_button.setEnabled(enabled)
