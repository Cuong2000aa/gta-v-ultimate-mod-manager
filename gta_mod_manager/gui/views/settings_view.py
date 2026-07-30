"""Settings page: installation selection, safety switches and paths."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.gui.i18n import (
    SUPPORTED_LANGUAGES,
    get_language,
    language_display_name,
    set_language,
    t,
)
from gta_mod_manager.gui.viewmodels.settings_vm import SettingsViewModel
from gta_mod_manager.gui.widgets.cards import Card, page_header
from gta_mod_manager.models.game_install import GameInstall, ValidationReport
from gta_mod_manager.models.settings import AppSettings

_ROOT_PATH_ROLE = Qt.ItemDataRole.UserRole


class SettingsView(QWidget):
    """Lets the user pick the installation and tune the safety behaviour."""

    def __init__(
        self,
        view_model: SettingsViewModel,
        paths: AppPaths,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._paths = paths
        self._loading = False
        self._build()

        self._vm.settingsLoaded.connect(self._render)
        self._vm.installsDetected.connect(self._render_installs)
        self._vm.folderValidated.connect(self._render_validation)
        self._vm.dataDirectoryMigrated.connect(self._data_directory_migrated)
        self._vm.errorRaised.connect(lambda _message: self._data_change.setEnabled(True))

    def refresh(self) -> None:
        """Reload the settings and re-run detection."""
        self._vm.refresh()
        self._vm.detect_installations()

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

        layout.addWidget(page_header(t("settings.title"), t("settings.subtitle")))
        layout.addWidget(self._build_installs_card())
        layout.addWidget(self._build_behaviour_card())
        layout.addWidget(self._build_paths_card())
        layout.addStretch(1)

    def _build_installs_card(self) -> Card:
        """Build the detection card."""
        card = Card(t("settings.installs"))

        self._installs = QTreeWidget()
        self._installs.setColumnCount(4)
        self._installs.setHeaderLabels(
            [
                t("settings.folder"),
                t("settings.platform"),
                t("settings.version"),
                t("settings.detected_by"),
            ]
        )
        self._installs.setRootIsDecorated(False)
        self._installs.setAlternatingRowColors(True)
        self._installs.setMinimumHeight(150)
        self._installs.itemDoubleClicked.connect(lambda *_: self._use_selected())
        header = self._installs.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        card.body.addWidget(self._installs)

        self._validation_label = QLabel("")
        self._validation_label.setObjectName("Hint")
        self._validation_label.setWordWrap(True)
        card.body.addWidget(self._validation_label)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        detect_button = QPushButton(t("settings.detect_again"))
        detect_button.clicked.connect(self._vm.detect_installations)
        actions.addWidget(detect_button)

        use_button = QPushButton(t("settings.use_selected"))
        use_button.setObjectName("PrimaryButton")
        use_button.clicked.connect(self._use_selected)
        actions.addWidget(use_button)

        browse_button = QPushButton(t("settings.choose_manually"))
        browse_button.clicked.connect(self._browse_game_folder)
        actions.addWidget(browse_button)
        actions.addStretch(1)
        card.body.addLayout(actions)
        return card

    def _build_behaviour_card(self) -> Card:
        """Build the safety-behaviour card."""
        card = Card(t("settings.behaviour"))
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._language = QComboBox()
        for code, label in SUPPORTED_LANGUAGES:
            self._language.addItem(label, code)
        self._language.currentIndexChanged.connect(self._on_language_changed)
        form.addRow(t("settings.language"), self._language)
        language_hint = QLabel(t("settings.language_hint"))
        language_hint.setObjectName("Hint")
        language_hint.setWordWrap(True)
        form.addRow("", language_hint)

        self._auto_backup = QCheckBox(t("settings.auto_backup"))
        self._auto_backup.toggled.connect(
            lambda value: self._save(auto_backup=value)
        )
        form.addRow(t("settings.backups"), self._auto_backup)
        backup_hint = QLabel(t("settings.auto_backup_hint"))
        backup_hint.setObjectName("Hint")
        backup_hint.setWordWrap(True)
        form.addRow("", backup_hint)

        self._confirm_root = QCheckBox(t("settings.confirm_root"))
        self._confirm_root.toggled.connect(
            lambda value: self._save(confirm_root_installs=value)
        )
        form.addRow(t("settings.safety"), self._confirm_root)

        self._keep_temp = QCheckBox(t("settings.keep_temp"))
        self._keep_temp.toggled.connect(
            lambda value: self._save(keep_extracted_temp=value)
        )
        form.addRow(t("settings.diagnostics"), self._keep_temp)

        self._crash_monitor = QCheckBox(t("settings.crash_monitor"))
        self._crash_monitor.toggled.connect(
            lambda value: self._save(crash_monitor_enabled=value)
        )
        form.addRow(t("settings.crash_monitor_label"), self._crash_monitor)
        crash_hint = QLabel(t("settings.crash_monitor_hint"))
        crash_hint.setObjectName("Hint")
        crash_hint.setWordWrap(True)
        form.addRow("", crash_hint)

        self._generations = QSpinBox()
        self._generations.setRange(1, 100)
        self._generations.valueChanged.connect(
            lambda value: self._save(max_backup_generations=value)
        )
        form.addRow(t("settings.snapshots_kept"), self._generations)

        seven_zip_row = QHBoxLayout()
        self._seven_zip = QLineEdit()
        self._seven_zip.setPlaceholderText(t("settings.seven_zip_ph"))
        self._seven_zip.editingFinished.connect(self._save_seven_zip)
        seven_zip_row.addWidget(self._seven_zip, 1)
        seven_zip_button = QPushButton(t("common.browse"))
        seven_zip_button.clicked.connect(self._browse_seven_zip)
        seven_zip_row.addWidget(seven_zip_button)
        form.addRow(t("settings.seven_zip"), seven_zip_row)

        unrar_row = QHBoxLayout()
        self._unrar = QLineEdit()
        self._unrar.setPlaceholderText(t("settings.unrar_ph"))
        self._unrar.editingFinished.connect(self._save_unrar)
        unrar_row.addWidget(self._unrar, 1)
        unrar_button = QPushButton(t("common.browse"))
        unrar_button.clicked.connect(self._browse_unrar)
        unrar_row.addWidget(unrar_button)
        form.addRow(t("settings.unrar"), unrar_row)

        self._nexus_key = QLineEdit()
        self._nexus_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._nexus_key.setPlaceholderText(t("settings.nexus_api_key_ph"))
        self._nexus_key.editingFinished.connect(self._save_nexus_key)
        form.addRow(t("settings.nexus_api_key"), self._nexus_key)
        nexus_hint = QLabel(t("settings.nexus_api_key_hint"))
        nexus_hint.setObjectName("Hint")
        nexus_hint.setWordWrap(True)
        nexus_hint.setOpenExternalLinks(True)
        form.addRow("", nexus_hint)

        card.body.addLayout(form)
        return card

    def _build_paths_card(self) -> Card:
        """Build the working-folder card."""
        card = Card(t("settings.working_folders"))
        data_row = QHBoxLayout()
        self._data_path = QLabel(f"{t('settings.app_data')}: {self._paths.root}")
        self._data_path.setObjectName("Hint")
        self._data_path.setWordWrap(True)
        data_row.addWidget(self._data_path, 1)
        data_open = QPushButton(t("common.open"))
        data_open.clicked.connect(lambda: self._open(self._paths.root))
        data_row.addWidget(data_open)
        self._data_change = QPushButton(t("settings.change_data_folder"))
        self._data_change.clicked.connect(self._browse_data_folder)
        data_row.addWidget(self._data_change)
        card.body.addLayout(data_row)

        data_hint = QLabel(t("settings.data_folder_hint"))
        data_hint.setObjectName("Hint")
        data_hint.setWordWrap(True)
        card.body.addWidget(data_hint)

        for label_key, path in (
            ("settings.logs", self._paths.logs),
            ("settings.backups_folder", self._paths.backup),
            ("settings.temp", self._paths.temp),
            ("settings.config", self._paths.config),
        ):
            row = QHBoxLayout()
            caption = QLabel(f"{t(label_key)}: {path}")
            caption.setObjectName("Hint")
            caption.setWordWrap(True)
            row.addWidget(caption, 1)
            open_button = QPushButton(t("common.open"))
            open_button.clicked.connect(lambda _checked=False, target=path: self._open(target))
            row.addWidget(open_button)
            card.body.addLayout(row)
        return card

    def _browse_data_folder(self) -> None:
        """Choose an empty destination and confirm the two-phase move."""
        selected = QFileDialog.getExistingDirectory(
            self,
            t("settings.data_folder_title"),
            str(self._paths.root.parent),
            QFileDialog.Option.ShowDirsOnly,
        )
        if not selected:
            return
        destination = Path(selected)
        # Selecting a drive root means "put the app's folder on this drive".
        if destination == Path(destination.anchor):
            destination /= "GtaVUltimateModManager"
        answer = QMessageBox.question(
            self,
            t("settings.data_move_title"),
            t(
                "settings.data_move_body",
                source=self._paths.root,
                destination=destination,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._data_change.setEnabled(False)
            self._vm.change_data_directory(destination)

    def _data_directory_migrated(self, migration: object) -> None:
        """Tell the user the switch is ready, then close cleanly."""
        destination = getattr(migration, "destination", "")
        QMessageBox.information(
            self,
            t("settings.data_move_done_title"),
            t("settings.data_move_done_body", destination=destination),
        )
        QApplication.quit()

    def _render(self, settings: AppSettings) -> None:
        """Fill the widgets from ``settings`` without re-triggering saves."""
        self._loading = True
        try:
            index = self._language.findData(settings.language)
            if index < 0:
                index = self._language.findData("en")
            if index >= 0:
                self._language.setCurrentIndex(index)
            self._auto_backup.setChecked(settings.auto_backup)
            self._confirm_root.setChecked(settings.confirm_root_installs)
            self._keep_temp.setChecked(settings.keep_extracted_temp)
            self._crash_monitor.setChecked(settings.crash_monitor_enabled)
            self._generations.setValue(settings.max_backup_generations)
            self._seven_zip.setText(
                str(settings.seven_zip_path) if settings.seven_zip_path else ""
            )
            self._unrar.setText(str(settings.unrar_path) if settings.unrar_path else "")
            self._nexus_key.setText(settings.nexus_api_key)
            if settings.game_root is not None:
                self._vm.validate_folder(settings.game_root)
        finally:
            self._loading = False

    def _on_language_changed(self, _index: int) -> None:
        """Persist the language and ask the user to restart."""
        if self._loading:
            return
        code = str(self._language.currentData() or "en")
        if code == get_language():
            return
        set_language(code)
        self._save(language=code)
        QMessageBox.information(
            self,
            t("settings.language_restart_title"),
            t(
                "settings.language_restart_body",
                language=language_display_name(code),
            ),
        )

    def _render_installs(self, installs: tuple[GameInstall, ...]) -> None:
        """Rebuild the detection table."""
        self._installs.clear()
        for install in installs:
            item = QTreeWidgetItem(
                [
                    str(install.root_path),
                    install.platform.display_name,
                    install.version or "unknown",
                    install.detected_by,
                ]
            )
            item.setData(0, _ROOT_PATH_ROLE, str(install.root_path))
            self._installs.addTopLevelItem(item)
        first = self._installs.topLevelItem(0)
        if first is not None:
            self._installs.setCurrentItem(first)
        else:
            self._validation_label.setText(
                "Nothing detected automatically - choose the folder containing GTA5.exe."
            )

    def _render_validation(self, path: str, report: ValidationReport) -> None:
        """Summarise a validation report under the table."""
        if report.is_valid and not report.issues:
            self._validation_label.setText(f"{path}: valid installation.")
            return
        prefix = "valid with warnings" if report.is_valid else "not usable"
        self._validation_label.setText(
            f"{path}: {prefix} - "
            + "; ".join(issue.message for issue in report.issues[:4])
        )

    def _use_selected(self) -> None:
        """Make the highlighted installation the active one."""
        item = self._installs.currentItem()
        if item is None:
            return
        self._vm.select_game(Path(item.data(0, _ROOT_PATH_ROLE)))

    def _browse_game_folder(self) -> None:
        """Pick the game folder manually."""
        folder = QFileDialog.getExistingDirectory(self, "Select the GTA V folder")
        if folder:
            self._vm.select_game(Path(folder))

    def _browse_seven_zip(self) -> None:
        """Pick the external 7-Zip executable."""
        selected, _filter = QFileDialog.getOpenFileName(
            self, "Select 7z.exe", "", "Executables (*.exe);;All files (*)"
        )
        if selected:
            self._seven_zip.setText(selected)
            self._save(seven_zip_path=Path(selected))

    def _save_seven_zip(self) -> None:
        """Persist the manually typed 7-Zip path."""
        text = self._seven_zip.text().strip()
        self._save(seven_zip_path=Path(text) if text else None)

    def _browse_unrar(self) -> None:
        """Pick the external UnRAR executable."""
        selected, _filter = QFileDialog.getOpenFileName(
            self, "Select UnRAR.exe", "", "Executables (*.exe);;All files (*)"
        )
        if selected:
            self._unrar.setText(selected)
            self._save(unrar_path=Path(selected))

    def _save_unrar(self) -> None:
        """Persist the manually typed UnRAR path."""
        text = self._unrar.text().strip()
        self._save(unrar_path=Path(text) if text else None)

    def _save_nexus_key(self) -> None:
        """Persist the Nexus Mods API key."""
        self._save(nexus_api_key=self._nexus_key.text().strip())

    def _save(self, **changes: object) -> None:
        """Persist a change unless the widgets are being populated."""
        if not self._loading:
            self._vm.update(**changes)

    @staticmethod
    def _open(path: Path) -> None:
        """Reveal ``path`` in the system file browser."""
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
