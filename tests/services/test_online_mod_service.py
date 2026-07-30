"""Tests for online mod catalogue helpers."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.models.online_mod import DownloadMode, OnlineModListing, OnlineSource
from gta_mod_manager.models.settings import AppSettings
from gta_mod_manager.net import http_client
from gta_mod_manager.repository.settings_repository import JsonSettingsRepository
from gta_mod_manager.services.gta5mods_client import Gta5ModsClient
from gta_mod_manager.services.nexus_mods_client import NexusModsClient
from gta_mod_manager.services.online_mod_service import OnlineModService, delete_owned_download


def test_gta5mods_parses_search_cards() -> None:
    html = """
    <html><body>
      <div class="file-list">
        <div class="file-list-obj">
          <a href="/vehicles/f250-super-baja" title="F250 Super Baja" class="preview empty">
            <div class="stats">
              <span title="12,345 Downloads"><span class="fa fa-download"></span> 12,345</span>
            </div>
          </a>
          <div class="details">
            <div class="top"><div class="name">
              <a href="/vehicles/f250-super-baja" title="F250 Super Baja">
                <span dir="ltr">F250 Super Baja</span>
              </a>
            </div></div>
            <div class="bottom">
              By <a href="/users/AuthorOne" title="AuthorOne">AuthorOne</a>
            </div>
          </div>
        </div>
        <div class="file-list-obj">
          <a href="/scripts/simple-trainer" title="Simple Trainer" class="preview empty"></a>
          <div class="details">
            <div class="top"><div class="name">
              <a href="/scripts/simple-trainer" title="Simple Trainer">
                <span dir="ltr">Simple Trainer</span>
              </a>
            </div></div>
            <div class="bottom">
              By <a href="/users/AuthorTwo" title="AuthorTwo">AuthorTwo</a>
            </div>
          </div>
        </div>
      </div>
      <a href="https://www.gta5-mods.com/tags/cars">Cars</a>
    </body></html>
    """
    listings = Gta5ModsClient()._parse_listings(html, limit=10)
    assert [item.mod_id for item in listings] == ["f250-super-baja", "simple-trainer"]
    assert listings[0].source is OnlineSource.GTA5_MODS
    assert listings[0].author == "AuthorOne"
    assert listings[0].downloads == 12345
    assert listings[0].page_url.endswith("/vehicles/f250-super-baja")


def test_gta5mods_parses_relative_href_fallback() -> None:
    html = """
    <a href="/vehicles/lykan-hypersport" title="Lykan Hypersport">Lykan</a>
    <a href="/tags/cars">Cars</a>
    """
    listings = Gta5ModsClient()._parse_listings(html, limit=10)
    assert len(listings) == 1
    assert listings[0].mod_id == "lykan-hypersport"
    assert listings[0].page_url.endswith("/vehicles/lykan-hypersport")


def test_gta5mods_plan_prefers_cdn_link(monkeypatch) -> None:
    listing = OnlineModListing(
        source=OnlineSource.GTA5_MODS,
        mod_id="demo",
        title="Demo",
        page_url="https://www.gta5-mods.com/vehicles/demo",
    )
    html = (
        '<html><a href="https://files.gta5-mods.com/uploads/demo/demo-pack.zip">'
        "file</a></html>"
    )
    monkeypatch.setattr(http_client, "request_text", lambda *_a, **_k: html)
    plan = Gta5ModsClient().plan_download(listing).unwrap()
    assert plan.mode is DownloadMode.DIRECT
    assert plan.download_url.endswith("demo-pack.zip")


def test_nexus_requires_api_key() -> None:
    result = NexusModsClient("").search("trainer")
    assert result.is_error
    assert result.code == "online.nexus_key_missing"


def test_nexus_search_maps_rows(monkeypatch) -> None:
    client = NexusModsClient("test-key")

    def fake_get(path: str):
        assert "search.json" in path
        return [
            {
                "mod_id": 123,
                "name": "NaturalVision",
                "summary": "graphics",
                "author": "razed",
                "mod_downloads": 10,
                "endorsement_count": 5,
                "category_name": "Visuals",
            }
        ]

    monkeypatch.setattr(client, "_get", fake_get)
    payload = client.search("natural").unwrap()
    assert len(payload.listings) == 1
    assert payload.listings[0].title == "NaturalVision"
    assert payload.listings[0].page_url.endswith("/mods/123")


def test_online_service_downloads_direct_url(tmp_path: Path, monkeypatch) -> None:
    paths = AppPaths(root=tmp_path).ensure()
    settings = JsonSettingsRepository.at(paths.settings_file)
    settings.save(AppSettings())
    service = OnlineModService(paths, settings)

    def fake_download(url: str, destination: Path, **_kwargs):
        destination.write_bytes(b"PK\x03\x04fake")
        return destination

    monkeypatch.setattr(http_client, "download_file", fake_download)
    outcome = service.download_url("https://files.gta5-mods.com/uploads/x/car.zip").unwrap()
    assert outcome.ready_for_install
    assert outcome.path is not None
    assert outcome.path.is_file()
    assert outcome.path.parent == paths.downloads


def test_filename_helpers() -> None:
    assert http_client.is_archive_filename("pack.ZIP")
    assert not http_client.is_archive_filename("readme.txt")
    assert http_client.filename_from_url("https://cdn.example/a/b%20c.rar") == "b c.rar"


def test_delete_owned_download_only_removes_app_downloads(tmp_path: Path) -> None:
    paths = AppPaths(root=tmp_path).ensure()
    owned = paths.downloads / "lykan.zip"
    owned.write_bytes(b"zip")
    outside = tmp_path / "manual.zip"
    outside.write_bytes(b"zip")

    assert delete_owned_download(owned, paths.downloads) is True
    assert not owned.exists()
    assert delete_owned_download(outside, paths.downloads) is False
    assert outside.exists()
