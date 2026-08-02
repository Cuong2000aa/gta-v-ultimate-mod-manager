"""Browse and download mods from Nexus Mods / GTA5-Mods into Install."""

from __future__ import annotations

import re
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from gta_mod_manager.core import constants
from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.protocols import ProgressReporter
from gta_mod_manager.core.result import Result
from gta_mod_manager.models.online_mod import (
    DownloadMode,
    OnlineDownloadPlan,
    OnlineDownloadResult,
    OnlineModListing,
    OnlineSearchResult,
    OnlineSource,
)
from gta_mod_manager.net import http_client
from gta_mod_manager.repository.settings_repository import JsonSettingsRepository
from gta_mod_manager.services.gta5mods_client import Gta5ModsClient
from gta_mod_manager.services.nexus_mods_client import NexusModsClient

_LOGGER = get_logger("services.online_mod")

_NEXUS_MOD = re.compile(
    r"nexusmods\.com/(?:gta5|gtav)/mods/(\d+)",
    re.IGNORECASE,
)
_GTA5MODS_PAGE = re.compile(
    r"gta5-mods\.com/(vehicles|weapons|maps|misc|scripts|player|mods|tools|"
    r"paint-jobs|liveries)/([^/?#]+)",
    re.IGNORECASE,
)


class OnlineModService:
    """Catalogue search + download handoff for the Online page."""

    def __init__(
        self,
        paths: AppPaths,
        settings: JsonSettingsRepository,
        progress: ProgressReporter | None = None,
    ) -> None:
        self._paths = paths
        self._settings = settings
        self._progress = progress
        self._gta5mods = Gta5ModsClient()

    def search(
        self,
        source: OnlineSource,
        query: str,
        *,
        category: str | None = None,
    ) -> Result[OnlineSearchResult]:
        """Search ``source`` (empty query = category / trending feed)."""
        if source is OnlineSource.NEXUS:
            return self._nexus().search(query)
        if source is OnlineSource.GTA5_MODS:
            return self._gta5mods.search(query, category=category)
        return Result.fail("Choose Nexus Mods or GTA5-Mods", code="online.bad_source")

    def download_listing(self, listing: OnlineModListing) -> Result[OnlineDownloadResult]:
        """Download ``listing`` or open its page when a direct file is unavailable."""
        planned = self._plan_for_listing(listing)
        if planned.is_error:
            return Result.fail(planned.error or "Plan failed", code=planned.code)
        return self._execute_plan(planned.unwrap())

    def download_url(self, url: str) -> Result[OnlineDownloadResult]:
        """Download a pasted archive URL, or resolve a Nexus / GTA5-Mods page."""
        cleaned = url.strip()
        if not cleaned:
            return Result.fail("Paste a download or mod-page URL", code="online.empty_url")

        nexus = _NEXUS_MOD.search(cleaned)
        if nexus:
            listing = OnlineModListing(
                source=OnlineSource.NEXUS,
                mod_id=nexus.group(1),
                title=f"Nexus mod {nexus.group(1)}",
                page_url=f"{constants.NEXUS_SITE_BASE}/mods/{nexus.group(1)}",
            )
            return self.download_listing(listing)

        gta = _GTA5MODS_PAGE.search(cleaned)
        if gta:
            slug = gta.group(2)
            listing = OnlineModListing(
                source=OnlineSource.GTA5_MODS,
                mod_id=slug,
                title=slug.replace("-", " "),
                page_url=cleaned.split("?")[0],
                category=gta.group(1),
            )
            return self.download_listing(listing)

        if not cleaned.lower().startswith(("http://", "https://")):
            return Result.fail("URL must start with http:// or https://", code="online.bad_url")

        name = http_client.filename_from_url(cleaned)
        if not http_client.is_archive_filename(name):
            # Still try — some CDNs omit extensions until redirect.
            parsed = urlparse(cleaned)
            if "files.gta5-mods.com" not in parsed.netloc.lower() and "nexus" not in parsed.netloc.lower():
                return Result.fail(
                    "That does not look like a .zip / .rar / .7z download link",
                    code="online.not_archive",
                )

        listing = OnlineModListing(
            source=OnlineSource.DIRECT_URL,
            mod_id=name or "direct",
            title=name or "Direct download",
            page_url=cleaned,
        )
        plan = OnlineDownloadPlan(
            listing=listing,
            mode=DownloadMode.DIRECT,
            download_url=cleaned,
            suggested_filename=name or "mod-download.zip",
        )
        return self._execute_plan(plan)

    def open_in_browser(self, listing: OnlineModListing) -> Result[OnlineDownloadResult]:
        """Open the mod page without attempting a download."""
        webbrowser.open(listing.page_url)
        return Result.ok(
            OnlineDownloadResult(
                path=None,
                listing=listing,
                mode=DownloadMode.OPEN_BROWSER,
                opened_url=listing.page_url,
                message=f"Opened {listing.page_url}",
            )
        )

    def _plan_for_listing(self, listing: OnlineModListing) -> Result[OnlineDownloadPlan]:
        if listing.source is OnlineSource.NEXUS:
            return self._nexus().plan_download(listing)
        if listing.source is OnlineSource.GTA5_MODS:
            return self._gta5mods.plan_download(listing)
        return Result.fail("Unsupported listing", code="online.unsupported")

    def _execute_plan(self, plan: OnlineDownloadPlan) -> Result[OnlineDownloadResult]:
        if plan.mode is DownloadMode.OPEN_BROWSER:
            target = plan.download_url or plan.listing.page_url
            if plan.listing.source is OnlineSource.NEXUS and not plan.download_url:
                target = f"{plan.listing.page_url}?tab=files"
            webbrowser.open(target)
            return Result.ok(
                OnlineDownloadResult(
                    path=None,
                    listing=plan.listing,
                    mode=DownloadMode.OPEN_BROWSER,
                    opened_url=target,
                    message=plan.message
                    or "Opened the download page in your browser.",
                )
            )

        destination = self._destination(plan.suggested_filename or "mod-download.zip")
        sized = False
        if self._progress is not None:
            self._progress.start("online.download", f"Downloading {destination.name}")

        def on_progress(written: int, total: int | None) -> None:
            nonlocal sized
            if self._progress is None:
                return
            if total and total > 0 and not sized:
                sized = True
                self._progress.start(
                    "online.download",
                    f"Downloading {destination.name}",
                    total=total,
                )
            label = f"Downloading {destination.name}"
            if not total:
                label = f"{label} ({max(written, 0) // (1024 * 1024)} MB)"
            self._progress.advance("online.download", written, label)

        headers: dict[str, str] | None = None
        if "files.gta5-mods.com" in plan.download_url.lower():
            referer = plan.listing.page_url or constants.GTA5MODS_SITE_BASE
            headers = {"Referer": referer}

        try:
            path = http_client.download_file(
                plan.download_url,
                destination,
                headers=headers,
                on_progress=on_progress,
            )
        except RuntimeError as error:
            if self._progress is not None:
                self._progress.finish("online.download")
            return Result.fail(str(error), code="online.download_failed")
        if self._progress is not None:
            self._progress.finish("online.download")

        _LOGGER.info("Online download ready: %s", path)
        return Result.ok(
            OnlineDownloadResult(
                path=path,
                listing=plan.listing,
                mode=DownloadMode.DIRECT,
                message=f"Downloaded {path.name}",
            )
        )

    def _destination(self, filename: str) -> Path:
        safe = re.sub(r'[<>:"/\\|?*]', "_", filename).strip() or "mod-download.zip"
        folder = self._paths.downloads
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / safe
        if not target.exists():
            return target
        stem, suffix = target.stem, target.suffix
        index = 2
        while True:
            candidate = folder / f"{stem}-{index}{suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    def _nexus(self) -> NexusModsClient:
        key = self._settings.load().nexus_api_key
        return NexusModsClient(key)


def delete_owned_download(archive: Path, downloads_dir: Path) -> bool:
    """Delete ``archive`` when it lives under ``downloads_dir``.

    Returns:
        ``True`` when a file was removed.
    """
    try:
        resolved = archive.resolve()
        root = downloads_dir.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return False
    if not resolved.is_file():
        return False
    try:
        resolved.unlink()
    except OSError as error:
        _LOGGER.warning("Could not delete download %s: %s", resolved, error)
        return False
    _LOGGER.info("Deleted online download after install: %s", resolved)
    return True
