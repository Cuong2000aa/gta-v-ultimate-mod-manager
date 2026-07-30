"""Lightweight GTA5-Mods.com search / page helpers.

There is no public API. We parse public HTML carefully and fall back to the
browser when a direct CDN link is not available (captcha / timed download).
"""

from __future__ import annotations

import re
from html import unescape
from urllib.parse import quote, urljoin

from gta_mod_manager.core import constants
from gta_mod_manager.core.result import Result
from gta_mod_manager.models.online_mod import (
    DownloadMode,
    OnlineDownloadPlan,
    OnlineModListing,
    OnlineSearchResult,
    OnlineSource,
)
from gta_mod_manager.net import http_client

#: Relative or absolute mod-page links used in search / category grids.
_CARD_HREF = re.compile(
    r'href="((?:https://www\.gta5-mods\.com)?'
    r"/(vehicles|weapons|maps|misc|scripts|player|mods|tools|paint-jobs|paintjobs|"
    r'liveries)/([^"?#]+))"'
    r'(?:[^>]*title="([^"]*)")?',
    re.IGNORECASE,
)
_FILE_LIST_OBJ = re.compile(
    r'<div class="file-list-obj">(.*?)</div>\s*</div>\s*</div>',
    re.IGNORECASE | re.DOTALL,
)
_AUTHOR = re.compile(
    r'href="/users/([^"]+)"[^>]*title="([^"]*)"',
    re.IGNORECASE,
)
_DOWNLOADS = re.compile(
    r'title="([\d,]+)\s+Downloads"',
    re.IGNORECASE,
)
_FILE_CDN = re.compile(
    r'https://files\.gta5-mods\.com/[^\s"\'<>]+\.(?:zip|rar|7z|oiv)',
    re.IGNORECASE,
)
_SKIP_SLUGS = frozenset({"tags", "user", "users", "login", "register"})


class Gta5ModsClient:
    """Search GTA5-Mods and attempt to resolve a direct archive URL."""

    def search(self, query: str, *, limit: int = 25) -> Result[OnlineSearchResult]:
        """Return catalogue cards for ``query`` (or a popular feed)."""
        cleaned = query.strip()
        if cleaned:
            url = f"{constants.GTA5MODS_SITE_BASE}/search/{quote(cleaned)}"
        else:
            url = f"{constants.GTA5MODS_SITE_BASE}/vehicles/most-downloaded"
        try:
            html = http_client.request_text(
                url,
                headers={"Accept": "text/html"},
                timeout=30.0,
            )
        except RuntimeError as error:
            return Result.fail(str(error), code="online.gta5mods_search_failed")

        listings = self._parse_listings(html, limit=limit)
        return Result.ok(
            OnlineSearchResult(
                source=OnlineSource.GTA5_MODS,
                query=cleaned,
                listings=listings,
            )
        )

    def plan_download(self, listing: OnlineModListing) -> Result[OnlineDownloadPlan]:
        """Prefer a CDN file URL; otherwise open the mod page in a browser."""
        if listing.source is not OnlineSource.GTA5_MODS:
            return Result.fail("Not a GTA5-Mods listing", code="online.wrong_source")
        try:
            html = http_client.request_text(
                listing.page_url,
                headers={"Accept": "text/html"},
                timeout=30.0,
            )
        except RuntimeError as error:
            return Result.fail(str(error), code="online.gta5mods_page_failed")

        matches = _FILE_CDN.findall(html)
        if matches:
            url = matches[0]
            return Result.ok(
                OnlineDownloadPlan(
                    listing=listing,
                    mode=DownloadMode.DIRECT,
                    download_url=url,
                    suggested_filename=http_client.filename_from_url(
                        url, fallback=f"gta5mods-{listing.mod_id}.zip"
                    ),
                )
            )
        return Result.ok(
            OnlineDownloadPlan(
                listing=listing,
                mode=DownloadMode.OPEN_BROWSER,
                message=(
                    "GTA5-Mods requires their timed download page. Opening it in your "
                    "browser — when the file finishes, drag it onto Install, or paste "
                    "the final CDN link here."
                ),
            )
        )

    def _parse_listings(self, html: str, *, limit: int) -> tuple[OnlineModListing, ...]:
        """Extract mod cards from a search or category HTML page."""
        by_obj = self._parse_file_list_objects(html, limit=limit)
        if by_obj:
            return by_obj
        return self._parse_href_fallback(html, limit=limit)

    def _parse_file_list_objects(
        self, html: str, *, limit: int
    ) -> tuple[OnlineModListing, ...]:
        items: list[OnlineModListing] = []
        seen: set[str] = set()
        for block in _FILE_LIST_OBJ.findall(html):
            match = _CARD_HREF.search(block)
            if match is None:
                continue
            href, category, slug, title_attr = match.groups()
            if slug.lower() in _SKIP_SLUGS:
                continue
            page_url = urljoin(constants.GTA5MODS_SITE_BASE + "/", href.lstrip("/"))
            if page_url in seen:
                continue
            seen.add(page_url)
            title = unescape(title_attr or "").strip()
            if not title:
                name_match = re.search(
                    r'<div class="name">.*?<span[^>]*>(.*?)</span>',
                    block,
                    re.IGNORECASE | re.DOTALL,
                )
                title = unescape(name_match.group(1)).strip() if name_match else slug
            author_match = _AUTHOR.search(block)
            downloads_match = _DOWNLOADS.search(block)
            downloads = None
            if downloads_match:
                try:
                    downloads = int(downloads_match.group(1).replace(",", ""))
                except ValueError:
                    downloads = None
            items.append(
                OnlineModListing(
                    source=OnlineSource.GTA5_MODS,
                    mod_id=slug,
                    title=title or slug.replace("-", " "),
                    page_url=page_url,
                    author=unescape(author_match.group(2)).strip() if author_match else "",
                    downloads=downloads,
                    category=category,
                )
            )
            if len(items) >= limit:
                break
        return tuple(items)

    def _parse_href_fallback(self, html: str, *, limit: int) -> tuple[OnlineModListing, ...]:
        seen: set[str] = set()
        items: list[OnlineModListing] = []
        for match in _CARD_HREF.finditer(html):
            href, category, slug, title_attr = match.groups()
            if slug.lower() in _SKIP_SLUGS:
                continue
            page_url = urljoin(constants.GTA5MODS_SITE_BASE + "/", href.lstrip("/"))
            if page_url in seen:
                continue
            seen.add(page_url)
            title = unescape(title_attr or "").strip() or slug.replace("-", " ")
            items.append(
                OnlineModListing(
                    source=OnlineSource.GTA5_MODS,
                    mod_id=slug,
                    title=title,
                    page_url=page_url,
                    category=category,
                )
            )
            if len(items) >= limit:
                break
        return tuple(items)

    @staticmethod
    def absolute(url: str) -> str:
        """Resolve a possibly relative GTA5-Mods URL."""
        return urljoin(constants.GTA5MODS_SITE_BASE + "/", url)
