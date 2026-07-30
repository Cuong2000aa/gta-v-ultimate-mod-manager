"""Smoke tests for the GUI: build the window and visit every page.

These tests run against the offscreen Qt platform, so they never open a real
window. They exist to catch broken object names, missing signals and view
models drifting away from the services they call.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gta_mod_manager.bootstrap import Application

pytest.importorskip("PySide6")

from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402

from gta_mod_manager.gui.main_window import MainWindow  # noqa: E402
from gta_mod_manager.gui.theme import load_stylesheet  # noqa: E402
from gta_mod_manager.gui.widgets.toast import ToastHost  # noqa: E402

_PAGE_KEYS = (
    "dashboard",
    "install",
    "online",
    "installed",
    "spawn",
    "graphics",
    "conflicts",
    "diagnostics",
    "backup",
    "logs",
    "settings",
)


@pytest.fixture()
def window(qt_app, application: Application):  # noqa: ANN001, ANN201, ARG001
    """Return a main window wired to the isolated test application."""
    created = MainWindow(application)
    created.resize(1280, 800)
    yield created
    created.close()
    created.deleteLater()


def test_the_window_builds_with_every_page(window) -> None:  # noqa: ANN001
    assert window.windowTitle()
    assert set(window._page_index) == set(_PAGE_KEYS)


def test_every_page_can_be_shown_and_refreshed(window) -> None:  # noqa: ANN001
    for key in _PAGE_KEYS:
        window._show_page(key)
        assert window._pages.currentIndex() == window._page_index[key]


def test_the_status_bar_follows_progress_events(window) -> None:  # noqa: ANN001
    window._on_progress("install", "Copying files", 3, 10)

    assert not window._progress.isHidden()
    assert window._progress.value() == 3
    assert window._status_label.text() == "Copying files"


def test_an_indeterminate_task_shows_a_busy_bar(window) -> None:  # noqa: ANN001
    window._on_busy(True)
    assert window._progress.maximum() == 0

    window._on_busy(False)
    assert window._progress.isHidden()


def test_an_error_is_surfaced_without_a_modal_dialog(window) -> None:  # noqa: ANN001
    window._show_error("Installation refused: protected file")

    assert "protected file" in window._status_label.text()


def test_the_active_game_folder_reaches_the_sidebar(
    window, game_root: Path
) -> None:  # noqa: ANN001
    window._on_game_changed("gta_v", str(game_root))

    assert str(game_root) in window._sidebar._footer.text()


def test_dropping_an_archive_opens_the_install_page(
    window, addon_vehicle_zip: Path
) -> None:  # noqa: ANN001
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(addon_vehicle_zip))])
    event = QDropEvent(
        QPoint(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window.dropEvent(event)

    assert window._pages.currentIndex() == window._page_index["install"]


def test_dropping_a_missing_path_is_ignored(window, tmp_path: Path) -> None:  # noqa: ANN001
    window._show_page("dashboard")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path / "absent.zip"))])
    event = QDropEvent(
        QPoint(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window.dropEvent(event)

    assert window._pages.currentIndex() == window._page_index["dashboard"]


def test_toasts_never_swallow_clicks(qt_app) -> None:  # noqa: ANN001, ARG001
    host = ToastHost()

    assert host.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_the_dark_stylesheet_loads(qt_app) -> None:  # noqa: ANN001, ARG001
    sheet = load_stylesheet()

    assert "QPushButton" in sheet
