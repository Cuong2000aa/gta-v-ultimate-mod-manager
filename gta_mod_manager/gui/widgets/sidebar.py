"""The navigation sidebar."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gta_mod_manager.core import constants
from gta_mod_manager.gui.i18n import t


@dataclass(frozen=True, slots=True)
class NavItem:
    """One navigation entry.

    Attributes:
        key: Stable identifier matching a page in the stacked widget.
        label_key: i18n key for the sidebar label.
        section_key: Optional i18n key for the group heading above the entry.
    """

    key: str
    label_key: str
    section_key: str = ""


DEFAULT_NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("dashboard", "nav.dashboard", section_key="nav.overview"),
    NavItem("install", "nav.install", section_key="nav.mods"),
    NavItem("online", "nav.online"),
    NavItem("installed", "nav.installed"),
    NavItem("spawn", "nav.spawn"),
    NavItem("graphics", "nav.graphics"),
    NavItem("conflicts", "nav.conflicts"),
    NavItem("backup", "nav.backup", section_key="nav.safety"),
    NavItem("diagnostics", "nav.diagnostics"),
    NavItem("logs", "nav.logs"),
    NavItem("settings", "nav.settings", section_key="nav.application"),
)


class Sidebar(QFrame):
    """Vertical navigation with exclusive selection.

    Attributes:
        pageSelected: Emitted with the :attr:`NavItem.key` of the new page.
    """

    pageSelected = Signal(str)

    def __init__(
        self, items: tuple[NavItem, ...] = DEFAULT_NAV_ITEMS, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(232)
        self._items = items

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(0)

        title = QLabel(constants.APP_NAME.replace(" Ultimate", "\nUltimate"))
        title.setObjectName("AppTitle")
        layout.addWidget(title)

        self._subtitle = QLabel(t("chrome.safety_first", version=constants.APP_VERSION))
        self._subtitle.setObjectName("AppSubtitle")
        layout.addWidget(self._subtitle)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        self._section_labels: list[tuple[QLabel, str]] = []

        for item in items:
            if item.section_key:
                heading = QLabel(t(item.section_key).upper())
                heading.setObjectName("SidebarHeader")
                layout.addWidget(heading)
                self._section_labels.append((heading, item.section_key))
            layout.addWidget(self._make_button(item))

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout.addWidget(spacer)

        self._footer = QLabel(t("chrome.no_install"))
        self._footer.setObjectName("Hint")
        self._footer.setWordWrap(True)
        self._footer.setContentsMargins(18, 0, 18, 0)
        self._footer_is_default = True
        layout.addWidget(self._footer)

    def select(self, key: str) -> None:
        """Programmatically activate the page identified by ``key``."""
        button = self._buttons.get(key)
        if button is not None and not button.isChecked():
            button.setChecked(True)
            self.pageSelected.emit(key)

    def set_footer(self, text: str) -> None:
        """Update the footer line, used to show the active game folder."""
        self._footer.setText(text)
        self._footer_is_default = False

    def retranslate(self) -> None:
        """Refresh labels after the UI language changed."""
        self._subtitle.setText(t("chrome.safety_first", version=constants.APP_VERSION))
        for label, key in self._section_labels:
            label.setText(t(key).upper())
        for item in self._items:
            button = self._buttons.get(item.key)
            if button is not None:
                button.setText(t(item.label_key))
        if getattr(self, "_footer_is_default", True):
            self._footer.setText(t("chrome.no_install"))

    def _make_button(self, item: NavItem) -> QPushButton:
        """Create and wire one navigation button."""
        button = QPushButton(t(item.label_key))
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.clicked.connect(lambda: self.pageSelected.emit(item.key))
        self._group.addButton(button)
        self._buttons[item.key] = button
        return button
