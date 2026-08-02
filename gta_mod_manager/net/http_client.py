"""Minimal HTTP helpers built on the standard library (no extra deps)."""

from __future__ import annotations

import http.cookiejar
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger

_LOGGER = get_logger("net.http")

ProgressCallback = Callable[[int, int | None], None]


def build_opener(
    *,
    cookie_jar: http.cookiejar.CookieJar | None = None,
) -> urllib.request.OpenerDirector:
    """Return an opener that tolerates common TLS setups."""
    context = ssl.create_default_context()
    handlers: list[urllib.request.BaseHandler] = [
        urllib.request.HTTPSHandler(context=context),
    ]
    if cookie_jar is not None:
        handlers.insert(0, urllib.request.HTTPCookieProcessor(cookie_jar))
    return urllib.request.build_opener(*handlers)


def request_json(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 30.0,
) -> Any:
    """GET ``url`` and decode a JSON body."""
    raw = request_bytes(url, headers=headers, timeout=timeout)
    return json.loads(raw.decode("utf-8"))


def request_text(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 30.0,
    encoding: str = "utf-8",
    cookie_jar: http.cookiejar.CookieJar | None = None,
) -> str:
    """GET ``url`` and decode a text body."""
    raw = request_bytes(
        url, headers=headers, timeout=timeout, cookie_jar=cookie_jar
    )
    return raw.decode(encoding, errors="replace")


def request_bytes(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 30.0,
    cookie_jar: http.cookiejar.CookieJar | None = None,
) -> bytes:
    """GET ``url`` and return the raw response body."""
    request = urllib.request.Request(url, headers=_with_user_agent(headers), method="GET")
    opener = build_opener(cookie_jar=cookie_jar)
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(_format_http_error(error.code, body)) from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Network error: {error.reason}") from error


def download_file(
    url: str,
    destination: Path,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 120.0,
    on_progress: ProgressCallback | None = None,
    cookie_jar: http.cookiejar.CookieJar | None = None,
) -> Path:
    """Stream ``url`` into ``destination``, creating parents as needed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers=_with_user_agent(headers), method="GET")
    opener = build_opener(cookie_jar=cookie_jar)
    try:
        with opener.open(request, timeout=timeout) as response:
            total_header = response.headers.get("Content-Length")
            total = int(total_header) if total_header and total_header.isdigit() else None
            written = 0
            with partial.open("wb") as handle:
                while True:
                    chunk = response.read(constants.HASH_CHUNK_SIZE)
                    if not chunk:
                        break
                    handle.write(chunk)
                    written += len(chunk)
                    if on_progress is not None:
                        on_progress(written, total)
    except urllib.error.HTTPError as error:
        partial.unlink(missing_ok=True)
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(_format_http_error(error.code, body)) from error
    except urllib.error.URLError as error:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Network error: {error.reason}") from error
    except Exception:
        partial.unlink(missing_ok=True)
        raise

    partial.replace(destination)
    _LOGGER.info("Downloaded %s (%s bytes)", destination.name, destination.stat().st_size)
    return destination


def filename_from_url(url: str, fallback: str = "download.bin") -> str:
    """Pick a filesystem-safe name from a URL path."""
    parsed = urllib.parse.urlparse(url)
    name = Path(urllib.parse.unquote(parsed.path)).name
    if not name or name in {".", "/"}:
        return fallback
    return name


def is_archive_filename(name: str) -> bool:
    """Return whether ``name`` looks like a mod archive."""
    return Path(name).suffix.lower() in constants.ARCHIVE_DOWNLOAD_EXTENSIONS


def _with_user_agent(headers: Mapping[str, str] | None) -> dict[str, str]:
    merged = {
        "User-Agent": constants.ONLINE_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        merged.update(dict(headers))
    return merged


def _format_http_error(status: int, body: str) -> str:
    snippet = body.strip().replace("\n", " ")
    if len(snippet) > 240:
        snippet = snippet[:237] + "..."
    if snippet:
        return f"HTTP {status}: {snippet}"
    return f"HTTP {status}"
