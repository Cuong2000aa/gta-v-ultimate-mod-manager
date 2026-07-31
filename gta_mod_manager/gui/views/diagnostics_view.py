"""Game diagnostics page: crash signatures, ASI/ENB pitfalls, suggested fixes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.theme.palette import DARK_PALETTE
from gta_mod_manager.gui.viewmodels.diagnostics_vm import DiagnosticsViewModel
from gta_mod_manager.gui.widgets.cards import Card, page_header
from gta_mod_manager.models.diagnostic import (
    DiagnosticFinding,
    DiagnosticReport,
    DiagnosticSeverity,
)

_FINDING_ROLE = Qt.ItemDataRole.UserRole

_SEVERITY_KEYS: dict[DiagnosticSeverity, str] = {
    DiagnosticSeverity.ERROR: "diagnostics.sev_error",
    DiagnosticSeverity.WARNING: "diagnostics.sev_warning",
    DiagnosticSeverity.INFO: "diagnostics.sev_info",
    DiagnosticSeverity.OK: "diagnostics.sev_ok",
}

_CATEGORY_KEYS: dict[str, str] = {
    "crash": "diagnostics.cat_crash",
    "graphics": "diagnostics.cat_graphics",
    "asi": "diagnostics.cat_asi",
    "mods": "diagnostics.cat_mods",
    "vehicles": "diagnostics.cat_vehicles",
    "components": "diagnostics.cat_components",
    "launch": "diagnostics.cat_launch",
    "logs": "diagnostics.cat_logs",
    "summary": "diagnostics.cat_summary",
    "general": "diagnostics.cat_general",
}

_SEVERITY_COLOURS: dict[DiagnosticSeverity, str] = {
    DiagnosticSeverity.ERROR: DARK_PALETTE.danger,
    DiagnosticSeverity.WARNING: DARK_PALETTE.warning,
    DiagnosticSeverity.INFO: DARK_PALETTE.text_muted,
    DiagnosticSeverity.OK: DARK_PALETTE.success,
}


class DiagnosticsView(QWidget):
    """Shows findings from the game diagnostics scanner."""

    def __init__(
        self, view_model: DiagnosticsViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._build()
        self._vm.reportLoaded.connect(self._render)
        self._vm.fixApplied.connect(self._on_fix_applied)

    def refresh(self) -> None:
        """Re-run the scan."""
        self._vm.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(14)

        layout.addWidget(page_header(t("diagnostics.title"), t("diagnostics.subtitle")))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        rescan = QPushButton(t("common.re_scan"))
        rescan.setObjectName("PrimaryButton")
        rescan.clicked.connect(self._vm.refresh)
        toolbar.addWidget(rescan)

        self._repair = QPushButton(t("diagnostics.repair_selected"))
        self._repair.setEnabled(False)
        self._repair.clicked.connect(self._repair_selected)
        toolbar.addWidget(self._repair)

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

        card = Card(t("diagnostics.findings"))
        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(
            [
                t("diagnostics.col_issue"),
                t("diagnostics.col_severity"),
                t("diagnostics.col_fix"),
            ]
        )
        self._tree.setAlternatingRowColors(True)
        self._tree.setWordWrap(True)
        self._tree.itemSelectionChanged.connect(self._update_repair_enabled)
        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        card.body.addWidget(self._tree)
        layout.addWidget(card, 1)

    def _render(self, report: DiagnosticReport | None) -> None:
        self._tree.clear()
        if report is None:
            self._summary.setText(t("diagnostics.need_game"))
            self._update_repair_enabled()
            return

        self._summary.setText(
            t("diagnostics.clean")
            if report.problem_count == 0
            else t(
                "diagnostics.summary",
                errors=report.error_count,
                warnings=report.warning_count,
                total=len(report.findings),
            )
        )

        for category, findings in report.by_category().items():
            label = t(_CATEGORY_KEYS.get(category, "diagnostics.cat_general"))
            parent = QTreeWidgetItem(
                [f"{label} ({len(findings)})", "", ""]
            )
            self._tree.addTopLevelItem(parent)
            for finding in findings:
                title, detail, fix = _localised_finding(finding)
                child = QTreeWidgetItem(
                    [
                        title,
                        f"[{t(_SEVERITY_KEYS[finding.severity])}]",
                        fix or "—",
                    ]
                )
                child.setData(0, _FINDING_ROLE, finding)
                tip = detail
                if finding.evidence:
                    tip = f"{detail}\n\n{finding.evidence}"
                child.setToolTip(0, tip)
                child.setToolTip(2, fix)
                colour = QBrush(QColor(_SEVERITY_COLOURS[finding.severity]))
                child.setForeground(1, colour)
                parent.addChild(child)
            parent.setExpanded(True)
        self._update_repair_enabled()

    def _selected_finding(self) -> DiagnosticFinding | None:
        items = self._tree.selectedItems()
        if not items:
            return None
        payload = items[0].data(0, _FINDING_ROLE)
        return payload if isinstance(payload, DiagnosticFinding) else None

    def _update_repair_enabled(self) -> None:
        finding = self._selected_finding()
        self._repair.setEnabled(bool(finding and finding.is_fixable))

    def _repair_selected(self) -> None:
        finding = self._selected_finding()
        if finding is None or not finding.is_fixable:
            QMessageBox.information(
                self,
                t("diagnostics.repair_selected"),
                t("diagnostics.fix_select_first"),
            )
            return

        title, _detail, fix = _localised_finding(finding)
        targets = ", ".join(finding.fix_targets)
        answer = QMessageBox.question(
            self,
            t("diagnostics.repair_confirm_title"),
            t(
                "diagnostics.repair_confirm_body",
                title=title,
                fix=fix or "—",
                targets=targets,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if int(answer) != int(QMessageBox.StandardButton.Yes):
            return
        self._vm.repair(finding)

    def _on_fix_applied(self, message: str) -> None:
        QMessageBox.information(self, t("diagnostics.repair_done_title"), message)


def _localised_finding(finding: DiagnosticFinding) -> tuple[str, str, str]:
    """Prefer i18n strings when present; otherwise keep scanner English text."""
    names = ", ".join(finding.fix_targets) if finding.fix_targets else ""
    short = ", ".join(
        target.rsplit("/", 1)[-1] for target in finding.fix_targets
    )
    values = {"names": names, "short": short or names}

    def pick(field: str, fallback: str) -> str:
        key = f"diagnostics.finding.{finding.code}.{field}"
        translated = t(key, **values)
        return fallback if translated == key else translated

    return (
        pick("title", finding.title),
        pick("detail", finding.detail),
        pick("fix", finding.fix),
    )
