"""
Live terminal panel widget.

Displays discovered email addresses in real time.
White background, black monospace font.
Only email addresses appear here — no crawler noise.
Debug log is hidden by default, expandable via toggle.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLabel, QPushButton
)
from PySide6.QtGui import QFont, QColor, QPalette
from PySide6.QtCore import Qt


class TerminalPanel(QWidget):
    """Scrolling terminal-style email feed."""

    def __init__(self) -> None:
        """Initialise terminal panel."""
        super().__init__()
        self._count = 0
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the terminal widget layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── Header row
        header = QHBoxLayout()

        self._badge = QLabel("0 emails found")
        badge_font = QFont()
        badge_font.setPointSize(11)
        badge_font.setBold(True)
        self._badge.setFont(badge_font)
        self._badge.setStyleSheet("color: #1A1A1A;")
        header.addWidget(self._badge)

        header.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888888;
                font-size: 11px;
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                padding: 0 8px;
            }
            QPushButton:hover { color: #333333; border-color: #AAAAAA; }
        """)
        self._clear_btn.clicked.connect(self.clear)
        header.addWidget(self._clear_btn)

        self._debug_btn = QPushButton("Show details")
        self._debug_btn.setFixedHeight(24)
        self._debug_btn.setCheckable(True)
        self._debug_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888888;
                font-size: 11px;
                border: 1px solid #DDDDDD;
                border-radius: 4px;
                padding: 0 8px;
            }
            QPushButton:hover { color: #333333; border-color: #AAAAAA; }
            QPushButton:checked { color: #1565C0; border-color: #1565C0; }
        """)
        self._debug_btn.toggled.connect(self._toggle_debug)
        header.addWidget(self._debug_btn)

        layout.addLayout(header)

        # ── Email feed (always visible)
        self._feed = QTextEdit()
        self._feed.setReadOnly(True)
        self._feed.setFont(QFont("Consolas", 10))
        self._feed.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                color: #111111;
                border: 1px solid #DDDDDD;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        layout.addWidget(self._feed, stretch=3)

        # ── Debug log (hidden by default)
        debug_label = QLabel("Crawler log")
        debug_label.setStyleSheet("color: #888888; font-size: 10px; margin-top: 4px;")
        debug_label.hide()
        self._debug_label = debug_label
        layout.addWidget(debug_label)

        self._debug_log = QTextEdit()
        self._debug_log.setReadOnly(True)
        self._debug_log.setFont(QFont("Consolas", 9))
        self._debug_log.setStyleSheet("""
            QTextEdit {
                background-color: #F8F8F8;
                color: #555555;
                border: 1px solid #EEEEEE;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        self._debug_log.hide()
        layout.addWidget(self._debug_log, stretch=1)

    # ── Public API

    def append_email(self, email: str, source: str = "") -> None:
        """
        Append a single discovered email address to the feed.

        Parameters
        ----------
        email : str
            The discovered email address.
        source : str
            Source URL (shown in debug log only).
        """
        self._count += 1
        self._feed.append(email)
        self._badge.setText(
            f"{self._count} email{'s' if self._count != 1 else ''} found"
        )
        self._scroll_to_bottom(self._feed)

        if source:
            self._debug_log.append(f"[found] {email}  ←  {source}")
            self._scroll_to_bottom(self._debug_log)

    def append_debug(self, message: str) -> None:
        """
        Append a crawler debug message to the debug log.

        Parameters
        ----------
        message : str
            Debug message to display.
        """
        self._debug_log.append(message)
        self._scroll_to_bottom(self._debug_log)

    def clear(self) -> None:
        """Clear both feeds and reset the counter."""
        self._feed.clear()
        self._debug_log.clear()
        self._count = 0
        self._badge.setText("0 emails found")

    # ── Private

    def _toggle_debug(self, checked: bool) -> None:
        """Show or hide the debug log panel."""
        self._debug_log.setVisible(checked)
        self._debug_label.setVisible(checked)
        self._debug_btn.setText("Hide details" if checked else "Show details")

    def _scroll_to_bottom(self, widget: QTextEdit) -> None:
        """Scroll a QTextEdit to its latest entry."""
        sb = widget.verticalScrollBar()
        sb.setValue(sb.maximum())