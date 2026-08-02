"""Lightweight GTA5-Mods.com search / page helpers.

There is no public API. We parse public HTML and resolve the timed-download
page (``…/download/{id}``) to a ``files.gta5-mods.com`` CDN URL in-app.
"""

from __future__ import annotations

import http.cookiejar
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
#: CDN archive links (optional query string / protocol-relative).
_FILE_CDN = re.compile(
    r'(?:https?:)?//files\.gta5-mods\.com/[^\s"\'<>]+?\.(?:zip|rar|7z|oiv)'
    r'(?:\?[^\s"\'<>]*)?',
    re.IGNORECASE,
)
#: Primary Download button — ``href`` before or after ``class``.
_BTN_DOWNLOAD = re.compile(
    r'<a[^>]*href="([^"]+/download/\d+)"[^>]*class="[^"]*btn-download'
    r'|<a[^>]*class="[^"]*btn-download[^"]*"[^>]*href="([^"]+/download/\d+)"',
    re.IGNORECASE,
)
#: Any version download link (fallback when the primary button is missing).
_ANY_DOWNLOAD = re.compile(
    r'href="((?:https://www\.gta5-mods\.com)?'
    r"/(?:[a-z]{2}/)?(?:vehicles|weapons|maps|misc|scripts|player|mods|tools|"
    r'paint-jobs|paintjobs|liveries)/[^"/]+/download/\d+)"',
    re.IGNORECASE,
)
_SKIP_SLUGS = frozenset({"tags", "user", "users", "login", "register"})
_HTML_HEADERS = {"Accept": "text/html"}


class Gta5ModsClient:
    """Search GTA5-Mods and attempt to resolve a direct archive URL."""

    #: Category slugs that expose a ``/{category}/most-downloaded`` feed.
    BROWSE_CATEGORIES: tuple[str, ...] = (
        "vehicles",
        "weapons",
        "maps",
        "scripts",
        "player",
        "misc",
        "tools",
    )

    def search(
        self,
        query: str,
        *,
        limit: int = 25,
        category: str | None = None,
    ) -> Result[OnlineSearchResult]:
        """Return catalogue cards for ``query`` or a category popular feed."""
        cleaned = query.strip()
        browse = (category or "").strip().lower()
        if browse == "all":
            browse = ""
        if cleaned:
            url = f"{constants.GTA5MODS_SITE_BASE}/search/{quote(cleaned)}"
        elif browse in self.BROWSE_CATEGORIES:
            url = f"{constants.GTA5MODS_SITE_BASE}/{browse}/most-downloaded"
        else:
            url = f"{constants.GTA5MODS_SITE_BASE}/vehicles/most-downloaded"
        try:
            html = http_client.request_text(
                url,
                headers=_HTML_HEADERS,
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
        """Resolve a ``files.gta5-mods.com`` CDN URL without opening a browser.

        Uses one cookie jar across the mod page and timed download page so the
        site session (``_gta5-mods_session``) is preserved. When Cloudflare /
        captcha blocks the CDN link, fall back to opening the page in a browser
        instead of failing the background task hard.
        """
        if listing.source is not OnlineSource.GTA5_MODS:
            return Result.fail("Not a GTA5-Mods listing", code="online.wrong_source")

        jar = http.cookiejar.CookieJar()
        try:
            html = http_client.request_text(
                listing.page_url,
                headers=_HTML_HEADERS,
                timeout=30.0,
                cookie_jar=jar,
            )
        except RuntimeError as error:
            return Result.fail(str(error), code="online.gta5mods_page_failed")

        cdn = self._first_cdn(html)
        download_page = self._first_download_page_url(html, listing.page_url)
        if cdn is None and download_page is not None:
            try:
                timed_html = http_client.request_text(
                    download_page,
                    headers={
                        **_HTML_HEADERS,
                        "Referer": listing.page_url,
                    },
                    timeout=30.0,
                    cookie_jar=jar,
                )
            except RuntimeError as error:
                return Result.fail(
                    str(error),
                    code="online.gta5mods_download_page_failed",
                )
            cdn = self._first_cdn(timed_html)

        if cdn is not None:
            return Result.ok(
                OnlineDownloadPlan(
                    listing=listing,
                    mode=DownloadMode.DIRECT,
                    download_url=cdn,
                    suggested_filename=http_client.filename_from_url(
                        cdn, fallback=f"gta5mods-{listing.mod_id}.zip"
                    ),
                )
            )

        # Soft fallback: open the timed download page (or mod page) in a browser.
        open_url = download_page or listing.page_url
        return Result.ok(
            OnlineDownloadPlan(
                listing=listing,
                mode=DownloadMode.OPEN_BROWSER,
                download_url=open_url,
                message=(
                    "Could not resolve a direct download link from GTA5-Mods "
                    "(captcha or blocked page). Opening the site — download there, "
                    "then paste the files.gta5-mods.com link into Online Mods."
                ),
            )
        )

    @staticmethod
    def _first_cdn(html: str) -> str | None:
        """Return the first archive CDN URL embedded in ``html``, if any."""
        matches = _FILE_CDN.findall(html)
        if not matches:
            return None
        raw = matches[0]
        if raw.startswith("//"):
            return "https:" + raw
        return raw

    @staticmethod
    def _first_download_page_url(html: str, page_url: str) -> str | None:
        """Pick the primary ``…/download/{id}`` URL from a mod page."""
        match = _BTN_DOWNLOAD.search(html)
        href = None
        if match is not None:
            href = match.group(1) or match.group(2)
        if href is None:
            any_match = _ANY_DOWNLOAD.search(html)
            href = any_match.group(1) if any_match else None
        if href is None:
            return None
        return urljoin(page_url, href)

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
