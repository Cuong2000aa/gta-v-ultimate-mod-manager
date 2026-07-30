"""Nexus Mods public API client for GTA V."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

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

_TERM_SPLIT = re.compile(r"\s+")


class NexusModsClient:
    """Talk to ``api.nexusmods.com`` using a personal API key."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key.strip()

    @property
    def configured(self) -> bool:
        """Return whether an API key is present."""
        return bool(self._api_key)

    def search(self, query: str, *, limit: int = 25) -> Result[OnlineSearchResult]:
        """Search GTA V mods, or return trending when ``query`` is empty."""
        if not self.configured:
            return Result.fail(
                "Add your Nexus Mods API key in Settings first",
                code="online.nexus_key_missing",
            )
        cleaned = query.strip()
        try:
            if cleaned:
                terms = ",".join(part for part in _TERM_SPLIT.split(cleaned) if part)
                payload = self._get(
                    f"/games/{constants.NEXUS_GAME_DOMAIN_GTA_V}/mods/"
                    f"search.json?terms={quote(terms)}"
                )
                rows = payload if isinstance(payload, list) else payload.get("results", [])
            else:
                payload = self._get(
                    f"/games/{constants.NEXUS_GAME_DOMAIN_GTA_V}/mods/trending.json"
                )
                rows = payload if isinstance(payload, list) else []
        except RuntimeError as error:
            return Result.fail(str(error), code="online.nexus_search_failed")

        listings = tuple(
            self._to_listing(row) for row in rows[:limit] if isinstance(row, dict)
        )
        return Result.ok(
            OnlineSearchResult(
                source=OnlineSource.NEXUS,
                query=cleaned,
                listings=listings,
            )
        )

    def plan_download(self, listing: OnlineModListing) -> Result[OnlineDownloadPlan]:
        """Resolve a download plan for ``listing`` (Premium API or browser)."""
        if listing.source is not OnlineSource.NEXUS:
            return Result.fail("Not a Nexus listing", code="online.wrong_source")
        if not self.configured:
            return Result.fail(
                "Add your Nexus Mods API key in Settings first",
                code="online.nexus_key_missing",
            )

        file_id = listing.file_id
        filename = ""
        if not file_id:
            try:
                files_payload = self._get(
                    f"/games/{constants.NEXUS_GAME_DOMAIN_GTA_V}/mods/"
                    f"{listing.mod_id}/files.json"
                )
            except RuntimeError as error:
                return Result.fail(str(error), code="online.nexus_files_failed")
            files = files_payload.get("files", []) if isinstance(files_payload, dict) else []
            chosen = self._pick_primary_file(files)
            if chosen is None:
                return Result.ok(
                    OnlineDownloadPlan(
                        listing=listing,
                        mode=DownloadMode.OPEN_BROWSER,
                        message=(
                            "No downloadable file listed via API — opening the Nexus page."
                        ),
                    )
                )
            file_id = str(chosen.get("file_id") or chosen.get("id") or "")
            filename = str(chosen.get("file_name") or chosen.get("name") or "")

        try:
            links = self._get(
                f"/games/{constants.NEXUS_GAME_DOMAIN_GTA_V}/mods/"
                f"{listing.mod_id}/files/{file_id}/download_link.json"
            )
        except RuntimeError as error:
            text = str(error)
            if "403" in text or "premium" in text.lower():
                return Result.ok(
                    OnlineDownloadPlan(
                        listing=listing,
                        mode=DownloadMode.OPEN_BROWSER,
                        message=(
                            "Nexus API downloads need Premium. Opening the Files tab — "
                            "download there, then drag the archive onto Install, or paste "
                            "the direct link here."
                        ),
                    )
                )
            return Result.fail(text, code="online.nexus_link_failed")

        url = self._first_uri(links)
        if not url:
            return Result.ok(
                OnlineDownloadPlan(
                    listing=listing,
                    mode=DownloadMode.OPEN_BROWSER,
                    message="No CDN link returned — opening the Nexus page instead.",
                )
            )
        suggested = filename or http_client.filename_from_url(url, fallback=f"nexus-{file_id}.zip")
        return Result.ok(
            OnlineDownloadPlan(
                listing=listing,
                mode=DownloadMode.DIRECT,
                download_url=url,
                suggested_filename=suggested,
            )
        )

    def _get(self, path: str) -> Any:
        url = f"{constants.NEXUS_API_BASE}{path}"
        return http_client.request_json(url, headers=self._headers())

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._api_key,
            "Accept": "application/json",
            "Application-Name": constants.APP_SLUG,
            "Application-Version": constants.APP_VERSION,
        }

    @staticmethod
    def _to_listing(row: dict[str, Any]) -> OnlineModListing:
        mod_id = str(row.get("mod_id") or row.get("id") or "")
        name = str(row.get("name") or row.get("title") or f"Mod {mod_id}")
        summary = str(row.get("summary") or row.get("description") or "")
        author = ""
        user = row.get("author") or row.get("uploaded_by") or row.get("user")
        if isinstance(user, dict):
            author = str(user.get("name") or "")
        elif user:
            author = str(user)
        picture = str(row.get("picture_url") or "")
        return OnlineModListing(
            source=OnlineSource.NEXUS,
            mod_id=mod_id,
            title=name,
            page_url=f"{constants.NEXUS_SITE_BASE}/mods/{mod_id}",
            summary=summary[:280],
            author=author,
            downloads=_as_int(row.get("mod_downloads") or row.get("downloads")),
            endorsements=_as_int(row.get("mod_endorsements") or row.get("endorsement_count")),
            image_url=picture,
            category=str(row.get("category_name") or ""),
        )

    @staticmethod
    def _pick_primary_file(files: list[Any]) -> dict[str, Any] | None:
        candidates = [row for row in files if isinstance(row, dict)]
        if not candidates:
            return None
        mains = [
            row
            for row in candidates
            if str(row.get("category_name") or "").lower() in {"main", "main files", ""}
            or int(row.get("category_id") or 0) in {1, 0}
        ]
        pool = mains or candidates
        pool.sort(key=lambda row: int(row.get("uploaded_timestamp") or 0), reverse=True)
        return pool[0]

    @staticmethod
    def _first_uri(payload: Any) -> str:
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and item.get("URI"):
                    return str(item["URI"])
        if isinstance(payload, dict) and payload.get("URI"):
            return str(payload["URI"])
        return ""


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
