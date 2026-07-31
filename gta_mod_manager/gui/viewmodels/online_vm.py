"""View model for browsing / downloading online mods."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.models.online_mod import (
    OnlineDownloadResult,
    OnlineModListing,
    OnlineSearchResult,
    OnlineSource,
)
from gta_mod_manager.services.gta5mods_client import Gta5ModsClient
from gta_mod_manager.services.online_mod_service import OnlineModService


class OnlineViewModel(ViewModel):
    """Search catalogues and hand downloaded archives to Install."""

    resultsLoaded = Signal(object)
    downloadFinished = Signal(object)
    sourceChanged = Signal(object)

    def __init__(
        self,
        runner: TaskRunner,
        online: OnlineModService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._online = online
        self._source = OnlineSource.GTA5_MODS
        self._category = "vehicles"
        self._listings: tuple[OnlineModListing, ...] = ()
        self._query = ""

    @property
    def source(self) -> OnlineSource:
        """Return the active catalogue."""
        return self._source

    @property
    def category(self) -> str:
        """Return the active GTA5-Mods browse category slug."""
        return self._category

    @property
    def listings(self) -> tuple[OnlineModListing, ...]:
        """Return the last search hits."""
        return self._listings

    def set_source(self, source: OnlineSource) -> None:
        """Switch catalogue and re-run the last query."""
        self._source = source
        self.sourceChanged.emit(source)
        self.search(self._query)

    def set_category(self, category: str) -> None:
        """Switch GTA5-Mods category feed and refresh when the query is empty."""
        cleaned = (category or "vehicles").strip().lower()
        if cleaned not in Gta5ModsClient.BROWSE_CATEGORIES:
            cleaned = "vehicles"
        self._category = cleaned
        if self._source is OnlineSource.GTA5_MODS:
            self.search(self._query)

    def search(self, query: str) -> None:
        """Search the active catalogue (or browse the category feed)."""
        self._query = query
        source = self._source
        category = self._category if source is OnlineSource.GTA5_MODS else None
        label = source.display_name
        if source is OnlineSource.GTA5_MODS and not query.strip():
            self.statusChanged.emit(f"Browsing {label} / {category}...")
        else:
            self.statusChanged.emit(f"Searching {label}...")

        def work() -> OnlineSearchResult:
            result = self._online.search(source, query, category=category)
            if result.is_error:
                raise RuntimeError(result.error or "Search failed")
            return result.unwrap()

        def done(payload: OnlineSearchResult) -> None:
            self._listings = payload.listings
            self.resultsLoaded.emit(payload.listings)
            self.statusChanged.emit(
                f"{len(payload.listings)} result(s) on {payload.source.display_name}"
            )

        self.run(work, done)

    def download(self, listing: OnlineModListing) -> None:
        """Download ``listing`` (or open the site when needed)."""
        self.statusChanged.emit(f"Fetching {listing.title}...")

        def work() -> OnlineDownloadResult:
            result = self._online.download_listing(listing)
            if result.is_error:
                raise RuntimeError(result.error or "Download failed")
            return result.unwrap()

        self.run(work, self._on_download)

    def download_pasted_url(self, url: str) -> None:
        """Download a pasted Nexus / GTA5-Mods / CDN URL."""
        self.statusChanged.emit("Resolving URL...")

        def work() -> OnlineDownloadResult:
            result = self._online.download_url(url)
            if result.is_error:
                raise RuntimeError(result.error or "Download failed")
            return result.unwrap()

        self.run(work, self._on_download)

    def open_page(self, listing: OnlineModListing) -> None:
        """Open the mod page without downloading."""
        def work() -> OnlineDownloadResult:
            result = self._online.open_in_browser(listing)
            if result.is_error:
                raise RuntimeError(result.error or "Could not open page")
            return result.unwrap()

        self.run(work, lambda _r: self.statusChanged.emit(f"Opened {listing.title}"))

    def _on_download(self, outcome: OnlineDownloadResult) -> None:
        self.downloadFinished.emit(outcome)
        if outcome.ready_for_install and outcome.path is not None:
            self.statusChanged.emit(f"Ready to install: {outcome.path.name}")
        else:
            self.statusChanged.emit(outcome.message or "Opened download page")

    @staticmethod
    def path_for_install(outcome: OnlineDownloadResult) -> Path | None:
        """Return a local archive path when install can continue."""
        if outcome.ready_for_install:
            return outcome.path
        return None
