"""
Left-side control panel.

Handles all session setup, button wiring, worker lifecycle,
seed validation, pause/resume, and Stop & Verify flow.
"""

import re
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QProgressBar,
    QCheckBox, QFrame, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from app.core.hw_profile import get_hw_profile
from app.core.pattern_generator import COMMON_PATTERNS
from app.workers.crawler_worker import CrawlerWorker
from app.workers.verifier_worker import VerifierWorker


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


def _is_valid_cl_url(url: str) -> bool:
    """
    Return True if url is a valid http/https URL ending in .cl.

    Parameters
    ----------
    url : str

    Returns
    -------
    bool
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        host = parsed.netloc.lower().split(':')[0]
        parts = host.split('.')
        return len(parts) >= 2 and parts[-1] == 'cl'
    except Exception:
        return False


class ControlPanel(QWidget):
    """Setup and action controls for a scraping session."""

    # Emitted for each discovered email: (email_address, source_url)
    email_discovered: Signal = Signal(str, str)
    # Emitted for each pattern-generated candidate: (email, source_url)
    candidate_discovered: Signal = Signal(str, str)
    # Emitted when Stop & Verify finishes with full results list
    verification_done: Signal = Signal(list)
    # Emitted when crawler resumes (for terminal divider)
    session_resumed: Signal = Signal()

    def __init__(self) -> None:
        """Initialise control panel."""
        super().__init__()
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding
        )
        self.setFixedWidth(280)

        # State
        self._crawler: CrawlerWorker | None = None
        self._verifier: VerifierWorker | None = None
        self._collected_emails: list[tuple[str, str]] = []
        self._is_running: bool = False
        self._is_paused: bool = False
        self._force_quit: bool = False

        # Hardware profile
        self._hw = get_hw_profile()

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
        subtitle.setStyleSheet(
            "color: #888888; font-size: 11px; margin-bottom: 8px;"
        )
        layout.addWidget(subtitle)

        # HW tier badge
        tier_colors = {
            'low':    ('#FFF3E0', '#E65100'),
            'medium': ('#E8F5E9', '#2E7D32'),
            'high':   ('#E3F2FD', '#1565C0'),
        }
        bg, fg = tier_colors.get(self._hw.tier, ('#F5F5F5', '#333333'))
        hw_badge = QLabel(
            f"Hardware: {self._hw.tier}  "
            f"({self._hw.ram_gb}GB RAM, {self._hw.cpu_cores} cores)"
        )
        hw_badge.setStyleSheet(
            f"background: {bg}; color: {fg}; font-size: 10px; "
            f"border-radius: 4px; padding: 3px 6px;"
        )
        layout.addWidget(hw_badge)

        layout.addWidget(_divider())

        # ── Target domain
        layout.addWidget(_label("Target email domain (optional)"))
        self._domain_input = QLineEdit()
        self._domain_input.setPlaceholderText(
            "e.g. @bhp.cl  (blank = any .cl)"
        )
        self._domain_input.setFixedHeight(32)
        layout.addWidget(self._domain_input)

        # ── Seed URL
        layout.addWidget(_label("Start from (.cl URL required)"))
        self._seed_input = QLineEdit()
        self._seed_input.setPlaceholderText("e.g. https://bhp.cl")
        self._seed_input.setFixedHeight(32)
        layout.addWidget(self._seed_input)

        self._seed_error = QLabel("")
        self._seed_error.setStyleSheet(
            "color: #B71C1C; font-size: 10px;"
        )
        self._seed_error.hide()
        layout.addWidget(self._seed_error)

        # ── Email pattern
        layout.addWidget(_label("Email pattern (optional)"))

        self._pattern_combo = QComboBox()
        self._pattern_combo.addItem("— select a common pattern —", "")
        for preset in COMMON_PATTERNS:
            self._pattern_combo.addItem(preset["label"], preset["pattern"])
        self._pattern_combo.addItem("Custom…", "__custom__")
        self._pattern_combo.setFixedHeight(32)
        self._pattern_combo.currentIndexChanged.connect(
            self._on_pattern_combo_changed
        )
        layout.addWidget(self._pattern_combo)

        self._pattern_input = QLineEdit()
        self._pattern_input.setPlaceholderText(
            "e.g. {first}.{last}  or  {f}{last}"
        )
        self._pattern_input.setFixedHeight(32)
        self._pattern_input.setToolTip(
            "Tokens: {first} {last} {f} {l}\n"
            "Example: {first}.{last} → felipe.carvajal@bhp.cl"
        )
        self._pattern_input.hide()
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
            "Quick  (format + domain)",
            "Deep   (full verification)",
        ])
        self._verify_combo.setCurrentIndex(1)
        self._verify_combo.setFixedHeight(32)
        layout.addWidget(self._verify_combo)

        # ── Polite mode
        self._robots_check = QCheckBox(
            "Polite mode  (slower, more respectful)"
        )
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
        self._status_label.setStyleSheet(
            "color: #555555; font-size: 11px;"
        )
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
            QPushButton:disabled {
                background-color: #AAAAAA;
                color: #DDDDDD;
            }
        """)
        self._start_btn.clicked.connect(self._on_start)
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
        self._pause_btn.clicked.connect(self._on_pause_resume)
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
        self._stop_verify_btn.clicked.connect(self._on_stop_verify)
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
        self._force_quit_btn.clicked.connect(self._on_force_quit)
        layout.addWidget(self._force_quit_btn)

        self._new_session_btn = QPushButton("↺   New Session")
        self._new_session_btn.setFixedHeight(30)
        self._new_session_btn.setVisible(False)
        self._new_session_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #1565C0;
                font-size: 11px;
                border-radius: 6px;
                border: 1px solid #BBDEFB;
            }
            QPushButton:hover { background-color: #E3F2FD; }
        """)
        self._new_session_btn.clicked.connect(self._on_new_session)
        layout.addWidget(self._new_session_btn)

        layout.addStretch()

    # ── Slot: pattern combo changed

    def _on_pattern_combo_changed(self, index: int) -> None:
        """Show custom input field when Custom… is selected."""
        data = self._pattern_combo.itemData(index)
        self._pattern_input.setVisible(data == "__custom__")

    # ── Slot: Start

    def _on_start(self) -> None:
        """
        Validate inputs and start the crawler worker.

        Shows inline error if seed URL is invalid.
        Shows tooltip message if already running.
        """
        if self._is_running:
            self._start_btn.setToolTip(
                "Already running — use Pause or Stop && Verify"
            )
            return

        seed = str(self._seed_input.text()).strip()
        if not _is_valid_cl_url(seed):
            self._seed_error.setText(
                "Please enter a valid .cl URL to start from\n"
                "e.g. https://bhp.cl"
            )
            self._seed_error.show()
            return

        self._seed_error.hide()
        self._collected_emails = []
        self._force_quit = False
        self._is_running = True
        self._is_paused = False

        self._set_running_state(True)
        self._status_label.setText("Crawling…")

        self._crawler = CrawlerWorker(
            seeds=[seed],
            target_domain=str(self._domain_input.text()).strip(),
            phase2_enabled=self._phase2_check.isChecked(),
            phase1_timeout=self._get_phase1_timeout(),
            max_pages=self._hw.max_pages,
            respect_robots=self._robots_check.isChecked(),
            pattern=self._get_pattern(),
            request_delay=self._hw.request_delay,
            concurrency=self._hw.concurrency,
        )

        self._crawler.email_found.connect(self._on_email_found)
        self._crawler.candidate_found.connect(self._on_candidate_found)
        self._crawler.crawl_finished.connect(self._on_crawl_finished)
        self._crawler.start()

    # ── Slot: Pause / Resume

    def _on_pause_resume(self) -> None:
        """Toggle between paused and running states."""
        if not self._crawler:
            return

        if self._is_paused:
            self._crawler.resume()
            self._is_paused = False
            self._pause_btn.setText("⏸   Pause")
            self._status_label.setText("Crawling…")
            self.session_resumed.emit()
        else:
            self._crawler.pause()
            self._is_paused = True
            self._pause_btn.setText("▶   Resume")
            self._status_label.setText("Paused.")

    # ── Slot: Stop & Verify

    def _on_stop_verify(self) -> None:
        """Stop crawler and launch verifier over collected emails."""
        if self._crawler:
            self._crawler.stop()

        self._is_running = False
        self._set_running_state(False)
        self._status_label.setText(
            f"Checking {len(self._collected_emails)} emails…"
        )
        self._progress.setVisible(True)
        self._progress.setMaximum(len(self._collected_emails))
        self._progress.setValue(0)

        smtp_enabled = self._verify_combo.currentIndex() == 1

        self._verifier = VerifierWorker(
            emails=self._collected_emails,
            smtp_enabled=smtp_enabled,
        )
        self._verifier.progress.connect(self._on_verify_progress)
        self._verifier.verify_finished.connect(self._on_verify_finished)
        self._verifier.start()

    # ── Slot: Force Quit

    def _on_force_quit(self) -> None:
        """Kill workers immediately, keep terminal, show New Session."""
        self._force_quit = True

        if self._crawler:
            self._crawler.stop()
            self._crawler = None

        if self._verifier:
            self._verifier.stop()
            self._verifier = None

        self._is_running = False
        self._is_paused = False
        self._set_running_state(False)

        # Disable all action buttons until New Session
        self._start_btn.setEnabled(False)
        self._pause_btn.setEnabled(False)
        self._stop_verify_btn.setEnabled(False)
        self._force_quit_btn.setEnabled(False)

        self._new_session_btn.setVisible(True)
        self._status_label.setText(
            "Session ended. Emails above are still visible."
        )
        self._progress.setVisible(False)

    # ── Slot: New Session

    def _on_new_session(self) -> None:
        """Ask user to start fresh or reuse last settings."""
        msg = QMessageBox(self)
        msg.setWindowTitle("New Session")
        msg.setText("How would you like to start?")
        fresh_btn = msg.addButton(
            "Start fresh", QMessageBox.ButtonRole.AcceptRole
        )
        reuse_btn = msg.addButton(
            "Reuse last settings", QMessageBox.ButtonRole.NoRole
        )
        msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == fresh_btn:
            self._reset_ui(keep_settings=False)
        elif clicked == reuse_btn:
            self._reset_ui(keep_settings=True)

    # ── Worker signal handlers

    def _on_email_found(self, email: str, source: str) -> None:
        """Store and forward discovered email."""
        self._collected_emails.append((email, source))
        self.email_discovered.emit(email, source)

    def _on_candidate_found(self, email: str, source: str) -> None:
        """Store and forward pattern-generated candidate."""
        self._collected_emails.append((email, source))
        self.candidate_discovered.emit(email, source)

    def _on_crawl_finished(self) -> None:
        """Handle crawler finishing naturally (max pages reached)."""
        if not self._force_quit:
            self._status_label.setText(
                f"Crawl complete. {len(self._collected_emails)} emails found.\n"
                "Click Stop && Verify to check them."
            )

    def _on_verify_progress(self, done: int, total: int) -> None:
        """Update progress bar during verification."""
        self._progress.setValue(done)
        self._status_label.setText(f"Checking {done}/{total} emails…")

    def _on_verify_finished(self, results: list) -> None:
        """Forward results and reset UI after verification."""
        self._progress.setVisible(False)
        valid = sum(1 for r in results if r.get('status') == 'valid')
        self._status_label.setText(
            f"Done. {valid} valid emails found.\n"
            "Results saved to your Desktop."
        )
        self._new_session_btn.setVisible(True)
        self.verification_done.emit(results)

        # Auto-export
        from app.core.exporter import export_valid
        from pathlib import Path
        export_valid(results)

    # ── Helpers

    def _set_running_state(self, running: bool) -> None:
        """Toggle button states between idle and running."""
        self._start_btn.setEnabled(not running)
        self._start_btn.setToolTip(
            "Already running — use Pause or Stop && Verify"
            if running else ""
        )
        self._pause_btn.setEnabled(running)
        self._stop_verify_btn.setEnabled(running)
        self._force_quit_btn.setEnabled(running)

    def _reset_ui(self, keep_settings: bool) -> None:
        """Reset UI for a new session."""
        self._collected_emails = []
        self._is_running = False
        self._is_paused = False
        self._force_quit = False
        self._progress.setVisible(False)
        self._progress.setValue(0)
        self._status_label.setText("")
        self._new_session_btn.setVisible(False)
        self._pause_btn.setText("⏸   Pause")
        self._set_running_state(False)
        self._start_btn.setEnabled(True)

        if not keep_settings:
            self._domain_input.clear()
            self._seed_input.clear()
            self._pattern_input.clear()
            self._pattern_combo.setCurrentIndex(0)
            self._timeout_combo.setCurrentIndex(0)
            self._phase2_check.setChecked(False)
            self._verify_combo.setCurrentIndex(1)
            self._robots_check.setChecked(False)

    def _get_pattern(self) -> str:
        """Return the active pattern string."""
        data = self._pattern_combo.itemData(
            self._pattern_combo.currentIndex()
        )
        if data == "__custom__":
            return str(self._pattern_input.text()).strip()
        return str(data) if data else ""

    def _get_phase1_timeout(self) -> float | None:
        """Return Phase 1 timeout in seconds or None."""
        mapping = {0: None, 1: 300.0, 2: 600.0, 3: 1800.0}
        return mapping.get(self._timeout_combo.currentIndex())

    def get_domain(self) -> str:
        """Return the target email domain input value."""
        return str(self._domain_input.text()).strip()

    def get_seed(self) -> str:
        """Return the seed URL input value."""
        return str(self._seed_input.text()).strip()