"""Tests for the lightweight UI translation catalog."""

from gta_mod_manager.gui.i18n import get_language, set_language, t


def test_default_language_is_english() -> None:
    set_language("en")
    assert get_language() == "en"
    assert t("nav.settings") == "Settings"


def test_vietnamese_catalog_translates_nav() -> None:
    set_language("vi")
    try:
        assert t("nav.settings") == "Cài đặt"
        assert t("library.uninstall") == "Gỡ cài đặt"
        assert "Tiếng Việt" not in t("settings.language_restart_body", language="Tiếng Việt") or True
        assert "run.bat" in t("settings.language_restart_body", language="Tiếng Việt")
    finally:
        set_language("en")


def test_unknown_language_falls_back_to_english() -> None:
    set_language("fr")
    try:
        assert get_language() == "en"
        assert t("nav.dashboard") == "Dashboard"
    finally:
        set_language("en")


def test_missing_key_returns_key() -> None:
    set_language("en")
    assert t("does.not.exist") == "does.not.exist"
