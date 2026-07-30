"""Models for browsing and downloading mods from online catalogues."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class OnlineSource(str, Enum):
    """Where an online listing / download came from."""

    NEXUS = "nexus"
    GTA5_MODS = "gta5_mods"
    DIRECT_URL = "direct_url"

    @property
    def display_name(self) -> str:
        """Return a short UI label."""
        if self is OnlineSource.NEXUS:
            return "Nexus Mods"
        if self is OnlineSource.GTA5_MODS:
            return "GTA5-Mods"
        return "Direct URL"


class DownloadMode(str, Enum):
    """How the tool should obtain the archive."""

    #: Stream the file into the local downloads folder.
    DIRECT = "direct"
    #: Open the site page; the user finishes the download in a browser.
    OPEN_BROWSER = "open_browser"


@dataclass(frozen=True, slots=True)
class OnlineModListing:
    """One searchable catalogue entry."""

    source: OnlineSource
    mod_id: str
    title: str
    page_url: str
    summary: str = ""
    author: str = ""
    downloads: int | None = None
    endorsements: int | None = None
    image_url: str = ""
    #: Nexus file id when the listing already points at a primary file.
    file_id: str = ""
    category: str = ""


@dataclass(frozen=True, slots=True)
class OnlineDownloadPlan:
    """Resolved plan for fetching one archive."""

    listing: OnlineModListing
    mode: DownloadMode
    #: Direct HTTP(S) URL when :attr:`mode` is ``DIRECT``.
    download_url: str = ""
    suggested_filename: str = ""
    message: str = ""


@dataclass(frozen=True, slots=True)
class OnlineDownloadResult:
    """Outcome of a download attempt."""

    path: Path | None
    listing: OnlineModListing
    mode: DownloadMode
    opened_url: str = ""
    message: str = ""

    @property
    def ready_for_install(self) -> bool:
        """Return whether a local archive is ready for the Install page."""
        return self.path is not None and self.path.is_file()


@dataclass(frozen=True, slots=True)
class OnlineSearchResult:
    """A batch of catalogue hits."""

    source: OnlineSource
    query: str
    listings: tuple[OnlineModListing, ...] = field(default_factory=tuple)
