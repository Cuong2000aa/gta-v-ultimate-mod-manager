"""Dashboard: installation status, components and quick actions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.viewmodels.dashboard_vm import DashboardState, DashboardViewModel
from gta_mod_manager.gui.widgets.cards import (
    BADGE_ERROR,
    BADGE_NEUTRAL,
    BADGE_OK,
    BADGE_WARNING,
    Badge,
    Card,
    StatCard,
    page_header,
)
from gta_mod_manager.models.component import DetectedComponent
from gta_mod_manager.models.enums import ComponentStatus
from gta_mod_manager.models.essentials import EssentialAction, EssentialsStatus
from gta_mod_manager.models.launch import LaunchIssueSeverity, LaunchOutcome, LaunchPreflightReport

_COMPONENT_BADGES: dict[ComponentStatus, tuple[str, str]] = {
    ComponentStatus.INSTALLED: ("dashboard.comp_installed", BADGE_OK),
    ComponentStatus.OUTDATED: ("dashboard.comp_outdated", BADGE_WARNING),
    ComponentStatus.MISSING: ("dashboard.comp_missing", BADGE_NEUTRAL),
    ComponentStatus.UNKNOWN: ("dashboard.comp_unknown", BADGE_NEUTRAL),
}


class DashboardView(QWidget):
    """Shows what the manager knows about the active installation."""

    def __init__(self, view_model: DashboardViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._build()

        self._vm.stateLoaded.connect(self._render)
        self._vm.gameMissing.connect(self._render_missing)
        self._vm.preflightReady.connect(self._on_preflight)
        self._vm.launchFinished.connect(self._on_launched)
        self._vm.busyChanged.connect(self._on_busy)

    def refresh(self) -> None:
        """Reload the dashboard."""
        self._vm.refresh()

    def _build(self) -> None:
        """Compose the page."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(page_header(t("dashboard.title"), t("dashboard.subtitle")))
        layout.addWidget(self._build_install_card())
        layout.addLayout(self._build_stats())
        layout.addWidget(self._build_essentials_card())
        layout.addWidget(self._build_components_card())
        layout.addWidget(self._build_issues_card())
        layout.addStretch(1)

    def _build_install_card(self) -> Card:
        """Build the card describing the detected installation."""
        card = Card(t("dashboard.card_active"))

        header = QHBoxLayout()
        self._path_label = QLabel(t("dashboard.detecting"))
        self._path_label.setObjectName("CardValue")
        self._path_label.setWordWrap(True)
        header.addWidget(self._path_label, 1)

        self._ready_badge = Badge(t("dashboard.badge_checking"), BADGE_NEUTRAL)
        header.addWidget(self._ready_badge, 0, Qt.AlignmentFlag.AlignTop)
        card.body.addLayout(header)

        self._meta_label = QLabel("")
        self._meta_label.setObjectName("Hint")
        card.body.addWidget(self._meta_label)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self._choose_button = QPushButton(t("dashboard.change_folder"))
        self._choose_button.clicked.connect(self._choose_folder)
        actions.addWidget(self._choose_button)

        self._detect_button = QPushButton(t("dashboard.redetect"))
        self._detect_button.clicked.connect(self._vm.refresh)
        actions.addWidget(self._detect_button)

        self._mods_button = QPushButton(t("dashboard.create_mods"))
        self._mods_button.setObjectName("PrimaryButton")
        self._mods_button.setVisible(False)
        self._mods_button.clicked.connect(self._vm.create_mods_folder)
        actions.addWidget(self._mods_button)

        self._launch_button = QPushButton(t("dashboard.launch"))
        self._launch_button.setObjectName("PrimaryButton")
        self._launch_button.setEnabled(False)
        self._launch_button.clicked.connect(self._vm.run_preflight)
        actions.addWidget(self._launch_button)

        actions.addStretch(1)
        card.body.addLayout(actions)
        return card

    def _build_stats(self) -> QGridLayout:
        """Build the row of headline numbers."""
        grid = QGridLayout()
        grid.setSpacing(14)

        self._mods_card = StatCard(t("dashboard.stat_mods"), "-", t("dashboard.stat_mods_cap"))
        self._components_card = StatCard(
            t("dashboard.stat_components"), "-", t("dashboard.stat_components_cap")
        )
        self._backup_card = StatCard(
            t("dashboard.stat_backups"), "-", t("dashboard.stat_backups_cap")
        )

        for column, card in enumerate(
            (self._mods_card, self._components_card, self._backup_card)
        ):
            grid.addWidget(card, 0, column)
        return grid

    def _build_essentials_card(self) -> Card:
        """Build the Story Mode essentials kit card."""
        card = Card(t("dashboard.essentials_card"))
        self._essentials_status = QLabel(t("dashboard.essentials_waiting"))
        self._essentials_status.setObjectName("Hint")
        self._essentials_status.setWordWrap(True)
        card.body.addWidget(self._essentials_status)

        self._essentials_list = QListWidget()
        self._essentials_list.setMinimumHeight(180)
        card.body.addWidget(self._essentials_list)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self._essentials_install = QPushButton(t("dashboard.essentials_install"))
        self._essentials_install.setObjectName("PrimaryButton")
        self._essentials_install.clicked.connect(self._vm.install_essentials)
        actions.addWidget(self._essentials_install)

        self._essentials_manual = QPushButton(t("dashboard.essentials_manual"))
        self._essentials_manual.clicked.connect(self._vm.open_essentials_pages)
        actions.addWidget(self._essentials_manual)
        actions.addStretch(1)
        card.body.addLayout(actions)
        return card

    def _build_components_card(self) -> Card:
        """Build the component table."""
        card = Card(t("dashboard.card_components"))

        self._components = QTreeWidget()
        self._components.setColumnCount(4)
        self._components.setHeaderLabels(
            [
                t("dashboard.col_component"),
                t("dashboard.col_status"),
                t("dashboard.col_version"),
                t("dashboard.col_location"),
            ]
        )
        self._components.setRootIsDecorated(False)
        self._components.setAlternatingRowColors(True)
        self._components.setMinimumHeight(230)
        header = self._components.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        card.body.addWidget(self._components)
        return card

    def _build_issues_card(self) -> Card:
        """Build the validation issue list."""
        card = Card(t("dashboard.card_validation"))
        self._issues = QListWidget()
        self._issues.setMinimumHeight(90)
        card.body.addWidget(self._issues)
        return card

    def _render(self, state: DashboardState) -> None:
        """Fill every widget from ``state``."""
        self._path_label.setText(str(state.install.root_path))
        self._meta_label.setText(
            t(
                "dashboard.meta",
                platform=state.platform_label,
                version=state.version_label,
                source=state.install.detected_by,
            )
        )

        if state.issues and any(issue.is_fatal for issue in state.issues):
            self._ready_badge.set_state(t("dashboard.badge_not_ready"), BADGE_ERROR)
        elif state.issues:
            self._ready_badge.set_state(t("dashboard.badge_ready_warn"), BADGE_WARNING)
        else:
            self._ready_badge.set_state(t("dashboard.badge_ready"), BADGE_OK)

        self._mods_button.setVisible(not state.mods_folder_exists)
        self._launch_button.setEnabled(True)
        self._mods_card.set_value(str(state.installed_count))
        self._components_card.set_value(
            f"{sum(1 for item in state.components if item.is_installed)}"
            f"/{len(state.components)}",
            caption=(
                t("dashboard.components_all")
                if not state.missing
                else t("dashboard.components_missing", count=len(state.missing))
            ),
        )
        self._backup_card.set_value(str(state.snapshot_count))

        self._fill_components(state.components)
        self._fill_essentials(state.essentials)
        self._fill_issues(state)

    def _render_missing(self, message: str) -> None:
        """Show the empty state when no installation is known."""
        self._path_label.setText(t("dashboard.no_install"))
        self._meta_label.setText(message)
        self._ready_badge.set_state(t("dashboard.badge_not_detected"), BADGE_ERROR)
        self._mods_button.setVisible(False)
        self._launch_button.setEnabled(False)
        self._components.clear()
        self._issues.clear()
        self._issues.addItem(t("dashboard.pick_folder"))
        self._essentials_list.clear()
        self._essentials_status.setText(t("dashboard.essentials_waiting"))
        self._essentials_install.setEnabled(False)
        self._essentials_manual.setEnabled(False)
        for card in (self._mods_card, self._components_card, self._backup_card):
            card.set_value("-")

    def _fill_essentials(self, status: EssentialsStatus | None) -> None:
        """Render the essentials kit checklist."""
        self._essentials_list.clear()
        if status is None:
            self._essentials_status.setText(t("dashboard.essentials_waiting"))
            self._essentials_install.setEnabled(False)
            self._essentials_manual.setEnabled(False)
            return
        self._essentials_status.setText(status.message)
        for item in status.items:
            mark = (
                t("dashboard.essentials_mark_ok")
                if item.installed
                else t("dashboard.essentials_mark_missing")
            )
            self._essentials_list.addItem(f"[{mark}] {item.display_name} — {item.detail}")
        can_auto = any(
            not item.installed
            and item.action
            in (EssentialAction.AUTO_INSTALL, EssentialAction.CREATE_FOLDER)
            for item in status.items
        )
        can_manual = any(
            not item.installed and item.action is EssentialAction.OPEN_BROWSER
            for item in status.items
        )
        self._essentials_install.setEnabled(can_auto)
        self._essentials_manual.setEnabled(can_manual)

    def _fill_components(self, components: tuple[DetectedComponent, ...]) -> None:
        """Rebuild the component table."""
        self._components.clear()
        for component in components:
            label_key, _badge = _COMPONENT_BADGES[component.status]
            item = QTreeWidgetItem(
                [
                    component.display_name,
                    t(label_key),
                    component.version or "-",
                    str(component.location) if component.location else "-",
                ]
            )
            if component.is_missing_dependency:
                item.setToolTip(0, t("dashboard.essential_tip"))
            if component.details:
                item.setToolTip(1, component.details)
            self._components.addTopLevelItem(item)

    def _fill_issues(self, state: DashboardState) -> None:
        """Rebuild the validation list."""
        self._issues.clear()
        for issue in state.issues:
            prefix = (
                t("conflicts.sev_blocking") if issue.is_fatal else t("conflicts.sev_warning")
            )
            self._issues.addItem(f"[{prefix}] {issue.message}")
        for component in state.missing:
            self._issues.addItem(
                t("dashboard.missing_line", name=component.display_name)
                + (
                    t("dashboard.missing_line_url", url=component.spec.homepage)
                    if component.spec.homepage
                    else ""
                )
            )
        if self._issues.count() == 0:
            self._issues.addItem(t("dashboard.no_problems"))

    def _choose_folder(self) -> None:
        """Ask for the game folder and hand it to the view model."""
        folder = QFileDialog.getExistingDirectory(self, t("dashboard.select_game_folder"))
        if folder:
            self._vm.choose_game_folder(Path(folder))

    def _on_preflight(self, report: object) -> None:
        """Show the preflight result and offer to launch."""
        if not isinstance(report, LaunchPreflightReport):
            return
        if not report.can_launch:
            QMessageBox.warning(
                self,
                t("dashboard.launch_title"),
                t("dashboard.launch_no_exe"),
            )
            return
        if report.is_clean:
            self._vm.launch_game(force=False)
            return

        lines = [t("dashboard.launch_issues_intro", count=len(report.issues)), ""]
        for issue in report.issues[:12]:
            mark = "!" if issue.severity is LaunchIssueSeverity.ERROR else "*"
            lines.append(f"[{mark}] {issue.title}: {issue.detail}")
        if len(report.issues) > 12:
            lines.append(t("dashboard.launch_issues_more", count=len(report.issues) - 12))
        lines.append("")
        lines.append(t("dashboard.launch_anyway_hint"))

        answer = QMessageBox.question(
            self,
            t("dashboard.launch_title"),
            "\n".join(lines),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._vm.launch_game(force=True)

    def _on_launched(self, outcome: object) -> None:
        """Confirm the game process was started."""
        if isinstance(outcome, LaunchOutcome):
            QMessageBox.information(
                self,
                t("dashboard.launch_title"),
                t("dashboard.launch_started", exe=outcome.executable.name),
            )

    def _on_busy(self, busy: bool) -> None:
        """Disable launch / essentials while a background task runs."""
        if busy:
            self._launch_button.setEnabled(False)
            self._essentials_install.setEnabled(False)
            self._essentials_manual.setEnabled(False)
        elif self._path_label.text() and self._path_label.text() != t("dashboard.no_install"):
            self._launch_button.setEnabled(True)
