"""Graphics page: install / switch / remove NCCVision cinematic levels."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.viewmodels.graphics_vm import GraphicsViewModel
from gta_mod_manager.gui.widgets.cards import (
    BADGE_ERROR,
    BADGE_NEUTRAL,
    BADGE_OK,
    BADGE_WARNING,
    Badge,
    Card,
    page_header,
)
from gta_mod_manager.models.graphics import GraphicsStatus


class GraphicsView(QWidget):
    """UI for the bundled NCCVision graphics pack."""

    def __init__(self, view_model: GraphicsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._build()
        self._vm.statusLoaded.connect(self._render_status)
        self._vm.busyChanged.connect(self._on_busy)
        self._vm.statusChanged.connect(self._on_status_line)
        self._vm.errorRaised.connect(self._on_error)

    def refresh(self) -> None:
        """Reload install status."""
        self._vm.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(page_header(t("graphics.title"), t("graphics.subtitle")))

        status_row = QHBoxLayout()
        self._badge = Badge(t("graphics.badge_short_missing"), BADGE_NEUTRAL)
        status_row.addWidget(self._badge)
        status_row.addStretch(1)
        layout.addLayout(status_row)

        self._badge_detail = QLabel(t("graphics.status_unknown"))
        self._badge_detail.setObjectName("Hint")
        self._badge_detail.setWordWrap(True)
        layout.addWidget(self._badge_detail)

        pack = Card(t("graphics.card_pack"))
        pack_body = QLabel(t("graphics.pack.nccvision.desc"))
        pack_body.setObjectName("Hint")
        pack_body.setWordWrap(True)
        pack.body.addWidget(pack_body)
        layout.addWidget(pack)

        actions = QHBoxLayout()
        self._install = QPushButton(t("graphics.install"))
        self._install.setObjectName("PrimaryButton")
        self._install.clicked.connect(self._vm.install)
        actions.addWidget(self._install)

        self._uninstall = QPushButton(t("graphics.uninstall"))
        self._uninstall.clicked.connect(self._vm.uninstall)
        actions.addWidget(self._uninstall)
        actions.addStretch(1)
        layout.addLayout(actions)

        self._status = QLabel("")
        self._status.setObjectName("Hint")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        textures = Card(t("graphics.card_textures"))
        texture_hint = QLabel(t("graphics.road_2k.hint"))
        texture_hint.setObjectName("Hint")
        texture_hint.setWordWrap(True)
        textures.body.addWidget(texture_hint)
        texture_actions = QHBoxLayout()
        self._install_road_2k = QPushButton(t("graphics.road_2k.install"))
        self._install_road_2k.clicked.connect(self._vm.install_road_2k)
        texture_actions.addWidget(self._install_road_2k)
        self._uninstall_road_2k = QPushButton(t("graphics.road_2k.uninstall"))
        self._uninstall_road_2k.clicked.connect(self._vm.uninstall_road_2k)
        texture_actions.addWidget(self._uninstall_road_2k)
        texture_actions.addStretch(1)
        textures.body.addLayout(texture_actions)
        layout.addWidget(textures)

        tips = Card(t("graphics.card_tips"))
        tip = QLabel(t("graphics.tips"))
        tip.setObjectName("Hint")
        tip.setWordWrap(True)
        tips.body.addWidget(tip)
        layout.addWidget(tips)
        layout.addStretch(1)

    def _render_status(self, status: object) -> None:
        if not isinstance(status, GraphicsStatus):
            return
        if status.conflict_enb:
            self._badge.set_state(t("graphics.badge_short_conflict"), BADGE_ERROR)
            self._badge_detail.setText(t("graphics.badge_conflict"))
        elif status.installed:
            self._badge.set_state(t("graphics.badge_short_installed"), BADGE_OK)
            self._badge_detail.setText(t("graphics.badge_installed"))
        else:
            self._badge.set_state(t("graphics.badge_short_missing"), BADGE_NEUTRAL)
            self._badge_detail.setText(t("graphics.badge_not_installed"))
        self._status.setText(status.message)
        self._install.setEnabled(not status.conflict_enb)
        self._uninstall.setEnabled(status.installed)

    def _on_status_line(self, message: str) -> None:
        self._status.setText(message)

    def _on_error(self, message: str) -> None:
        self._badge.set_state(t("graphics.badge_short_error"), BADGE_ERROR)
        self._badge_detail.setText(t("graphics.badge_error"))
        self._status.setText(message)

    def _on_busy(self, busy: bool) -> None:
        enabled = not busy
        self._install.setEnabled(enabled)
        self._uninstall.setEnabled(enabled)
        self._install_road_2k.setEnabled(enabled)
        self._uninstall_road_2k.setEnabled(enabled)
        if not busy and self._vm.status is not None:
            self._render_status(self._vm.status)
