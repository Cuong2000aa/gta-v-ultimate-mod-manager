"""Download and extract the official ReShade injector for NCCVision."""

from __future__ import annotations

import ctypes
import re
import shutil
import subprocess
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.net import http_client

_LOGGER = get_logger("graphics.reshade")

_RESHADE_HOME = "https://reshade.me/"
_SETUP_HREF = re.compile(
    r'href="(/downloads/(ReShade_Setup_(\d+\.\d+\.\d+)(?:_Addon)?\.exe))"',
    re.IGNORECASE,
)
_VERSION_FILE = "VERSION.txt"


def discover_latest() -> tuple[str, str]:
    """Return ``(version, download_url)`` for the signed ReShade setup on reshade.me."""
    html = http_client.request_text(_RESHADE_HOME, timeout=45.0)
    signed: tuple[str, str] | None = None
    addon: tuple[str, str] | None = None
    for match in _SETUP_HREF.finditer(html):
        path, version = match.group(1), match.group(3)
        url = f"https://reshade.me{path}"
        if "_Addon" in match.group(2):
            addon = addon or (version, url)
        else:
            signed = (version, url)
            break
    if signed is not None:
        return signed
    if addon is not None:
        return addon
    raise OSError("Could not find a ReShade download link on reshade.me")


def read_injector_version(injector: Path) -> str | None:
    """Return the ProductVersion of ``injector``, or a VERSION.txt sibling."""
    version_file = injector.parent / _VERSION_FILE
    if version_file.is_file():
        text = version_file.read_text(encoding="utf-8").strip()
        if text:
            return text.splitlines()[0].strip()
    return _pe_product_version(injector)


def write_injector_version(injector_dir: Path, version: str) -> None:
    """Persist the installed ReShade version next to the injector DLL."""
    (injector_dir / _VERSION_FILE).write_text(f"{version}\n", encoding="utf-8")


def resolve_seven_zip(configured: Path | None = None) -> Path | None:
    """Return a usable 7-Zip executable for extracting the ReShade setup."""
    if configured is not None and configured.is_file():
        return configured
    for name in constants.SEVEN_ZIP_COMMAND_NAMES:
        located = shutil.which(name)
        if located:
            return Path(located)
    for candidate in constants.SEVEN_ZIP_INSTALL_PATHS:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def extract_reshade64(setup: Path, destination: Path, seven_zip: Path) -> Path:
    """Extract ``ReShade64.dll`` from the official setup executable via 7-Zip."""
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    completed = subprocess.run(  # noqa: S603 - executable resolved from known paths
        [str(seven_zip), "x", "-y", f"-o{destination}", str(setup)],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (
            completed.stderr.decode(errors="replace").strip()
            or completed.stdout.decode(errors="replace").strip()
            or f"exit {completed.returncode}"
        )
        raise OSError(f"7-Zip could not extract the ReShade setup: {detail}")
    matches = sorted(destination.rglob("ReShade64.dll"))
    if not matches:
        raise OSError("ReShade64.dll was not found inside the ReShade setup package")
    return matches[0]


def _pe_product_version(path: Path) -> str | None:
    """Read a dotted ProductVersion from a Windows PE via the version API."""
    if not path.is_file():
        return None

    class VS_FIXEDFILEINFO(ctypes.Structure):
        _fields_ = [
            ("dwSignature", ctypes.c_uint32),
            ("dwStrucVersion", ctypes.c_uint32),
            ("dwFileVersionMS", ctypes.c_uint32),
            ("dwFileVersionLS", ctypes.c_uint32),
            ("dwProductVersionMS", ctypes.c_uint32),
            ("dwProductVersionLS", ctypes.c_uint32),
            ("dwFileFlagsMask", ctypes.c_uint32),
            ("dwFileFlags", ctypes.c_uint32),
            ("dwFileOS", ctypes.c_uint32),
            ("dwFileType", ctypes.c_uint32),
            ("dwFileSubtype", ctypes.c_uint32),
            ("dwFileDateMS", ctypes.c_uint32),
            ("dwFileDateLS", ctypes.c_uint32),
        ]

    try:
        size = ctypes.windll.version.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(str(path), 0, size, buffer):
            return None
        value = ctypes.c_void_p()
        length = ctypes.c_uint()
        if not ctypes.windll.version.VerQueryValueW(
            buffer, "\\", ctypes.byref(value), ctypes.byref(length)
        ):
            return None
        if not value:
            return None
        info = ctypes.cast(value, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
        major = (info.dwProductVersionMS >> 16) & 0xFFFF
        minor = info.dwProductVersionMS & 0xFFFF
        patch = (info.dwProductVersionLS >> 16) & 0xFFFF
        return f"{major}.{minor}.{patch}"
    except (AttributeError, OSError, ValueError):
        _LOGGER.debug("Could not read PE version from %s", path, exc_info=True)
        return None
