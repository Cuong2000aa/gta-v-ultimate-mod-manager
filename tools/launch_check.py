"""Start the real GUI entry point offscreen, then quit.

Used as a release smoke check: it proves ``gta_mod_manager.app.main`` can build
the container, apply the stylesheet, construct the window and shut down cleanly
without a display attached.

The quit request comes from a helper thread, because the timer has to be armed
after :func:`gta_mod_manager.app.main` created the ``QApplication``.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_RUN_SECONDS = 2.0
_STARTUP_TIMEOUT_SECONDS = 30.0


def main() -> int:
    """Launch the application, close it after a moment and report the result."""
    data_dir = Path(tempfile.mkdtemp(prefix="gtamm-launch-check-"))
    threading.Thread(target=_quit_once_running, daemon=True).start()

    from gta_mod_manager.app import main as app_main

    exit_code = app_main(["--data-dir", str(data_dir), "--debug"])
    print(f"Launch check finished with exit code {exit_code}; data in {data_dir}")
    return exit_code


def _quit_once_running() -> None:
    """Wait for the event loop to start, then ask it to stop."""
    from PySide6.QtCore import QMetaObject, Qt
    from PySide6.QtWidgets import QApplication

    deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        instance = QApplication.instance()
        if instance is not None and instance.topLevelWidgets():
            time.sleep(_RUN_SECONDS)
            QMetaObject.invokeMethod(instance, "quit", Qt.ConnectionType.QueuedConnection)
            return
        time.sleep(0.1)
    print("Launch check timed out waiting for the main window", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
