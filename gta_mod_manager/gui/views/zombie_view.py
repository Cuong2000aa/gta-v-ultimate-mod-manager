"""Dedicated page for the Simple Zombies Reborn game mode."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.viewmodels.zombie_vm import ZombieViewModel
from gta_mod_manager.gui.widgets.cards import Card, page_header
from gta_mod_manager.models.zombie import ZombieModeStatus


class ZombieView(QWidget):
    """Install and explain the managed zombie survival mode."""

    def __init__(self, view_model: ZombieViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._build()
        self._vm.statusLoaded.connect(self._render_status)
        self._vm.busyChanged.connect(self._on_busy)
        self._vm.statusChanged.connect(self._status.setText)
        self._vm.errorRaised.connect(self._on_error)

    def refresh(self) -> None:
        """Reload current install state."""
        self._vm.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(page_header(t("zombie.title"), t("zombie.subtitle")))

        self._badge = QLabel(t("zombie.checking"))
        self._badge.setObjectName("Hint")
        self._badge.setWordWrap(True)
        layout.addWidget(self._badge)

        pack = Card(t("zombie.card_mode"))
        description = QLabel(t("zombie.description"))
        description.setObjectName("Hint")
        description.setWordWrap(True)
        pack.body.addWidget(description)
        actions = QHBoxLayout()
        self._install = QPushButton(t("zombie.install"))
        self._install.setObjectName("PrimaryButton")
        self._install.clicked.connect(self._vm.install)
        actions.addWidget(self._install)
        self._uninstall = QPushButton(t("zombie.uninstall"))
        self._uninstall.clicked.connect(self._vm.uninstall)
        actions.addWidget(self._uninstall)
        self._launch = QPushButton(t("zombie.launch"))
        self._launch.clicked.connect(self._vm.launch_game)
        actions.addWidget(self._launch)
        actions.addStretch(1)
        pack.body.addLayout(actions)
        layout.addWidget(pack)

        controls = Card(t("zombie.card_controls"))
        control_text = QLabel(t("zombie.controls"))
        control_text.setObjectName("Hint")
        control_text.setWordWrap(True)
        controls.body.addWidget(control_text)
        layout.addWidget(controls)

        notes = Card(t("zombie.card_notes"))
        note_text = QLabel(t("zombie.notes"))
        note_text.setObjectName("Hint")
        note_text.setWordWrap(True)
        notes.body.addWidget(note_text)
        layout.addWidget(notes)

        self._status = QLabel("")
        self._status.setObjectName("Hint")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        layout.addStretch(1)

    def _render_status(self, status: object) -> None:
        if not isinstance(status, ZombieModeStatus):
            return
        if status.ready:
            self._badge.setText(t("zombie.ready", version=status.version or ""))
        elif status.installed:
            missing = ", ".join(status.missing_dependencies)
            self._badge.setText(t("zombie.missing", dependencies=missing))
        else:
            self._badge.setText(t("zombie.not_installed"))
        self._status.setText(status.message)
        self._uninstall.setEnabled(status.installed)
        self._launch.setEnabled(status.ready)

    def _on_error(self, message: str) -> None:
        self._badge.setText(t("zombie.error"))
        self._status.setText(message)

    def _on_busy(self, busy: bool) -> None:
        enabled = not busy
        self._install.setEnabled(enabled)
        self._uninstall.setEnabled(enabled)
        self._launch.setEnabled(enabled)
        if not busy and self._vm.status is not None:
            self._render_status(self._vm.status)
