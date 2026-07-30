"""GUI entry point: ``python -m gta_mod_manager.app``."""

from __future__ import annotations

import logging
import sys
from argparse import SUPPRESS, ArgumentParser, Namespace
from pathlib import Path

from gta_mod_manager.bootstrap import Application, build_application
from gta_mod_manager.core import constants
from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.data_root import configured_data_root, finalize_pending_cleanup
from gta_mod_manager.core.logging_setup import get_logger

_LOGGER = get_logger("app")


def parse_arguments(argv: list[str] | None = None) -> Namespace:
    """Parse the command line."""
    parser = ArgumentParser(prog=constants.APP_SLUG, description=constants.APP_NAME)
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Keep logs, backups and settings next to the application instead of in LOCALAPPDATA.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Explicit working directory for logs, backups and settings.",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Log at DEBUG level."
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Do not delete leftover extraction workspaces on startup.",
    )
    parser.add_argument("--smoke-test", action="store_true", help=SUPPRESS)
    return parser.parse_args(argv)


def resolve_paths(arguments: Namespace) -> AppPaths:
    """Return the working-directory layout the arguments ask for."""
    if arguments.data_dir is not None:
        return AppPaths(root=arguments.data_dir)
    if arguments.portable:
        return AppPaths.portable(Path(sys.argv[0]).resolve().parent)
    selected = configured_data_root()
    if selected is not None:
        return AppPaths(root=selected)
    return AppPaths.default()


def build(arguments: Namespace) -> Application:
    """Build the application object for the parsed arguments."""
    paths = resolve_paths(arguments)
    application = build_application(
        paths,
        log_level=logging.DEBUG if arguments.debug else logging.INFO,
        purge_temp=not arguments.keep_temp,
    )
    # Only clean the old copy after the migrated repositories and logging have
    # opened successfully. Explicit CLI/portable launches never mutate it.
    if arguments.data_dir is None and not arguments.portable:
        finalize_pending_cleanup(paths.root)
    return application


def main(argv: list[str] | None = None) -> int:
    """Start the GUI and return the process exit code."""
    arguments = parse_arguments(argv)
    application = build(arguments)
    _LOGGER.info(
        "%s %s starting - data directory %s",
        constants.APP_NAME,
        constants.APP_VERSION,
        application.paths.root,
    )

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication

    from gta_mod_manager.gui.i18n import set_language
    from gta_mod_manager.gui.main_window import MainWindow
    from gta_mod_manager.gui.theme.palette import load_stylesheet
    from gta_mod_manager.repository.settings_repository import JsonSettingsRepository

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar, True)
    qt_app = QApplication(sys.argv[:1] if argv is None else [])
    qt_app.setApplicationName(constants.APP_NAME)
    qt_app.setApplicationVersion(constants.APP_VERSION)
    qt_app.setOrganizationName(constants.ORG_NAME)
    qt_app.setStyleSheet(load_stylesheet())

    settings = application.container.resolve(JsonSettingsRepository).load()
    set_language(settings.language)

    if settings.crash_monitor_enabled:
        application.crash_monitor.start()

    window = MainWindow(application)
    # A quit request can also come from outside the window (session logout, a
    # tray action). Closing it here guarantees the event relay is detached and
    # the worker threads are joined in every case.
    qt_app.aboutToQuit.connect(window.close)
    window.show()
    if arguments.smoke_test:
        QTimer.singleShot(1500, qt_app.quit)

    exit_code = qt_app.exec()

    application.crash_monitor.stop()

    # Destroy the window while the QApplication is still alive; leaving both to
    # interpreter shutdown can tear them down in the wrong order and crash Qt.
    window.close()
    del window

    _LOGGER.info("Shutting down with code %d", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
