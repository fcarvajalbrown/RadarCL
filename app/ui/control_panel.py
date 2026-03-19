"""
Left-side control panel.

Contains:
  - Session setup fields (target domain, seed URL/keyword)
  - Optional email pattern field (e.g. {first}.{last}@domain.cl)
  - Phase 1 timeout selector
  - Phase 2 toggle
  - Verification depth selector
  - Polite mode toggle
  - Start / Pause / Stop & Verify / Force Quit buttons

Emits signals consumed by MainWindow to update the terminal
and results table. Long-running work runs in CrawlerWorker
and VerifierWorker (QThread subclasses).
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QProgressBar,
    QCheckBox, QFrame, QSizePolicy
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont


def _label(text: str) -> QLabel:
    """Return a small muted label."""
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #666666; font-size: 11px;")
    return lbl


def _divider() -> QFrame:
    """Return a horizontal divider line."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #DDDDDD;")
    return line


class ControlPanel(QWidget):
    """Setup and action controls for a scraping session."""

    # Emitted for each discovered email: (email_address, source_url)
    email_discovered: Signal = Signal(str, str)
    # Emitted when Stop & Verify finishes with full results list
    verification_done: Signal = Signal(list)

    def __init__(self) -> None:
        """Initialise control panel."""
        super().__init__()
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding
        )
        self.setFixedWidth(280)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build all control widgets."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── Title
        title = QLabel("RadarCL")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #1A1A1A; margin-bottom: 4px;")
        layout.addWidget(title)

        subtitle = QLabel("Chilean email discovery")
        subtitle.setStyleSheet("color: #888888; font-size: 11px; margin-bottom: 8px;")
        layout.addWidget(subtitle)

        layout.addWidget(_divider())

        # ── Target domain
        layout.addWidget(_label("Target email domain (optional)"))
        self._domain_input = QLineEdit()
        self._domain_input.setPlaceholderText("e.g. @bhp.cl  (blank = any .cl)")
        self._domain_input.setFixedHeight(32)
        layout.addWidget(self._domain_input)

        # ── Seed
        layout.addWidget(_label("Start from (URL or keyword)"))
        self._seed_input = QLineEdit()
        self._seed_input.setPlaceholderText("e.g. bhp.cl  or  bhp chile contacto")
        self._seed_input.setFixedHeight(32)
        layout.addWidget(self._seed_input)

        # ── Email pattern (optional)
        layout.addWidget(_label("Email pattern (optional)"))
        self._pattern_input = QLineEdit()
        self._pattern_input.setPlaceholderText(
            "e.g. {first}.{last}  or  {f}{last}"
        )
        self._pattern_input.setFixedHeight(32)
        self._pattern_input.setToolTip(
            "If set, RadarCL will harvest names from pages and generate\n"
            "candidate addresses using this pattern.\n\n"
            "Supported tokens:\n"
            "  {first}  — full first name  (felipe)\n"
            "  {last}   — full last name   (carvajal)\n"
            "  {f}      — first initial    (f)\n"
            "  {l}      — last initial     (c)\n\n"
            "Examples:\n"
            "  {first}.{last}  →  felipe.carvajal@bhp.cl\n"
            "  {f}{last}       →  fcarvajal@bhp.cl\n"
            "  {first}_{last}  →  felipe_carvajal@bhp.cl"
        )
        layout.addWidget(self._pattern_input)

        # ── Phase 1 timeout
        layout.addWidget(_label("Search .cl sites for"))
        self._timeout_combo = QComboBox()
        self._timeout_combo.addItems([
            "As long as possible",
            "5 minutes",
            "10 minutes",
            "30 minutes",
        ])
        self._timeout_combo.setFixedHeight(32)
        layout.addWidget(self._timeout_combo)

        # ── Phase 2 toggle
        self._phase2_check = QCheckBox("Then expand to other sites")
        self._phase2_check.setToolTip(
            "After Phase 1 time is up, follow links to non-.cl sites.\n"
            "Still only collects .cl emails."
        )
        layout.addWidget(self._phase2_check)

        # ── Verification depth
        layout.addWidget(_label("How thoroughly check each email?"))
        self._verify_combo = QComboBox()
        self._verify_combo.addItems([
            "Quick  (format only)",
            "Standard  (format + domain)",
            "Deep  (full verification)",
        ])
        self._verify_combo.setCurrentIndex(2)
        self._verify_combo.setFixedHeight(32)
        layout.addWidget(self._verify_combo)

        # ── Polite mode
        self._robots_check = QCheckBox("Polite mode  (slower, more respectful)")
        self._robots_check.setToolTip(
            "Respects website crawling rules.\n"
            "Recommended for ethical use."
        )
        layout.addWidget(self._robots_check)

        layout.addWidget(_divider())

        # ── Progress
        self._progress = QProgressBar()
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #EEEEEE;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: #1565C0;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: #555555; font-size: 11px;")
        layout.addWidget(self._status_label)

        # ── Buttons
        self._start_btn = QPushButton("▶   Start")
        self._start_btn.setFixedHeight(44)
        self._start_btn.setStyleSheet("""
            QPushButton {
                background-color: #2E7D32;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #388E3C; }
            QPushButton:pressed { background-color: #1B5E20; }
            QPushButton:disabled { background-color: #AAAAAA; }
        """)
        layout.addWidget(self._start_btn)

        self._pause_btn = QPushButton("⏸   Pause")
        self._pause_btn.setFixedHeight(36)
        self._pause_btn.setEnabled(False)
        self._pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                color: #333333;
                font-size: 12px;
                border-radius: 6px;
                border: 1px solid #CCCCCC;
            }
            QPushButton:hover { background-color: #EEEEEE; }
            QPushButton:disabled { color: #AAAAAA; border-color: #EEEEEE; }
        """)
        layout.addWidget(self._pause_btn)

        self._stop_verify_btn = QPushButton("⏹   Stop && Verify")
        self._stop_verify_btn.setFixedHeight(36)
        self._stop_verify_btn.setEnabled(False)
        self._stop_verify_btn.setStyleSheet("""
            QPushButton {
                background-color: #1565C0;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:pressed { background-color: #0D47A1; }
            QPushButton:disabled { background-color: #AAAAAA; }
        """)
        layout.addWidget(self._stop_verify_btn)

        self._force_quit_btn = QPushButton("✕   Force Quit")
        self._force_quit_btn.setFixedHeight(30)
        self._force_quit_btn.setEnabled(False)
        self._force_quit_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #B71C1C;
                font-size: 11px;
                border-radius: 6px;
                border: 1px solid #FFCDD2;
            }
            QPushButton:hover { background-color: #FFEBEE; }
            QPushButton:disabled { color: #AAAAAA; border-color: #EEEEEE; }
        """)
        layout.addWidget(self._force_quit_btn)

        layout.addStretch()

    # ── Public accessors (used by workers)

    def get_domain(self) -> str:
        """Return the target email domain input value."""
        return str(self._domain_input.text()).strip()

    def get_seed(self) -> str:
        """Return the seed URL or keyword input value."""
        return str(self._seed_input.text()).strip()

    def get_pattern(self) -> str:
        """Return the optional email pattern input value."""
        return str(self._pattern_input.text()).strip()

    def get_phase2_enabled(self) -> bool:
        """Return True if Phase 2 expansion is enabled."""
        return self._phase2_check.isChecked()

    def get_phase1_timeout(self) -> float | None:
        """
        Return Phase 1 timeout in seconds, or None if unlimited.

        Returns
        -------
        float | None
        """
        mapping = {
            0: None,
            1: 300.0,
            2: 600.0,
            3: 1800.0,
        }
        return mapping.get(self._timeout_combo.currentIndex())

    def get_verify_depth(self) -> int:
        """
        Return verification depth index.

        0 = syntax only
        1 = syntax + MX
        2 = full (syntax + MX + SMTP)
        """
        return self._verify_combo.currentIndex()

    def get_respect_robots(self) -> bool:
        """Return True if polite mode is enabled."""
        return self._robots_check.isChecked()

    def set_status(self, text: str) -> None:
        """Update the status label text."""
        self._status_label.setText(text)

    def set_progress(self, value: int, maximum: int) -> None:
        """Show and update the progress bar."""
        self._progress.setVisible(True)
        self._progress.setMaximum(maximum)
        self._progress.setValue(value)

    def set_running(self, running: bool) -> None:
        """Toggle button states between idle and running modes."""
        self._start_btn.setEnabled(not running)
        self._pause_btn.setEnabled(running)
        self._stop_verify_btn.setEnabled(running)
        self._force_quit_btn.setEnabled(running)