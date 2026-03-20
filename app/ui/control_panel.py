"""
Left-side control panel.
Handles all session setup, button wiring, worker lifecycle,
seed discovery, pause/resume, and Stop & Verify flow.
Layout
------
Top section (scrollable): all settings and configuration
Bottom section (fixed):   progress bar, status, action buttons
"""

import asyncio
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QProgressBar,
    QCheckBox, QFrame, QSizePolicy, QMessageBox,
    QTextEdit, QScrollArea
)
from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtGui import QFont, QIcon

from app.core.hw_profile import get_hw_profile
from app.core.pattern_generator import COMMON_PATTERNS
from app.core.seed_discoverer import discover_seeds
from app.workers.crawler_worker import CrawlerWorker
from app.workers.verifier_worker import VerifierWorker


def _assets_path() -> Path:
    """Return assets directory, works both in dev and PyInstaller .exe."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / 'assets'  # type: ignore[attr-defined]
    return Path(__file__).parent.parent.parent / 'assets'

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


class _DiscoveryWorker(QThread):
    """
    Background thread for seed discovery.

    Runs discover_seeds() without blocking the GUI.

    Signals
    -------
    seeds_found : Signal(list)
        Emitted when discovery completes with the seed list.
    """

    seeds_found: Signal = Signal(list)

    def __init__(self, domain: str) -> None:
        """
        Initialise discovery worker.

        Parameters
        ----------
        domain : str
            Target domain to discover seeds for.
        """
        super().__init__()
        self._domain = domain

    def run(self) -> None:
        """Run seed discovery in background thread."""
        seeds = asyncio.run(discover_seeds(self._domain))
        self.seeds_found.emit(seeds)


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
    # Emitted when a new session starts (hides results table)
    new_session_started: Signal = Signal()

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
        self._discovery_worker: _DiscoveryWorker | None = None
        self._collected_emails: list[tuple[str, str]] = []
        self._discovered_seeds: list[str] = []
        self._is_running: bool = False
        self._is_paused: bool = False
        self._force_quit: bool = False

        # Hardware profile
        self._hw = get_hw_profile()

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build all control widgets.

        Layout: scrollable settings area on top, fixed button
        area pinned to the bottom so buttons are always visible.
        """
        # ── Outer layout: scroll area (top) + fixed buttons (bottom)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Scrollable settings area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setStyleSheet("QScrollArea { border: none; }")

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(8, 12, 8, 4)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(inner)
        outer.addWidget(scroll, stretch=1)

        # ── Fixed button area (never scrolls)
        btn_widget = QWidget()
        btn_widget.setStyleSheet(
            "background: #FAFAFA; border-top: 1px solid #EEEEEE;"
        )
        btn_layout = QVBoxLayout(btn_widget)
        btn_layout.setContentsMargins(8, 8, 8, 12)
        btn_layout.setSpacing(6)
        outer.addWidget(btn_widget, stretch=0)

        # ════════════════════════════════
        # SCROLLABLE SETTINGS
        # ════════════════════════════════

        # ── Title
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        icon_label = QLabel()
        icon_label.setPixmap(
            QIcon(str(_assets_path() / 'icon.ico')).pixmap(28, 28)
        )
        title_row.addWidget(icon_label)

        title = QLabel("RadarCL")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #1A1A1A; margin-bottom: 4px;")
        title_row.addWidget(title)
        title_row.addStretch()

        layout.addLayout(title_row)

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

        # ── Seed discovery
        layout.addWidget(_label("Seeds (discovered automatically)"))

        self._seed_status = QLabel("Enter target domain then click Discover")
        self._seed_status.setWordWrap(True)
        self._seed_status.setStyleSheet("color: #888888; font-size: 10px;")
        layout.addWidget(self._seed_status)

        self._seed_list = QTextEdit()
        self._seed_list.setReadOnly(True)
        self._seed_list.setFixedHeight(80)
        self._seed_list.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._seed_list.setFont(QFont("Consolas", 9))
        self._seed_list.setStyleSheet("""
            QTextEdit {
                background: #F8F8F8;
                color: #333333;
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        layout.addWidget(self._seed_list)

        self._discover_btn = QPushButton("⟳  Discover seeds")
        self._discover_btn.setFixedHeight(28)
        self._discover_btn.setStyleSheet("""
            QPushButton {
                background: #F5F5F5;
                color: #333333;
                font-size: 11px;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
            }
            QPushButton:hover { background: #EEEEEE; }
            QPushButton:disabled { color: #AAAAAA; }
        """)
        self._discover_btn.clicked.connect(self._on_discover_seeds)
        layout.addWidget(self._discover_btn)

        # ── Extra seeds
        layout.addWidget(_label("Add more URLs (one per line, optional)"))
        self._extra_seeds = QTextEdit()
        self._extra_seeds.setFixedHeight(60)
        self._extra_seeds.setPlaceholderText(
            "e.g. https://www.transparencia.cl\n"
            "https://www.munitel.cl"
        )
        self._extra_seeds.setStyleSheet("""
            QTextEdit {
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                font-size: 10px;
                padding: 4px;
            }
        """)
        layout.addWidget(self._extra_seeds)

        self._seed_error = QLabel("")
        self._seed_error.setWordWrap(True)
        self._seed_error.setStyleSheet("color: #B71C1C; font-size: 10px;")
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

        # ════════════════════════════════
        # FIXED BUTTON AREA
        # ════════════════════════════════

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
        btn_layout.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet(
            "color: #555555; font-size: 11px;"
        )
        btn_layout.addWidget(self._status_label)

        # ── Start
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
        btn_layout.addWidget(self._start_btn)

        # ── Pause
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
        btn_layout.addWidget(self._pause_btn)

        # ── Stop & Verify
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
        btn_layout.addWidget(self._stop_verify_btn)

        # ── Force Quit
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
        btn_layout.addWidget(self._force_quit_btn)

        # ── New Session
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
        btn_layout.addWidget(self._new_session_btn)

    # ── Slot: pattern combo changed

    def _on_pattern_combo_changed(self, index: int) -> None:
        """Show custom input field when Custom… is selected."""
        data = self._pattern_combo.itemData(index)
        self._pattern_input.setVisible(data == "__custom__")

    # ── Slot: Discover seeds

    def _on_discover_seeds(self) -> None:
        """
        Run seed discovery for the target domain in a background thread.

        Shows spinner while running, populates seed list on completion.
        """
        domain = str(self._domain_input.text()).strip().lstrip('@')
        if not domain:
            self._seed_error.setText(
                "Enter a target domain first e.g. @nunoa.cl"
            )
            self._seed_error.show()
            return

        self._seed_error.hide()
        self._discover_btn.setEnabled(False)
        self._discover_btn.setText("⟳  Discovering…")
        self._seed_status.setText(f"Searching for seeds for {domain}…")
        self._seed_list.clear()

        self._discovery_worker = _DiscoveryWorker(domain)
        self._discovery_worker.seeds_found.connect(self._on_seeds_found)
        self._discovery_worker.start()

    def _on_seeds_found(self, seeds: list[str]) -> None:
        """
        Populate seed list after discovery completes.

        Parameters
        ----------
        seeds : list[str]
            Discovered seed URLs.
        """
        self._discovered_seeds = seeds
        self._seed_list.setPlainText('\n'.join(seeds))
        self._seed_status.setText(f"{len(seeds)} seeds discovered")
        self._discover_btn.setEnabled(True)
        self._discover_btn.setText("⟳  Rediscover")

    # ── Slot: Start

    def _on_start(self) -> None:
        """
        Validate inputs and start the crawler worker.

        Shows tooltip if already running.
        Shows error if no seeds available.
        """
        if self._is_running:
            self._start_btn.setToolTip(
                "Already running — use Pause or Stop && Verify"
            )
            return

        # Combine discovered seeds with manual extras
        all_seeds = list(self._discovered_seeds)
        extra = str(self._extra_seeds.toPlainText()).strip()
        if extra:
            for line in extra.splitlines():
                line = line.strip()
                if line and line not in all_seeds:
                    all_seeds.append(line)

        if not all_seeds:
            self._seed_error.setText(
                "No seeds found.\n"
                "Click 'Discover seeds' first or add URLs manually."
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
            seeds=all_seeds,
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
        self._crawler.page_crawled.connect(self._on_page_crawled)
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
            self._crawler.wait(3000)
            self._crawler = None

        self._is_running = False
        self._set_running_state(False)
        self._status_label.setText(
            f"Checking {len(self._collected_emails)} emails…"
        )
        self._progress.setVisible(True)
        self._progress.setMaximum(max(len(self._collected_emails), 1))
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
        """
        Kill all workers immediately.

        Keeps terminal content visible. Disables all buttons
        until user clicks New Session.
        """
        self._force_quit = True

        if self._crawler:
            self._crawler.stop()
            self._crawler.wait(3000)
            if self._crawler.isRunning():
                self._crawler.terminate()
                self._crawler.wait(1000)
            self._crawler = None

        if self._verifier:
            self._verifier.stop()
            self._verifier.wait(3000)
            if self._verifier.isRunning():
                self._verifier.terminate()
                self._verifier.wait(1000)
            self._verifier = None

        if self._discovery_worker and self._discovery_worker.isRunning():
            self._discovery_worker.quit()
            self._discovery_worker.wait(3000)
            if self._discovery_worker.isRunning():
                self._discovery_worker.terminate()
                self._discovery_worker.wait(1000)
            self._discovery_worker = None

        self._is_running = False
        self._is_paused = False
        self._set_running_state(False)

        # Disable all buttons until New Session
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
        self._is_running = False
        self._set_running_state(False)
        if not self._force_quit:
            self._status_label.setText(
                f"Crawl complete. {len(self._collected_emails)} emails found.\n"
                "Click Stop && Verify to check them."
            )
            # Re-enable Stop & Verify so user can still verify
            self._stop_verify_btn.setEnabled(True)

    def _on_page_crawled(self, count: int) -> None:
        """Update status label with current page count."""
        self._status_label.setText(f"Crawling… {count} sites visited")

    def _on_verify_progress(self, done: int, total: int) -> None:
        """Update progress bar during verification."""
        self._progress.setValue(done)
        self._status_label.setText(f"Checking {done}/{total} emails…")

    def _on_verify_finished(self, results: list) -> None:
        """Forward results and auto-export after verification."""
        self._progress.setVisible(False)
        valid = sum(1 for r in results if r.get('status') == 'valid')
        self._status_label.setText(
            f"Done. {valid} valid emails found.\n"
            "Results saved to your Desktop."
        )
        self._new_session_btn.setVisible(True)
        self.verification_done.emit(results)

        from app.core.exporter import export_valid
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
        """
        Reset UI for a new session.

        Parameters
        ----------
        keep_settings : bool
            If True, preserve domain/seed/pattern fields.
            If False, clear everything.
        """
        self._collected_emails = []
        self._discovered_seeds = []
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
        self._seed_list.clear()
        self._seed_status.setText("Enter target domain then click Discover")
        self._discover_btn.setText("⟳  Discover seeds")
        self._discover_btn.setEnabled(True)
        self._seed_error.hide()

        if not keep_settings:
            self._domain_input.clear()
            self._extra_seeds.clear()
            self._pattern_input.clear()
            self._pattern_combo.setCurrentIndex(0)
            self._timeout_combo.setCurrentIndex(0)
            self._phase2_check.setChecked(False)
            self._verify_combo.setCurrentIndex(1)
            self._robots_check.setChecked(False)

        # Notify main window to hide results table and reset splitter
        self.new_session_started.emit()

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

    def get_seeds(self) -> list[str]:
        """Return the current list of discovered seeds."""
        return list(self._discovered_seeds)
