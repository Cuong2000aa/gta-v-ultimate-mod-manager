"""Spawn Center: browse and copy vehicle / ped spawn codes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.viewmodels.spawn_vm import SpawnViewModel
from gta_mod_manager.gui.widgets.cards import Card, page_header
from gta_mod_manager.models.spawn import SpawnEntry, SpawnKind

_CODE_ROLE = Qt.ItemDataRole.UserRole


class SpawnView(QWidget):
    """Lists spawn codes from installed mods with one-click copy."""

    def __init__(self, view_model: SpawnViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._build()
        self._vm.entriesLoaded.connect(self._render)
        self._vm.copied.connect(self._on_copied)
        self._vm.busyChanged.connect(self._on_busy)

    def refresh(self) -> None:
        """Reload the catalog."""
        self._vm.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(page_header(t("spawn.title"), t("spawn.subtitle")))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText(t("spawn.search_ph"))
        self._search.returnPressed.connect(self._apply_filters)
        toolbar.addWidget(self._search, 1)

        self._kind = QComboBox()
        self._kind.addItem(t("spawn.filter_all"), None)
        self._kind.addItem(t("spawn.filter_vehicles"), SpawnKind.VEHICLE)
        self._kind.addItem(t("spawn.filter_peds"), SpawnKind.PED)
        self._kind.currentIndexChanged.connect(lambda _i: self._apply_filters())
        toolbar.addWidget(self._kind)

        refresh = QPushButton(t("common.refresh"))
        refresh.clicked.connect(self.refresh)
        toolbar.addWidget(refresh)
        layout.addLayout(toolbar)

        catalog = Card(t("spawn.card_codes"))
        self._table = QTreeWidget()
        self._table.setColumnCount(4)
        self._table.setHeaderLabels(
            [
                t("spawn.col_code"),
                t("spawn.col_kind"),
                t("spawn.col_mod"),
                t("spawn.col_tip"),
            ]
        )
        self._table.setRootIsDecorated(False)
        self._table.setAlternatingRowColors(True)
        self._table.setMinimumHeight(280)
        self._table.itemDoubleClicked.connect(self._copy_item)
        header = self._table.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        catalog.body.addWidget(self._table)

        actions = QHBoxLayout()
        self._status = QLabel(t("spawn.empty"))
        self._status.setObjectName("Hint")
        actions.addWidget(self._status, 1)
        self._copy_button = QPushButton(t("spawn.copy"))
        self._copy_button.setObjectName("PrimaryButton")
        self._copy_button.setEnabled(False)
        self._copy_button.clicked.connect(self._copy_selected)
        actions.addWidget(self._copy_button)
        catalog.body.addLayout(actions)
        layout.addWidget(catalog, 1)

        tips = Card(t("spawn.card_tips"))
        tip = QLabel(t("spawn.tips_body"))
        tip.setObjectName("Hint")
        tip.setWordWrap(True)
        tips.body.addWidget(tip)
        layout.addWidget(tips)

        self._table.itemSelectionChanged.connect(self._sync_copy_enabled)

    def _apply_filters(self) -> None:
        kind = self._kind.currentData()
        self._vm.apply_filters(
            query=self._search.text(),
            kind=kind if isinstance(kind, SpawnKind) else None,
        )

    def _render(self, entries: object) -> None:
        self._table.clear()
        rows = entries if isinstance(entries, tuple) else ()
        for entry in rows:
            assert isinstance(entry, SpawnEntry)
            kind_label = (
                t("spawn.kind_vehicle")
                if entry.kind is SpawnKind.VEHICLE
                else t("spawn.kind_ped")
            )
            item = QTreeWidgetItem(
                [entry.code, kind_label, entry.mod_name, entry.tip]
            )
            item.setData(0, _CODE_ROLE, entry.code)
            item.setToolTip(0, entry.tip)
            self._table.addTopLevelItem(item)
        if rows:
            self._status.setText(t("spawn.count", count=len(rows)))
            self._table.setCurrentItem(self._table.topLevelItem(0))
        else:
            self._status.setText(t("spawn.empty"))
        self._sync_copy_enabled()

    def _sync_copy_enabled(self) -> None:
        self._copy_button.setEnabled(self._table.currentItem() is not None)

    def _copy_selected(self) -> None:
        item = self._table.currentItem()
        if item is None:
            return
        code = item.data(0, _CODE_ROLE)
        if code:
            self._vm.copy_code(str(code))

    def _copy_item(self, item: QTreeWidgetItem, _column: int) -> None:
        code = item.data(0, _CODE_ROLE)
        if code:
            self._vm.copy_code(str(code))

    def _on_copied(self, code: str) -> None:
        self._status.setText(t("spawn.copied", code=code))

    def _on_busy(self, busy: bool) -> None:
        self._copy_button.setEnabled(not busy and self._table.currentItem() is not None)
        self._search.setEnabled(not busy)
        self._kind.setEnabled(not busy)
