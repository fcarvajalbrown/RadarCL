"""
Results table widget.

Shown after Stop & Verify completes.
Displays email, source URL, and traffic-light status per row.
Supports sorting and filtering by column.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from app.core.exporter import export
from pathlib import Path


STATUS_COLORS = {
    'valid':   ('#E8F5E9', '#2E7D32'),  # (bg, fg)
    'unknown': ('#FFF8E1', '#F57F17'),
    'invalid': ('#FFEBEE', '#B71C1C'),
}

STATUS_LABELS = {
    'valid': 'Válido',
    'unknown': 'Desconocido',
    'invalid': 'Inválido',
}

# Save-As filters, in the order they appear in the dialog. The suffix is
# appended when the user types a name with no extension of its own.
SAVE_FILTERS = {
    "CSV — solo válidos (*.csv)": '.csv',
    "JSON — todos los estados (*.json)": '.json',
    "HTML — reporte (*.html)": '.html',
}


class ResultsTable(QWidget):
    """Sortable, filterable results table for verified emails."""

    def __init__(self) -> None:
        """Initialise results table."""
        super().__init__()
        self._results: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the table layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── Header row
        header = QHBoxLayout()

        title = QLabel("Resultados verificados")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #1A1A1A;")
        header.addWidget(title)

        header.addStretch()

        self._copy_btn = QPushButton("Copiar válidos")
        self._copy_btn.setFixedHeight(28)
        self._copy_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F5;
                color: #333333;
                font-size: 11px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 0 10px;
            }
            QPushButton:hover { background: #EEEEEE; }
        """)
        self._copy_btn.clicked.connect(self._copy_valid)
        header.addWidget(self._copy_btn)

        self._export_btn = QPushButton("Exportar…")
        self._export_btn.setFixedHeight(28)
        self._export_btn.setStyleSheet("""
            QPushButton {
                background: #1565C0;
                color: white;
                font-size: 11px;
                border: none;
                border-radius: 4px;
                padding: 0 10px;
            }
            QPushButton:hover { background: #1976D2; }
        """)
        self._export_btn.clicked.connect(self._save_as)
        header.addWidget(self._export_btn)

        layout.addLayout(header)

        # ── Filter bar
        filter_row = QHBoxLayout()
        filter_label = QLabel("Filtrar:")
        filter_label.setStyleSheet("color: #888888; font-size: 11px;")
        filter_row.addWidget(filter_label)

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText(
            "Escribe para filtrar por correo u origen…"
        )
        self._filter_input.setFixedHeight(28)
        self._filter_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                padding: 0 8px;
                font-size: 11px;
            }
        """)
        self._filter_input.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._filter_input)

        layout.addLayout(filter_row)

        # ── Summary badges
        self._summary = QLabel("")
        self._summary.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self._summary)

        # ── Table
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Correo", "Origen", "Estado"])
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #DDDDDD;
                border-radius: 6px;
                gridline-color: #F0F0F0;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #F5F5F5;
                color: #555555;
                font-size: 11px;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid #DDDDDD;
                padding: 6px 8px;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background-color: #E3F2FD;
                color: #1A1A1A;
            }
        """)
        layout.addWidget(self._table)

    # ── Public API

    def populate(self, results: list[dict]) -> None:
        """
        Fill the table with verification results.

        Parameters
        ----------
        results : list[dict]
            Each dict must have keys: email, source, status.
        """
        self._results = results
        self._render(results)
        self._update_summary(results)

    # ── Private

    def _render(self, results: list[dict]) -> None:
        """Render a list of result dicts into the table."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)

        for row_data in results:
            row = self._table.rowCount()
            self._table.insertRow(row)

            email_item = QTableWidgetItem(row_data.get('email', ''))
            source_item = QTableWidgetItem(row_data.get('source', ''))
            status = row_data.get('status', 'unknown').lower()
            status_item = QTableWidgetItem(
                STATUS_LABELS.get(status, status.capitalize())
            )
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            bg, fg = STATUS_COLORS.get(status, ('#FFFFFF', '#333333'))
            for item in (email_item, source_item, status_item):
                item.setBackground(QColor(bg))
                item.setForeground(QColor(fg))

            self._table.setItem(row, 0, email_item)
            self._table.setItem(row, 1, source_item)
            self._table.setItem(row, 2, status_item)

        self._table.setSortingEnabled(True)
        self._table.resizeColumnsToContents()
        self._table.horizontalHeader().setStretchLastSection(True)

    def _update_summary(self, results: list[dict]) -> None:
        """Update the summary badge counts."""
        valid = sum(1 for r in results if r.get('status') == 'valid')
        unknown = sum(1 for r in results if r.get('status') == 'unknown')
        invalid = sum(1 for r in results if r.get('status') == 'invalid')
        self._summary.setText(
            f"Total: {len(results)}   "
            f"✓ Válidos: {valid}   "
            f"? Desconocidos: {unknown}   "
            f"✗ Inválidos: {invalid}"
        )

    def _apply_filter(self, text: str) -> None:
        """Filter table rows by email or source containing text."""
        text = text.lower()
        filtered = [
            r for r in self._results
            if text in r.get('email', '').lower()
            or text in r.get('source', '').lower()
        ]
        self._render(filtered)
        self._update_summary(filtered)

    def _copy_valid(self) -> None:
        """Copy all valid email addresses to the clipboard."""
        from PySide6.QtWidgets import QApplication
        valid_emails = [
            r['email'] for r in self._results
            if r.get('status') == 'valid'
        ]
        if valid_emails:
            QApplication.clipboard().setText('\n'.join(valid_emails))

    def _save_as(self) -> None:
        """
        Open a Save As dialog and export the results.

        CSV keeps carrying only the valid addresses; JSON and HTML carry
        every status, so the filter the user picks changes what the file
        contains, not just how it is formatted (ADR-0010).
        """
        path, selected = QFileDialog.getSaveFileName(
            self,
            "Guardar resultados",
            str(Path.home() / 'Desktop' / 'RadarCL-export.csv'),
            ';;'.join(SAVE_FILTERS),
        )
        if not path:
            return

        target = Path(path)
        if target.suffix.lower() not in ('.csv', '.json', '.html', '.htm'):
            target = target.with_suffix(SAVE_FILTERS.get(selected, '.csv'))

        try:
            export(self._results, target)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "No se pudo guardar",
                f"No se pudo escribir el archivo:\n{exc}"
            )
            return

        QMessageBox.information(
            self,
            "Guardado",
            f"Resultados guardados en:\n{target}"
        )