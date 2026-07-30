"""Conflict center: everything clashing between installed mods."""

from __future__ import annotations

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.theme.palette import DARK_PALETTE
from gta_mod_manager.gui.viewmodels.conflict_vm import ConflictViewModel
from gta_mod_manager.gui.widgets.cards import Card, page_header
from gta_mod_manager.models.enums import ConflictSeverity, ConflictType
from gta_mod_manager.services.conflict_service import ConflictGroup

_SEVERITY_KEYS: dict[ConflictSeverity, str] = {
    ConflictSeverity.BLOCKING: "conflicts.sev_blocking",
    ConflictSeverity.WARNING: "conflicts.sev_warning",
    ConflictSeverity.INFO: "conflicts.sev_info",
}

_TYPE_KEYS: dict[ConflictType, str] = {
    ConflictType.DUPLICATE_VEHICLE_NAME: "conflicts.duplicate_vehicle_name",
    ConflictType.FILE_OVERWRITE: "conflicts.file_overwrite",
    ConflictType.DUPLICATE_DLC: "conflicts.duplicate_dlc",
    ConflictType.DUPLICATE_GAMECONFIG: "conflicts.duplicate_gameconfig",
    ConflictType.MISSING_DEPENDENCY: "conflicts.missing_dependency",
}

_SEVERITY_COLOURS: dict[ConflictSeverity, str] = {
    ConflictSeverity.BLOCKING: DARK_PALETTE.danger,
    ConflictSeverity.WARNING: DARK_PALETTE.warning,
    ConflictSeverity.INFO: DARK_PALETTE.text_muted,
}


class ConflictView(QWidget):
    """Shows the audit of the whole installation, grouped by conflict type."""

    def __init__(self, view_model: ConflictViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._build()

        self._vm.groupsLoaded.connect(self._render)

    def refresh(self) -> None:
        """Re-run the audit."""
        self._vm.refresh()

    def _build(self) -> None:
        """Compose the page."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)

        layout.addWidget(page_header(t("conflicts.title"), t("conflicts.subtitle")))

        self._tree = QTreeWidget()

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        rescan = QPushButton(t("common.re_scan"))
        rescan.setObjectName("PrimaryButton")
        rescan.clicked.connect(self._vm.refresh)
        toolbar.addWidget(rescan)

        expand = QPushButton(t("common.expand_all"))
        expand.clicked.connect(lambda: self._tree.expandAll())
        toolbar.addWidget(expand)

        collapse = QPushButton(t("common.collapse_all"))
        collapse.clicked.connect(lambda: self._tree.collapseAll())
        toolbar.addWidget(collapse)

        self._summary = QLabel("")
        self._summary.setObjectName("Hint")
        toolbar.addWidget(self._summary, 1)
        layout.addLayout(toolbar)

        card = Card(t("conflicts.detected"))
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(
            [
                t("conflicts.col_conflict"),
                t("conflicts.col_severity"),
                t("conflicts.col_action"),
            ]
        )
        self._tree.setAlternatingRowColors(True)
        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        card.body.addWidget(self._tree)
        layout.addWidget(card, 1)

    def _render(self, groups: tuple[ConflictGroup, ...]) -> None:
        """Rebuild the tree from the audit result."""
        self._tree.clear()

        total = sum(len(group.conflicts) for group in groups)
        blocking = sum(
            1 for group in groups for conflict in group.conflicts if conflict.is_blocking
        )
        self._summary.setText(
            t("conflicts.none")
            if total == 0
            else t(
                "conflicts.summary",
                count=total,
                categories=len(groups),
                blocking=blocking,
            )
        )

        for group in groups:
            type_key = _TYPE_KEYS.get(group.conflict_type)
            title = (
                f"{t(type_key)} ({len(group.conflicts)})"
                if type_key
                else group.title
            )
            parent = QTreeWidgetItem(
                [title, t(_SEVERITY_KEYS[group.worst_severity]), ""]
            )
            parent.setForeground(
                1, QBrush(QColor(_SEVERITY_COLOURS[group.worst_severity]))
            )
            self._tree.addTopLevelItem(parent)

            for conflict in group.conflicts:
                child = QTreeWidgetItem(
                    [
                        conflict.description,
                        t(_SEVERITY_KEYS[conflict.severity]),
                        conflict.resolution_hint or "",
                    ]
                )
                child.setForeground(1, QBrush(QColor(_SEVERITY_COLOURS[conflict.severity])))
                if conflict.paths:
                    child.setToolTip(
                        0, "\n".join(str(path) for path in conflict.paths)
                    )
                if conflict.owner:
                    child.setToolTip(2, t("conflicts.owned_by", owner=conflict.owner))
                parent.addChild(child)

        self._tree.expandAll()
