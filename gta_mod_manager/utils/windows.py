"""Thin, testable wrappers around Windows-only APIs.

Every helper degrades gracefully on non-Windows hosts so the domain and the
test suite stay portable.
"""

from __future__ import annotations

import sys
from contextlib import suppress
from pathlib import Path

from gta_mod_manager.core.logging_setup import get_logger

_LOGGER = get_logger("utils.windows")

IS_WINDOWS = sys.platform.startswith("win")


class ProcessWatch:
    """Polls one process for exit, reading its exit code when possible.

    A process handle is opened once when the watch starts. If the handle
    cannot be opened (permissions), the watch degrades to a name lookup and
    reports the exit code as unknown (``None``).
    """

    _STILL_ACTIVE = 259

    def __init__(self, pid: int, name: str) -> None:
        self.pid = pid
        self.name = name
        self._handle: int | None = self._open(pid)

    @staticmethod
    def _open(pid: int) -> int | None:
        """Open the process with just enough access to read its exit code."""
        if not IS_WINDOWS:
            return None
        import ctypes

        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
            process_query_limited_information, False, pid
        )
        return int(handle) if handle else None

    def poll(self) -> tuple[bool, int | None]:
        """Return ``(still_running, exit_code)``.

        ``exit_code`` is only meaningful once ``still_running`` is ``False``;
        it stays ``None`` when Windows would not let us open the process.
        """
        if self._handle is not None:
            import ctypes
            from ctypes import wintypes

            code = wintypes.DWORD()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(  # type: ignore[attr-defined]
                self._handle, ctypes.byref(code)
            )
            if ok:
                if code.value == self._STILL_ACTIVE:
                    return True, None
                return False, int(code.value)
            self.close()  # handle went bad; fall through to the name lookup

        running = find_running_process((self.name,)) is not None
        return running, None

    def close(self) -> None:
        """Release the process handle."""
        if self._handle is None or not IS_WINDOWS:
            self._handle = None
            return
        import ctypes

        with suppress(Exception):
            ctypes.windll.kernel32.CloseHandle(self._handle)  # type: ignore[attr-defined]
        self._handle = None


def find_running_process(names: tuple[str, ...] | list[str]) -> tuple[int, str] | None:
    """Return ``(pid, name)`` of the first running process matching ``names``.

    Uses a toolhelp snapshot, so no extra dependency is needed. Returns
    ``None`` on non-Windows hosts or when nothing matches.
    """
    if not IS_WINDOWS:
        return None
    import ctypes
    from ctypes import wintypes

    wanted = {name.lower() for name in names}

    class ProcessEntry32(ctypes.Structure):
        """Subset of ``PROCESSENTRY32W`` used for the name lookup."""

        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    th32cs_snapprocess = 0x00000002
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    snapshot = kernel32.CreateToolhelp32Snapshot(th32cs_snapprocess, 0)
    if snapshot in (0, -1):
        return None
    try:
        entry = ProcessEntry32()
        entry.dwSize = ctypes.sizeof(ProcessEntry32)
        if not kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            return None
        while True:
            name = entry.szExeFile
            if name.lower() in wanted:
                return int(entry.th32ProcessID), name
            if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                return None
    finally:
        kernel32.CloseHandle(snapshot)


def read_registry_value(hive: str, key_path: str, value_name: str) -> str | None:
    """Return a registry string value, or ``None`` when unavailable.

    Args:
        hive: Hive name such as ``HKEY_LOCAL_MACHINE``.
        key_path: Path below the hive.
        value_name: Name of the value to read.
    """
    if not IS_WINDOWS:
        return None
    try:
        import winreg
    except ImportError:  # pragma: no cover - Windows only
        return None

    hive_handle = getattr(winreg, hive, None)
    if hive_handle is None:
        return None

    access_flags = (
        0,
        getattr(winreg, "KEY_WOW64_64KEY", 0),
        getattr(winreg, "KEY_WOW64_32KEY", 0),
    )
    for access_flag in access_flags:
        try:
            with winreg.OpenKey(hive_handle, key_path, 0, winreg.KEY_READ | access_flag) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        except OSError:
            continue
    return None


def iter_registry_subkeys(hive: str, key_path: str) -> tuple[str, ...]:
    """Return the names of every subkey below ``key_path``."""
    if not IS_WINDOWS:
        return ()
    try:
        import winreg
    except ImportError:  # pragma: no cover - Windows only
        return ()

    hive_handle = getattr(winreg, hive, None)
    if hive_handle is None:
        return ()

    names: list[str] = []
    try:
        with winreg.OpenKey(hive_handle, key_path, 0, winreg.KEY_READ) as key:
            index = 0
            while True:
                try:
                    names.append(winreg.EnumKey(key, index))
                except OSError:
                    break
                index += 1
    except OSError:
        return ()
    return tuple(names)


def read_file_version(path: Path) -> str | None:
    """Return the file version of a PE binary such as ``ScriptHookV.dll``.

    Uses ``pefile`` when available and falls back to the Win32 version API.
    Returns ``None`` when neither can read the resource.
    """
    if not path.is_file():
        return None

    version = _read_version_with_pefile(path)
    if version:
        return version
    return _read_version_with_win32(path)


def _read_version_with_pefile(path: Path) -> str | None:
    """Read the version resource using the optional ``pefile`` dependency."""
    try:
        import pefile  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        binary = pefile.PE(str(path), fast_load=True)
        binary.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]]
        )
        info = getattr(binary, "VS_FIXEDFILEINFO", None)
        if not info:
            return None
        fixed = info[0]
        parts = (
            fixed.FileVersionMS >> 16,
            fixed.FileVersionMS & 0xFFFF,
            fixed.FileVersionLS >> 16,
            fixed.FileVersionLS & 0xFFFF,
        )
        return ".".join(str(part) for part in parts)
    except Exception as error:  # noqa: BLE001 - malformed binaries are common
        _LOGGER.debug("pefile could not read %s: %s", path, error)
        return None
    finally:
        with suppress(Exception):
            binary.close()  # type: ignore[possibly-undefined]


def _read_version_with_win32(path: Path) -> str | None:
    """Read the version resource through ``ctypes`` on Windows."""
    if not IS_WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:  # pragma: no cover - Windows only
        return None

    try:
        version_dll = ctypes.WinDLL("version")  # type: ignore[attr-defined]
        size = version_dll.GetFileVersionInfoSizeW(ctypes.c_wchar_p(str(path)), None)
        if not size:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not version_dll.GetFileVersionInfoW(ctypes.c_wchar_p(str(path)), 0, size, buffer):
            return None
        pointer = ctypes.c_void_p()
        length = wintypes.UINT()
        if not version_dll.VerQueryValueW(
            buffer, ctypes.c_wchar_p("\\"), ctypes.byref(pointer), ctypes.byref(length)
        ):
            return None

        class FixedFileInfo(ctypes.Structure):
            """Subset of ``VS_FIXEDFILEINFO`` that carries the version."""

            _fields_ = [
                ("dwSignature", wintypes.DWORD),
                ("dwStrucVersion", wintypes.DWORD),
                ("dwFileVersionMS", wintypes.DWORD),
                ("dwFileVersionLS", wintypes.DWORD),
            ]

        info = ctypes.cast(pointer, ctypes.POINTER(FixedFileInfo)).contents
        return ".".join(
            str(part)
            for part in (
                info.dwFileVersionMS >> 16,
                info.dwFileVersionMS & 0xFFFF,
                info.dwFileVersionLS >> 16,
                info.dwFileVersionLS & 0xFFFF,
            )
        )
    except Exception as error:  # noqa: BLE001 - defensive: ctypes on odd hosts
        _LOGGER.debug("Win32 version lookup failed for %s: %s", path, error)
        return None
