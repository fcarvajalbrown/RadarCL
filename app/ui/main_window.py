"""
Main application window.

Layout
------
Left  : control panel (scrollable settings + fixed action buttons)
Centre: live terminal feed (emails only)
Right : results table (hidden until Stop & Verify completes,
        hidden again on New Session)
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QScreen

from app.ui.terminal_panel import TerminalPanel
from app.ui.control_panel import ControlPanel
from app.ui.results_table import ResultsTable


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self) -> None:
        """Initialise window and build UI."""
        super().__init__()
        self.setWindowTitle("RadarCL — Felipe Carvajal Brown, Investigador Independiente")
        self._apply_screen_size()
        self._build_ui()

    def _apply_screen_size(self) -> None:
        """
        Size the window to 80% of the primary screen on startup.
        User can freely resize or maximise from there.
        """
        screen: QScreen = self.screen()
        geometry = screen.availableGeometry()
        w = int(geometry.width() * 0.80)
        h = int(geometry.height() * 0.80)
        x = (geometry.width() - w) // 2
        y = (geometry.height() - h) // 2
        self.setGeometry(x, y, w, h)
        self.setMinimumSize(900, 600)

    def _build_ui(self) -> None:
        """Construct and wire up all child widgets."""
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)

        # Left: controls
        self.control_panel = ControlPanel()
        self._splitter.addWidget(self.control_panel)

        # Centre: live terminal
        self.terminal = TerminalPanel()
        self._splitter.addWidget(self.terminal)

        # Right: results table (hidden until verification completes)
        self.results_table = ResultsTable()
        self.results_table.hide()
        self._splitter.addWidget(self.results_table)

        # Proportional split: 22% controls, 78% terminal
        total = self.width()
        self._splitter.setSizes([
            int(total * 0.22),
            int(total * 0.78),
            0,
        ])
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 1)

        root_layout.addWidget(self._splitter)

        # ── Wire signals
        self.control_panel.email_discovered.connect(
            self.terminal.append_email
        )
        self.control_panel.candidate_discovered.connect(
            self.terminal.append_email
        )
        self.control_panel.verification_done.connect(
            self._on_verification_done
        )
        self.control_panel.session_resumed.connect(
            self.terminal.add_divider
        )
        self.control_panel.new_session_started.connect(
            self._on_new_session
        )

    def _on_verification_done(self, results: list) -> None:
        """Show and populate results table after verification finishes."""
        self.results_table.populate(results)
        self.results_table.show()
        total = self.width()
        self._splitter.setSizes([
            int(total * 0.22),
            int(total * 0.39),
            int(total * 0.39),
        ])

    def _on_new_session(self) -> None:
        """
        Hide results table, clear terminal, reset splitter.

        Called when user starts a new session via the New Session button.
        """
        self.results_table.hide()
        self.terminal.clear()
        total = self.width()
        self._splitter.setSizes([
            int(total * 0.22),
            int(total * 0.78),
            0,
        ])
