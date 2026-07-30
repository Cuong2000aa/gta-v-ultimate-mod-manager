"""Installed-mods page: search, inspect, verify, uninstall."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.viewmodels.library_vm import LibraryViewModel
from gta_mod_manager.gui.widgets.cards import (
    BADGE_ERROR,
    BADGE_NEUTRAL,
    BADGE_OK,
    BADGE_WARNING,
    Badge,
    Card,
    page_header,
)
from gta_mod_manager.models.enums import ModStatus
from gta_mod_manager.models.mod_package import InstalledMod
from gta_mod_manager.services.library_service import ModSummary

_MOD_ID_ROLE = Qt.ItemDataRole.UserRole

_STATUS_BADGES: dict[ModStatus, tuple[str, str]] = {
    ModStatus.INSTALLED: ("Installed", BADGE_OK),
    ModStatus.DISABLED: ("Disabled", BADGE_NEUTRAL),
    ModStatus.BROKEN: ("Broken", BADGE_ERROR),
    ModStatus.AVAILABLE: ("Available", BADGE_NEUTRAL),
}


class LibraryView(QWidget):
    """Lists the mods the manager installed and tracks."""

    def __init__(self, view_model: LibraryViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._summaries: dict[str, ModSummary] = {}
        self._current_mod_id: str | None = None
        self._busy = False
        self._build()

        self._vm.modsLoaded.connect(self._render)
        self._vm.verificationDone.connect(self._on_verified)
        self._vm.busyChanged.connect(self._on_busy)
        self._vm.modRemoved.connect(self._on_removed)
        self._vm.statusChanged.connect(self._on_status)

    def refresh(self) -> None:
        """Reload the mod list."""
        self._vm.refresh()

    def show_progress(self, _operation: str, label: str, current: int, total: int) -> None:
        """Render a progress event while this page owns the running command."""
        if not self._busy:
            return
        self._progress_label.setText(label or "Working...")
        self._progress_label.setVisible(True)
        self._progress.setVisible(True)
        if total > 0:
            self._progress.setRange(0, total)
            self._progress.setValue(min(max(current, 0), total))
            self._progress.setFormat("%p%")
        else:
            self._progress.setRange(0, 0)
            self._progress.setFormat("Working...")

    def _on_status(self, message: str) -> None:
        """Mirror status lines onto the progress label while busy."""
        if self._busy and message:
            self._progress_label.setText(message)
            self._progress_label.setVisible(True)

    def _build(self) -> None:
        """Compose the page."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)

        layout.addWidget(page_header(t("library.title"), t("library.subtitle")))

        self._progress_label = QLabel("")
        self._progress_label.setObjectName("LibraryProgressLabel")
        self._progress_label.setWordWrap(True)
        self._progress_label.setVisible(False)
        layout.addWidget(self._progress_label)

        self._progress = QProgressBar()
        self._progress.setObjectName("LibraryProgress")
        self._progress.setTextVisible(True)
        self._progress.setFormat("%p%")
        self._progress.setMinimumHeight(22)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self._search = QLineEdit()
        self._search.setPlaceholderText(t("library.search_ph"))
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._vm.search)
        toolbar.addWidget(self._search, 1)

        refresh_button = QPushButton(t("common.refresh"))
        refresh_button.clicked.connect(self._vm.refresh)
        toolbar.addWidget(refresh_button)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_table())
        splitter.addWidget(self._build_details())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

    def _build_table(self) -> QWidget:
        """Build the mod table."""
        card = Card(t("library.card"))
        self._table = QTreeWidget()
        self._table.setColumnCount(6)
        self._table.setHeaderLabels(
            [
                t("library.col_mod"),
                t("library.col_category"),
                t("library.col_spawn"),
                t("library.col_files"),
                t("library.col_size"),
                t("library.col_status"),
            ]
        )
        self._table.setRootIsDecorated(False)
        self._table.setAlternatingRowColors(True)
        self._table.currentItemChanged.connect(self._on_selection)
        header = self._table.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for column in (1, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        card.body.addWidget(self._table)
        return card

    def _build_details(self) -> QWidget:
        """Build the detail panel with the per-mod actions."""
        card = Card(t("library.details"))

        head = QHBoxLayout()
        self._name_label = QLabel(t("library.select_mod"))
        self._name_label.setObjectName("CardValue")
        self._name_label.setWordWrap(True)
        head.addWidget(self._name_label, 1)
        self._status_badge = Badge("", BADGE_NEUTRAL)
        head.addWidget(self._status_badge, 0, Qt.AlignmentFlag.AlignTop)
        card.body.addLayout(head)

        self._meta_label = QLabel("")
        self._meta_label.setObjectName("Hint")
        self._meta_label.setWordWrap(True)
        card.body.addWidget(self._meta_label)

        self._files = QTreeWidget()
        self._files.setColumnCount(2)
        self._files.setHeaderLabels(["Installed content", "State"])
        self._files.setAlternatingRowColors(True)
        self._files.setRootIsDecorated(True)
        self._files.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._files.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        card.body.addWidget(self._files, 1)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self._verify_button = QPushButton(t("library.verify"))
        self._verify_button.clicked.connect(self._verify)
        actions.addWidget(self._verify_button)

        self._toggle_button = QPushButton(t("library.disable"))
        self._toggle_button.clicked.connect(self._toggle_enabled)
        actions.addWidget(self._toggle_button)

        self._remove_button = QPushButton(t("library.uninstall"))
        self._remove_button.setObjectName("DangerButton")
        self._remove_button.clicked.connect(self._uninstall)
        actions.addWidget(self._remove_button)
        actions.addStretch(1)
        card.body.addLayout(actions)

        self._set_actions_enabled(False)
        return card

    def _render(self, summaries: tuple[ModSummary, ...]) -> None:
        """Rebuild the table from ``summaries``."""
        selected = self._current_mod_id
        self._summaries = {summary.mod_id: summary for summary in summaries}
        self._table.clear()

        for summary in summaries:
            label, _kind = _STATUS_BADGES[summary.mod.status]
            spawn = ", ".join(summary.mod.spawn_codes) if summary.mod.spawn_codes else "—"
            item = QTreeWidgetItem(
                [
                    summary.display_name,
                    summary.mod.kind,
                    spawn,
                    str(summary.mod.file_count),
                    summary.size_label,
                    label if summary.is_intact else "Files missing",
                ]
            )
            item.setData(0, _MOD_ID_ROLE, summary.mod_id)
            if summary.mod.spawn_codes:
                item.setToolTip(
                    2,
                    "Type this in a trainer (Menyoo / Simple Trainer) to spawn the vehicle:\n"
                    + "\n".join(summary.mod.spawn_codes),
                )
            self._table.addTopLevelItem(item)
            if summary.mod_id == selected:
                self._table.setCurrentItem(item)

        if self._current_mod_id not in self._summaries:
            self._clear_details()
        elif self._table.currentItem() is not None:
            self._on_selection(self._table.currentItem())

    def _on_selection(self, current: QTreeWidgetItem | None, _previous: object = None) -> None:
        """Show the details of the selected mod."""
        if current is None:
            self._clear_details()
            return
        mod_id = current.data(0, _MOD_ID_ROLE)
        summary = self._summaries.get(str(mod_id) if mod_id is not None else "")
        if summary is None:
            self._clear_details()
            return

        self._current_mod_id = summary.mod_id
        mod = summary.mod
        label, badge = _STATUS_BADGES[mod.status]
        self._name_label.setText(mod.display_name)
        self._status_badge.set_state(
            label if summary.is_intact else "Files missing",
            badge if summary.is_intact else BADGE_WARNING,
        )
        self._meta_label.setText(
            f"{mod.kind} - installed {mod.installed_at:%Y-%m-%d %H:%M} - "
            f"{mod.file_count} file(s), {summary.size_label}"
            + (
                f"\nIn-game spawn: {', '.join(mod.spawn_codes)}"
                if mod.spawn_codes
                else ""
            )
            + (f"\nDLC packs: {', '.join(mod.dlc_packs)}" if mod.dlc_packs else "")
        )
        self._toggle_button.setText(
            t("library.enable") if mod.status is ModStatus.DISABLED else t("library.disable")
        )

        self._render_file_explorer(mod)
        self._set_actions_enabled(True)

    def _render_file_explorer(self, mod: InstalledMod) -> None:
        """Render the mod manifest as a navigable folder and archive tree."""
        self._files.clear()
        roots: dict[str, QTreeWidgetItem] = {}
        folders: dict[tuple[str, ...], QTreeWidgetItem] = {}

        for record in mod.installed_files:
            try:
                relative = record.target_path.relative_to(mod.game_root)
            except ValueError:
                relative = record.target_path
            parts = relative.parts
            if not parts:
                continue
            root_key = parts[0]
            root = roots.get(root_key)
            if root is None:
                root = QTreeWidgetItem([root_key, "folder"])
                roots[root_key] = root
                self._files.addTopLevelItem(root)

            parent = root
            folder_key = (root_key,)
            for part in parts[1:-1]:
                folder_key += (part,)
                child = folders.get(folder_key)
                if child is None:
                    child = QTreeWidgetItem([part, "folder"])
                    parent.addChild(child)
                    folders[folder_key] = child
                parent = child

            state = "installed" if record.target_path.exists() else "missing"
            file_item = QTreeWidgetItem([parts[-1], state])
            file_item.setToolTip(0, str(record.target_path))
            parent.addChild(file_item)
            for member in record.archive_members:
                member_item = QTreeWidgetItem([member, "archive member"])
                member_item.setToolTip(0, f"Inside {record.target_path.name}")
                file_item.addChild(member_item)

        if mod.vehicle_definitions:
            vehicles = QTreeWidgetItem(["Vehicles", "metadata"])
            self._files.addTopLevelItem(vehicles)
            for vehicle in mod.vehicle_definitions:
                details = [
                    value
                    for value in (
                        f"handling: {vehicle.handling_id}" if vehicle.handling_id else "",
                        vehicle.manufacturer or "",
                        vehicle.vehicle_class or "",
                    )
                    if value
                ]
                vehicle_item = QTreeWidgetItem(
                    [vehicle.spawn_code, "; ".join(details) or "spawn code"]
                )
                vehicle_item.setToolTip(
                    0,
                    "Spawn with this code in Menyoo / Simple Trainer: "
                    + vehicle.spawn_code,
                )
                vehicles.addChild(vehicle_item)

        self._files.expandToDepth(1)

    def _on_verified(self, mod_id: str, problems: tuple[str, ...]) -> None:
        """Report the verification outcome."""
        summary = self._summaries.get(mod_id)
        name = summary.display_name if summary else mod_id
        if not problems:
            QMessageBox.information(self, "Verification", f"{name}: every file is intact.")
            return
        QMessageBox.warning(
            self,
            "Verification",
            f"{name}: {len(problems)} problem(s) found.\n\n" + "\n".join(problems[:20]),
        )

    def _verify(self) -> None:
        """Verify the selected mod."""
        mod_id = self._selected_mod_id()
        if mod_id is None:
            QMessageBox.information(self, "Verify files", "Select a mod in the list first.")
            return
        self._vm.verify(mod_id)

    def _toggle_enabled(self) -> None:
        """Flip the enabled flag of the selected mod."""
        mod_id = self._selected_mod_id()
        summary = self._summaries.get(mod_id or "")
        if mod_id is None or summary is None:
            QMessageBox.information(self, "Enable / Disable", "Select a mod in the list first.")
            return
        self._vm.set_enabled(mod_id, summary.mod.status is ModStatus.DISABLED)

    def _uninstall(self) -> None:
        """Ask for confirmation, then remove the selected mod."""
        mod_id = self._selected_mod_id()
        summary = self._summaries.get(mod_id or "")
        if mod_id is None or summary is None:
            QMessageBox.information(self, "Uninstall mod", "Select a mod in the list first.")
            return

        staging_only = bool(summary.mod.installed_files) and all(
            "openiv-payload" in str(record.target_path).replace("\\", "/").lower()
            for record in summary.mod.installed_files
        )
        shared = [item for item in summary.mod.installed_files if item.shared_archive]
        if staging_only:
            detail = t("library.staging_detail")
        elif shared:
            detail = t("library.shared_detail")
        else:
            detail = t("library.plain_detail")
        answer = QMessageBox.question(
            self,
            t("library.uninstall_title"),
            t(
                "library.remove_confirm",
                name=summary.display_name,
                count=summary.mod.file_count,
                detail=detail,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        # PySide may return StandardButton or a plain int; never compare with `is`.
        if int(answer) != int(QMessageBox.StandardButton.Yes):
            return

        self._set_actions_enabled(False)
        self._start_progress(f"Removing {summary.display_name}...")
        self._vm.uninstall(mod_id)

    def _on_removed(self, mod_id: str) -> None:
        """Confirm removal after a successful uninstall."""
        if self._current_mod_id == mod_id:
            self._current_mod_id = None
        self._stop_progress()
        QMessageBox.information(
            self,
            t("library.uninstall_complete"),
            t("library.uninstall_complete_body"),
        )

    def _start_progress(self, label: str) -> None:
        """Show an indeterminate bar until the first real progress event."""
        self._busy = True
        self._progress_label.setText(label)
        self._progress_label.setVisible(True)
        self._progress.setRange(0, 0)
        self._progress.setFormat("Working...")
        self._progress.setVisible(True)

    def _stop_progress(self) -> None:
        """Hide the progress row."""
        self._busy = False
        self._progress.setVisible(False)
        self._progress_label.setVisible(False)
        self._progress_label.clear()

    def _on_busy(self, busy: bool) -> None:
        """Lock actions while a library command is running."""
        if busy:
            self._set_actions_enabled(False)
            # Keep an already-visible uninstall bar; don't hide it on busy flicker.
            return
        if not self._busy:
            if self._current_mod_id in self._summaries:
                self._set_actions_enabled(True)
            return
        self._stop_progress()
        if self._current_mod_id in self._summaries:
            self._set_actions_enabled(True)

    def _selected_mod_id(self) -> str | None:
        """Return the identifier of the selected mod, when there is one."""
        if self._current_mod_id and self._current_mod_id in self._summaries:
            return self._current_mod_id
        item = self._table.currentItem()
        if item is None:
            return None
        mod_id = item.data(0, _MOD_ID_ROLE)
        return str(mod_id) if mod_id is not None else None

    def _clear_details(self) -> None:
        """Reset the detail panel."""
        self._current_mod_id = None
        self._name_label.setText(t("library.select_mod"))
        self._status_badge.set_state("", BADGE_NEUTRAL)
        self._meta_label.clear()
        self._files.clear()
        self._set_actions_enabled(False)

    def _set_actions_enabled(self, enabled: bool) -> None:
        """Enable or disable the per-mod buttons."""
        for button in (self._verify_button, self._toggle_button, self._remove_button):
            button.setEnabled(enabled)
