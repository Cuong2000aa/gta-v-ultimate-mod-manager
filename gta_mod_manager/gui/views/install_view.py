"""Install page: drop a mod, review the plan, confirm."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gta_mod_manager.core import constants
from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.viewmodels.install_vm import InstallViewModel
from gta_mod_manager.gui.widgets.cards import (
    BADGE_NEUTRAL,
    BADGE_OK,
    BADGE_WARNING,
    Badge,
    Card,
    page_header,
)
from gta_mod_manager.gui.widgets.drop_area import DropArea
from gta_mod_manager.models.enums import ConflictSeverity, InstallTarget, ModKind
from gta_mod_manager.services.install_service import InstallPreview
from gta_mod_manager.utils import fs

_PREVIEW_MAX_WIDTH = 320

_ZONE_KEYS: dict[str, str] = {
    InstallTarget.MODS_FOLDER.value: "install.zone_mods",
    InstallTarget.DLC_PACKS.value: "install.zone_dlc",
    InstallTarget.SCRIPTS_FOLDER.value: "install.zone_scripts",
    InstallTarget.LML_FOLDER.value: "install.zone_lml",
    InstallTarget.GAME_ROOT.value: "install.zone_root",
    InstallTarget.EXTERNAL.value: "install.zone_external",
}

_KIND_KEYS: dict[ModKind, str] = {
    ModKind.VEHICLE_ADDON: "install.kind_vehicle_addon",
    ModKind.VEHICLE_REPLACE: "install.kind_vehicle_replace",
    ModKind.PED: "install.kind_ped",
    ModKind.WEAPON: "install.kind_weapon",
    ModKind.MAP: "install.kind_map",
    ModKind.SCRIPT: "install.kind_script",
    ModKind.ASI: "install.kind_asi",
    ModKind.SCRIPT_HOOK_DOTNET: "install.kind_script_hook_dotnet",
    ModKind.GRAPHICS: "install.kind_graphics",
    ModKind.LML: "install.kind_lml",
    ModKind.OPENIV_PACKAGE: "install.kind_openiv_package",
    ModKind.MENYOO: "install.kind_menyoo",
    ModKind.TRAINER: "install.kind_trainer",
    ModKind.ZOMBIE: "install.kind_zombie",
    ModKind.SOUND: "install.kind_sound",
    ModKind.TEXTURE: "install.kind_texture",
    ModKind.UNKNOWN: "install.kind_unknown",
}


def _kind_label(kind: ModKind) -> str:
    """Return a friendly i18n label for an analyzer kind."""
    return t(_KIND_KEYS.get(kind, "install.kind_unknown"))


def _spawn_source_label(source: Path | None) -> str:
    """Return a short label describing where a spawn code came from."""
    if source is None:
        return "DLC pack"
    name = source.name.lower()
    if name.endswith((".txt", ".md", ".nfo", ".rtf")):
        return "Readme"
    if name.endswith(".meta"):
        return "vehicles.meta"
    if name.endswith(".rpf"):
        return "dlc.rpf"
    if name.endswith((".yft", ".ytd")):
        return "model file"
    return source.suffix.lstrip(".") or "package"


class InstallView(QWidget):
    """Drives one installation from import to confirmation."""

    def __init__(self, view_model: InstallViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._loading_variants = False
        self._build()

        self._vm.previewReady.connect(self._render_preview)
        self._vm.installFinished.connect(self._on_installed)
        self._vm.cleared.connect(self._reset)
        self._vm.busyChanged.connect(self._on_busy)

    def load_source(self, source: Path) -> None:
        """Analyse ``source``; used by the window-level drag and drop."""
        self._vm.analyze(source)

    def _build(self) -> None:
        """Compose the page."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)

        layout.addWidget(
            page_header(t("install.title"), t("install.subtitle"))
        )

        self._drop = DropArea()
        self._drop.fileDropped.connect(self._vm.analyze)
        self._drop.browseRequested.connect(self._browse)
        layout.addWidget(self._drop)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._build_plan_panel())
        self._splitter.addWidget(self._build_details_panel())
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        self._splitter.setVisible(False)
        layout.addWidget(self._splitter, 1)

        layout.addLayout(self._build_actions())

    def _build_plan_panel(self) -> QWidget:
        """Build the left panel holding the operation table."""
        card = Card(t("install.card_plan"))

        self._operations = QTreeWidget()
        self._operations.setColumnCount(4)
        self._operations.setHeaderLabels(
            [
                t("install.col_action"),
                t("install.col_zone"),
                t("install.col_target"),
                t("install.col_detail"),
            ]
        )
        self._operations.setRootIsDecorated(False)
        self._operations.setAlternatingRowColors(True)
        header = self._operations.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        card.body.addWidget(self._operations)
        return card

    def _build_details_panel(self) -> QWidget:
        """Build the right panel with the package summary and tabs."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        summary = Card(t("install.card_package"))
        head = QHBoxLayout()
        self._name_label = QLabel("-")
        self._name_label.setObjectName("CardValue")
        self._name_label.setWordWrap(True)
        head.addWidget(self._name_label, 1)
        self._kind_badge = Badge("", BADGE_NEUTRAL)
        head.addWidget(self._kind_badge, 0, Qt.AlignmentFlag.AlignTop)
        summary.body.addLayout(head)

        self._summary_label = QLabel("")
        self._summary_label.setObjectName("Hint")
        self._summary_label.setWordWrap(True)
        summary.body.addWidget(self._summary_label)

        self._variant_box = QWidget()
        variant_layout = QVBoxLayout(self._variant_box)
        variant_layout.setContentsMargins(0, 8, 0, 0)
        variant_layout.setSpacing(6)
        variant_hint = QLabel(t("install.variant_hint"))
        variant_hint.setObjectName("Hint")
        variant_hint.setWordWrap(True)
        variant_layout.addWidget(variant_hint)
        checks = QHBoxLayout()
        checks.setSpacing(16)
        self._addon_check = QCheckBox(t("install.variant_addon"))
        self._replace_check = QCheckBox(t("install.variant_replace"))
        self._addon_check.toggled.connect(self._on_variant_toggled)
        self._replace_check.toggled.connect(self._on_variant_toggled)
        checks.addWidget(self._addon_check)
        checks.addWidget(self._replace_check)
        checks.addStretch(1)
        variant_layout.addLayout(checks)
        self._variant_box.setVisible(False)
        summary.body.addWidget(self._variant_box)

        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setVisible(False)
        summary.body.addWidget(self._image)
        layout.addWidget(summary)

        self._tabs = QTabWidget()
        self._vehicles = QTreeWidget()
        self._vehicles.setColumnCount(4)
        self._vehicles.setHeaderLabels(
            [t("library.col_spawn"), t("install.col_vehicle_source"), t("install.col_vehicle_handling"), t("install.col_vehicle_make")]
        )
        self._vehicles.setRootIsDecorated(False)
        self._vehicles.setAlternatingRowColors(True)
        vehicles_header = self._vehicles.header()
        vehicles_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        vehicles_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        vehicles_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        vehicles_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._tabs.addTab(self._vehicles, t("install.tab_vehicles"))
        self._conflicts = self._add_list_tab(t("install.tab_conflicts"))
        self._manual = self._add_list_tab(t("install.tab_manual"))
        self._evidence = self._add_list_tab(t("install.tab_evidence"))
        self._readme = QTextEdit()
        self._readme.setReadOnly(True)
        self._tabs.addTab(self._readme, t("install.tab_readme"))
        layout.addWidget(self._tabs, 1)
        return container

    def _add_list_tab(self, title: str) -> QListWidget:
        """Add a plain list tab and return its widget."""
        widget = QListWidget()
        widget.setWordWrap(True)
        self._tabs.addTab(widget, title)
        return widget

    def _build_actions(self) -> QHBoxLayout:
        """Build the confirm / discard button row."""
        row = QHBoxLayout()
        row.setSpacing(8)

        self._blocking_label = QLabel("")
        self._blocking_label.setObjectName("Hint")
        self._blocking_label.setWordWrap(True)
        row.addWidget(self._blocking_label, 1)

        self._discard_button = QPushButton(t("install.discard"))
        self._discard_button.setEnabled(False)
        self._discard_button.clicked.connect(self._vm.clear)
        row.addWidget(self._discard_button)

        self._install_button = QPushButton(t("install.confirm"))
        self._install_button.setObjectName("PrimaryButton")
        self._install_button.setEnabled(False)
        self._install_button.clicked.connect(self._vm.confirm)
        row.addWidget(self._install_button)
        return row

    def _browse(self) -> None:
        """Ask for an archive to analyse."""
        patterns = " ".join(f"*{suffix}" for suffix in sorted(constants.ARCHIVE_EXTENSIONS))
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            t("install.select_archive"),
            "",
            t("install.file_filter", patterns=patterns),
        )
        if selected:
            self._vm.analyze(Path(selected))

    def _render_preview(self, preview: InstallPreview) -> None:
        """Fill the page from a freshly built preview."""
        package = preview.package
        plan = preview.plan
        classification = package.classification

        self._splitter.setVisible(True)
        self._name_label.setText(package.display_name)
        self._kind_badge.set_state(
            _kind_label(classification.primary),
            BADGE_OK if classification.is_reliable else BADGE_WARNING,
        )
        self._kind_badge.setToolTip(
            t(
                "install.kind_confidence",
                kind=_kind_label(classification.primary),
                confidence=f"{classification.score:.0%}",
            )
        )
        self._summary_label.setText(
            t(
                "install.summary",
                files=len(package.files),
                size=fs.human_size(package.total_size),
                ops=len(plan.operations),
                write=fs.human_size(plan.total_bytes),
            )
            + (
                t("install.summary_root", count=len(plan.root_operations))
                if plan.root_operations
                else ""
            )
            + (
                t("install.summary_spawn", codes=", ".join(package.vehicles.spawn_codes))
                if package.vehicles.spawn_codes
                else ""
            )
        )
        self._render_image(package.preview_image)
        self._sync_variant_checks(preview)
        self._fill_operations()
        self._fill_vehicles(preview)
        self._fill_conflicts(preview)
        self._fill_manual_steps(preview)
        self._fill_evidence(preview)
        self._fill_readme(preview)

        self._discard_button.setEnabled(True)
        self._install_button.setEnabled(preview.is_installable)
        if preview.needs_variant_choice and not preview.variants.any_selected:
            self._blocking_label.setText(t("install.variant_required"))
        else:
            self._blocking_label.setText(
                "" if preview.is_installable else " | ".join(preview.blocking_reasons)
            )

    def _sync_variant_checks(self, preview: InstallPreview) -> None:
        """Show or hide the Add-On / Replace checkboxes for dual packages."""
        show = preview.needs_variant_choice
        self._variant_box.setVisible(show)
        if not show:
            return
        self._loading_variants = True
        try:
            self._addon_check.setChecked(preview.variants.addon)
            self._replace_check.setChecked(preview.variants.replace)
        finally:
            self._loading_variants = False

    def _on_variant_toggled(self, _checked: bool = False) -> None:
        """Rebuild the plan when the user changes Add-On / Replace."""
        if self._loading_variants:
            return
        self._vm.set_variants(
            addon=self._addon_check.isChecked(),
            replace=self._replace_check.isChecked(),
        )

    def _render_image(self, image: Path | None) -> None:
        """Show the package preview picture when it could be loaded."""
        if image is None:
            self._image.setVisible(False)
            return
        pixmap = QPixmap(str(image))
        if pixmap.isNull():
            self._image.setVisible(False)
            return
        self._image.setPixmap(
            pixmap.scaledToWidth(
                _PREVIEW_MAX_WIDTH, Qt.TransformationMode.SmoothTransformation
            )
        )
        self._image.setVisible(True)

    def _fill_operations(self) -> None:
        """Rebuild the operation table from the view model rows."""
        self._operations.clear()
        for row in self._vm.preview_rows():
            zone_key = _ZONE_KEYS.get(row.zone)
            item = QTreeWidgetItem(
                [
                    row.action,
                    t(zone_key) if zone_key else row.zone,
                    row.target,
                    row.detail,
                ]
            )
            if row.zone != InstallTarget.MODS_FOLDER.value:
                item.setToolTip(1, t("install.zone_outside_tip"))
            self._operations.addTopLevelItem(item)

    def _fill_vehicles(self, preview: InstallPreview) -> None:
        """List the vehicles and DLC packs found in the package."""
        self._vehicles.clear()
        manifest = preview.package.vehicles
        for vehicle in manifest.vehicles:
            source = _spawn_source_label(vehicle.source_file)
            item = QTreeWidgetItem(
                [
                    vehicle.spawn_code,
                    source,
                    vehicle.handling_id or "—",
                    vehicle.manufacturer or "—",
                ]
            )
            item.setToolTip(0, t("install.spawn_tip", code=vehicle.spawn_code))
            if vehicle.source_file is not None:
                item.setToolTip(1, str(vehicle.source_file.name))
            self._vehicles.addTopLevelItem(item)
        for pack in manifest.dlc_packs:
            item = QTreeWidgetItem(
                [f"[DLC] {pack.pack_name}", "DLC pack", "—", pack.dlclist_entry]
            )
            item.setToolTip(0, t("install.dlc_tip", entry=pack.dlclist_entry))
            self._vehicles.addTopLevelItem(item)
        if self._vehicles.topLevelItemCount() == 0:
            self._vehicles.addTopLevelItem(
                QTreeWidgetItem([t("install.no_vehicle_meta"), "—", "—", "—"])
            )
        self._tabs.setTabText(0, t("install.tab_vehicles_n", count=len(manifest.vehicles)))

    def _fill_conflicts(self, preview: InstallPreview) -> None:
        """List the conflicts detected against the current game state."""
        self._conflicts.clear()
        for conflict in preview.plan.conflicts.conflicts:
            marker = (
                t("conflicts.sev_blocking")
                if conflict.severity is ConflictSeverity.BLOCKING
                else t("conflicts.sev_warning")
            )
            hint = f" -> {conflict.resolution_hint}" if conflict.resolution_hint else ""
            self._conflicts.addItem(f"[{marker}] {conflict.description}{hint}")
        for warning in preview.plan.dependency_warnings:
            self._conflicts.addItem(f"[{t('conflicts.sev_warning')}] {warning}")
        if self._conflicts.count() == 0:
            self._conflicts.addItem(t("conflicts.none"))
        self._tabs.setTabText(
            1, t("install.tab_conflicts_n", count=len(preview.plan.conflicts.conflicts))
        )

    def _fill_manual_steps(self, preview: InstallPreview) -> None:
        """List the steps the safety rule leaves to the user."""
        self._manual.clear()
        for step in preview.plan.manual_steps:
            target = f" (target: {step.target_hint})" if step.target_hint else ""
            self._manual.addItem(f"{step.title}{target}\n{step.instruction}")
        if self._manual.count() == 0:
            self._manual.addItem(t("install.installs_auto"))
        self._tabs.setTabText(
            2, t("install.tab_manual_n", count=len(preview.plan.manual_steps))
        )

    def _fill_evidence(self, preview: InstallPreview) -> None:
        """Explain the classification so the verdict is auditable."""
        self._evidence.clear()
        for evidence in preview.package.classification.evidence:
            self._evidence.addItem(
                f"{evidence.weight:+.2f}  {evidence.description}  [{evidence.rule_id}]"
            )
        for note in preview.plan.notes:
            self._evidence.addItem(f"note: {note}")
        if self._evidence.count() == 0:
            self._evidence.addItem(t("install.no_markers"))

    def _fill_readme(self, preview: InstallPreview) -> None:
        """Show the shipped documentation, with spawn codes called out on top."""
        excerpts = preview.package.readmes
        spawn_codes = preview.package.vehicles.spawn_codes
        header = ""
        if spawn_codes:
            header = t("install.readme_spawn", codes=", ".join(spawn_codes))
        if not excerpts:
            self._readme.setPlainText(header + t("install.no_readme"))
            self._tabs.setTabText(4, t("install.tab_readme"))
            return
        body = "\n\n".join(f"--- {item.source.name} ---\n{item.text}" for item in excerpts)
        self._readme.setPlainText(header + body)
        self._tabs.setTabText(4, t("install.tab_readme_n", count=len(excerpts)))

    def _on_installed(self, _report: object) -> None:
        """Clear the page after a successful installation."""
        self._reset()

    def _reset(self) -> None:
        """Return the page to its empty state."""
        self._splitter.setVisible(False)
        self._operations.clear()
        self._install_button.setEnabled(False)
        self._discard_button.setEnabled(False)
        self._blocking_label.clear()
        self._image.setVisible(False)
        self._variant_box.setVisible(False)
        self._loading_variants = True
        try:
            self._addon_check.setChecked(False)
            self._replace_check.setChecked(False)
        finally:
            self._loading_variants = False

    def _on_busy(self, busy: bool) -> None:
        """Disable the drop area while a task is running."""
        self._drop.setEnabled(not busy)
        if busy:
            self._install_button.setEnabled(False)
        elif self._vm.preview is not None:
            self._install_button.setEnabled(self._vm.preview.is_installable)
