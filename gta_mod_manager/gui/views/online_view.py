"""Online mods: search Nexus / GTA5-Mods and download into Install."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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
from gta_mod_manager.gui.viewmodels.online_vm import OnlineViewModel
from gta_mod_manager.gui.widgets.cards import Card, page_header
from gta_mod_manager.models.online_mod import OnlineDownloadResult, OnlineModListing, OnlineSource
from gta_mod_manager.services.gta5mods_client import Gta5ModsClient

_LISTING_ROLE = Qt.ItemDataRole.UserRole

_CATEGORY_LABELS: dict[str, str] = {
    "vehicles": "online.category_vehicles",
    "weapons": "online.category_weapons",
    "maps": "online.category_maps",
    "scripts": "online.category_scripts",
    "player": "online.category_player",
    "misc": "online.category_misc",
    "tools": "online.category_tools",
}


class OnlineView(QWidget):
    """Browse online catalogues and hand archives to the Install page."""

    installRequested = Signal(object)

    def __init__(self, view_model: OnlineViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._build()
        self._vm.resultsLoaded.connect(self._render)
        self._vm.downloadFinished.connect(self._on_download)
        self._vm.busyChanged.connect(self._on_busy)
        self._vm.statusChanged.connect(self._status.setText)

    def refresh(self) -> None:
        """Load the default feed for the active source."""
        self._vm.search(self._search.text().strip())

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(page_header(t("online.title"), t("online.subtitle")))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self._source = QComboBox()
        self._source.addItem(t("online.source_gta5mods"), OnlineSource.GTA5_MODS)
        self._source.addItem(t("online.source_nexus"), OnlineSource.NEXUS)
        self._source.currentIndexChanged.connect(self._on_source_changed)
        toolbar.addWidget(self._source)

        self._category = QComboBox()
        for slug in Gta5ModsClient.BROWSE_CATEGORIES:
            self._category.addItem(t(_CATEGORY_LABELS[slug]), slug)
        self._category.setCurrentIndex(
            Gta5ModsClient.BROWSE_CATEGORIES.index("vehicles")
        )
        self._category.currentIndexChanged.connect(self._on_category_changed)
        toolbar.addWidget(self._category)

        self._search = QLineEdit()
        self._search.setPlaceholderText(t("online.search_ph"))
        self._search.returnPressed.connect(self.refresh)
        toolbar.addWidget(self._search, 1)

        search_button = QPushButton(t("common.search"))
        search_button.setObjectName("PrimaryButton")
        search_button.clicked.connect(self.refresh)
        toolbar.addWidget(search_button)
        layout.addLayout(toolbar)

        paste = Card(t("online.card_paste"))
        paste_row = QHBoxLayout()
        self._url = QLineEdit()
        self._url.setPlaceholderText(t("online.url_ph"))
        self._url.returnPressed.connect(self._download_url)
        paste_row.addWidget(self._url, 1)
        paste_button = QPushButton(t("online.download_url"))
        paste_button.clicked.connect(self._download_url)
        paste_row.addWidget(paste_button)
        paste.body.addLayout(paste_row)
        paste_hint = QLabel(t("online.paste_hint"))
        paste_hint.setObjectName("Hint")
        paste_hint.setWordWrap(True)
        paste.body.addWidget(paste_hint)
        layout.addWidget(paste)

        results = Card(t("online.card_results"))
        self._table = QTreeWidget()
        self._table.setColumnCount(4)
        self._table.setHeaderLabels(
            [
                t("online.col_title"),
                t("online.col_author"),
                t("online.col_category"),
                t("online.col_stats"),
            ]
        )
        self._table.setRootIsDecorated(False)
        self._table.setAlternatingRowColors(True)
        self._table.setMinimumHeight(280)
        self._table.itemDoubleClicked.connect(self._download_item)
        header = self._table.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        results.body.addWidget(self._table)

        actions = QHBoxLayout()
        self._status = QLabel(t("online.empty"))
        self._status.setObjectName("Hint")
        actions.addWidget(self._status, 1)
        self._open_button = QPushButton(t("online.open_page"))
        self._open_button.setEnabled(False)
        self._open_button.clicked.connect(self._open_selected)
        actions.addWidget(self._open_button)
        self._download_button = QPushButton(t("online.download"))
        self._download_button.setObjectName("PrimaryButton")
        self._download_button.setEnabled(False)
        self._download_button.clicked.connect(self._download_selected)
        actions.addWidget(self._download_button)
        results.body.addLayout(actions)
        layout.addWidget(results, 1)

        tip = QLabel(t("online.tips"))
        tip.setObjectName("Hint")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        self._table.itemSelectionChanged.connect(self._sync_actions)

    def _on_source_changed(self, _index: int) -> None:
        data = self._source.currentData()
        if isinstance(data, OnlineSource):
            self._category.setEnabled(data is OnlineSource.GTA5_MODS)
            self._vm.set_source(data)

    def _on_category_changed(self, _index: int) -> None:
        slug = self._category.currentData()
        if isinstance(slug, str):
            self._vm.set_category(slug)

    def _render(self, listings: object) -> None:
        self._table.clear()
        rows = listings if isinstance(listings, tuple) else ()
        for listing in rows:
            if not isinstance(listing, OnlineModListing):
                continue
            stats = []
            if listing.endorsements is not None:
                stats.append(f"★ {listing.endorsements}")
            if listing.downloads is not None:
                stats.append(f"↓ {listing.downloads}")
            item = QTreeWidgetItem(
                [
                    listing.title,
                    listing.author or "—",
                    listing.category or listing.source.display_name,
                    " · ".join(stats) if stats else "—",
                ]
            )
            item.setData(0, _LISTING_ROLE, listing)
            item.setToolTip(0, listing.summary or listing.page_url)
            self._table.addTopLevelItem(item)
        if not rows:
            self._status.setText(t("online.empty"))
        self._sync_actions()

    def _selected_listing(self) -> OnlineModListing | None:
        item = self._table.currentItem()
        if item is None:
            return None
        listing = item.data(0, _LISTING_ROLE)
        return listing if isinstance(listing, OnlineModListing) else None

    def _sync_actions(self) -> None:
        has = self._selected_listing() is not None
        self._download_button.setEnabled(has)
        self._open_button.setEnabled(has)

    def _download_selected(self) -> None:
        listing = self._selected_listing()
        if listing is not None:
            self._vm.download(listing)

    def _download_item(self, item: QTreeWidgetItem, _column: int) -> None:
        listing = item.data(0, _LISTING_ROLE)
        if isinstance(listing, OnlineModListing):
            self._vm.download(listing)

    def _open_selected(self) -> None:
        listing = self._selected_listing()
        if listing is not None:
            self._vm.open_page(listing)

    def _download_url(self) -> None:
        text = self._url.text().strip()
        if text:
            self._vm.download_pasted_url(text)

    def _on_download(self, outcome: object) -> None:
        if not isinstance(outcome, OnlineDownloadResult):
            return
        path = OnlineViewModel.path_for_install(outcome)
        if path is not None:
            self.installRequested.emit(path)
            self._status.setText(t("online.ready_install", name=path.name))
        else:
            self._status.setText(outcome.message or t("online.opened_browser"))

    def _on_busy(self, busy: bool) -> None:
        self._download_button.setEnabled(not busy and self._selected_listing() is not None)
        self._open_button.setEnabled(not busy and self._selected_listing() is not None)
