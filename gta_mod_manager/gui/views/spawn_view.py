"""Spawn Center: browse and copy vehicle / ped spawn codes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.viewmodels.spawn_vm import SpawnViewModel
from gta_mod_manager.gui.widgets.cards import Card, page_header
from gta_mod_manager.models.enums import ModKind
from gta_mod_manager.models.spawn import SpawnEntry, SpawnKind

_CODE_ROLE = Qt.ItemDataRole.UserRole

_INSTALL_KIND_KEYS: dict[str, str] = {
    ModKind.VEHICLE_ADDON.value: "spawn.install_addon",
    ModKind.VEHICLE_REPLACE.value: "spawn.install_replace",
    ModKind.PED.value: "spawn.install_ped",
    "addon_ped": "spawn.install_ped",
    "peds": "spawn.install_ped",
    "character": "spawn.install_ped",
    "tuning": "spawn.install_tuning",
    "vehicle_tuning": "spawn.install_tuning",
}


class SpawnView(QWidget):
    """Lists spawn codes from installed mods with one-click copy."""

    def __init__(self, view_model: SpawnViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._all_entries: tuple[SpawnEntry, ...] = ()
        self._build()
        self._vm.entriesLoaded.connect(self._on_entries_loaded)
        self._vm.copied.connect(self._on_copied)
        self._vm.busyChanged.connect(self._on_busy)

    def refresh(self) -> None:
        """Reload the full catalog (tabs / search filter in the view)."""
        self._vm.apply_filters(query="", kind=None)

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(page_header(t("spawn.title"), t("spawn.subtitle")))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText(t("spawn.search_ph"))
        self._search.textChanged.connect(self._render_filtered)
        self._search.returnPressed.connect(self._render_filtered)
        toolbar.addWidget(self._search, 1)

        refresh = QPushButton(t("common.refresh"))
        refresh.clicked.connect(self.refresh)
        toolbar.addWidget(refresh)
        layout.addLayout(toolbar)

        self._tabs = QTabBar()
        self._tabs.setExpanding(False)
        self._tabs.setDocumentMode(True)
        self._tabs.addTab(t("spawn.filter_all"))
        self._tabs.addTab(t("spawn.filter_vehicles"))
        self._tabs.addTab(t("spawn.filter_peds"))
        self._tabs.setCurrentIndex(1)
        self._tabs.currentChanged.connect(self._render_filtered)
        layout.addWidget(self._tabs)

        catalog = Card(t("spawn.card_codes"))
        self._table = QTreeWidget()
        self._table.setColumnCount(4)
        self._table.setHeaderLabels(
            [
                t("spawn.col_code"),
                t("spawn.col_kind"),
                t("spawn.col_mod"),
                t("spawn.col_install"),
            ]
        )
        self._table.setRootIsDecorated(False)
        self._table.setAlternatingRowColors(True)
        self._table.setMinimumHeight(280)
        self._table.itemDoubleClicked.connect(self._copy_item)
        self._table.itemSelectionChanged.connect(self._sync_copy_enabled)
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

    def _current_kind(self) -> SpawnKind | None:
        index = self._tabs.currentIndex()
        if index == 1:
            return SpawnKind.VEHICLE
        if index == 2:
            return SpawnKind.PED
        return None

    def _on_entries_loaded(self, entries: object) -> None:
        self._all_entries = entries if isinstance(entries, tuple) else ()
        self._update_tab_labels()
        self._render_filtered()

    def _update_tab_labels(self) -> None:
        vehicles = sum(1 for entry in self._all_entries if entry.kind is SpawnKind.VEHICLE)
        peds = sum(1 for entry in self._all_entries if entry.kind is SpawnKind.PED)
        total = len(self._all_entries)
        self._tabs.setTabText(0, t("spawn.tab_all_n", count=total))
        self._tabs.setTabText(1, t("spawn.tab_vehicles_n", count=vehicles))
        self._tabs.setTabText(2, t("spawn.tab_peds_n", count=peds))

    def _filtered_entries(self) -> tuple[SpawnEntry, ...]:
        kind = self._current_kind()
        needle = self._search.text().strip().lower()
        rows: list[SpawnEntry] = []
        for entry in self._all_entries:
            if kind is not None and entry.kind is not kind:
                continue
            if needle and needle not in entry.code.lower() and needle not in entry.mod_name.lower():
                continue
            rows.append(entry)
        return tuple(rows)

    def _render_filtered(self) -> None:
        rows = self._filtered_entries()
        self._table.setColumnHidden(1, self._current_kind() is not None)
        self._table.clear()
        for entry in rows:
            kind_label = (
                t("spawn.kind_vehicle")
                if entry.kind is SpawnKind.VEHICLE
                else t("spawn.kind_ped")
            )
            install_label = _install_kind_label(entry.mod_kind)
            item = QTreeWidgetItem(
                [entry.code, kind_label, entry.mod_name, install_label]
            )
            item.setData(0, _CODE_ROLE, entry.code)
            if entry.tip:
                item.setToolTip(0, entry.tip)
                item.setToolTip(3, entry.tip)
            self._table.addTopLevelItem(item)
        if rows:
            self._status.setText(t("spawn.count", count=len(rows)))
            self._table.setCurrentItem(self._table.topLevelItem(0))
        else:
            kind = self._current_kind()
            if kind is SpawnKind.VEHICLE:
                self._status.setText(t("spawn.empty_vehicles"))
            elif kind is SpawnKind.PED:
                self._status.setText(t("spawn.empty_peds"))
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
        self._tabs.setEnabled(not busy)


def _install_kind_label(mod_kind: str) -> str:
    """Return a short Add-On / Replace / Ped label for the install-type column."""
    key = _INSTALL_KIND_KEYS.get(mod_kind.strip().lower())
    if key is not None:
        return t(key)
    if mod_kind.strip():
        return mod_kind.replace("_", " ").strip().title()
    return t("spawn.install_unknown")
