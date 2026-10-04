from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer


class ChallengeDialog(QDialog):
    """
    Dialog displayed when a bot-challenge or verification prompt is detected.
    Implements HITL Workflow #5: Human Bot-Challenge / Exception Resolution.
    
    Prompts the human operator to manually complete the verification in the
    browser window, and provides 'Resume Scraping' and 'Cancel Scraping' actions.
    """
    resume_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, parent=None, reason: str = "", timeout_seconds: int = 300) -> None:
        super().__init__(parent)
        self.setWindowTitle("Human Action Required - GeoScrape")
        self.setFixedWidth(460)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self.timeout_remaining = timeout_seconds

        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Badge & Title
        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)

        badge_label = QLabel("⚠️ HUMAN ACTION REQUIRED")
        badge_label.setStyleSheet("""
            font-size: 11px;
            font-weight: 700;
            color: #d97706;
            background-color: #fef3c7;
            border: 1px solid #fde68a;
            border-radius: 6px;
            padding: 4px 8px;
            max-width: 200px;
        """)

        title_label = QLabel("Browser Verification Detected")
        title_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #1d1d1f;")

        header_layout.addWidget(badge_label)
        header_layout.addWidget(title_label)
        layout.addLayout(header_layout)

        # Instructions Card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #f5f5f7;
                border: 1px solid #d2d2d7;
                border-radius: 10px;
                padding: 14px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        msg_label = QLabel(
            "A browser verification/challenge was detected.<br><br>"
            "Please complete the verification manually in the <b>browser window</b>.<br><br>"
            "After completing it, click <b>Resume Scraping</b>."
        )
        msg_label.setStyleSheet("font-size: 13px; color: #1d1d1f; line-height: 1.4;")
        msg_label.setWordWrap(True)
        card_layout.addWidget(msg_label)

        if reason:
            reason_label = QLabel(f"<b>Detail:</b> {reason}")
            reason_label.setStyleSheet("font-size: 11px; color: #6e6e73;")
            reason_label.setWordWrap(True)
            card_layout.addWidget(reason_label)

        layout.addWidget(card)

        # Warning / Alert Label (Initially hidden, used if resume is clicked prematurely)
        self.alert_label = QLabel("")
        self.alert_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 600;
            color: #b91c1c;
            background-color: #fee2e2;
            border: 1px solid #fca5a5;
            border-radius: 6px;
            padding: 8px 12px;
        """)
        self.alert_label.setWordWrap(True)
        self.alert_label.setVisible(False)
        layout.addWidget(self.alert_label)

        # Countdown Timer Label
        self.timer_label = QLabel(self._format_timer_text(self.timeout_remaining))
        self.timer_label.setStyleSheet("font-size: 11px; color: #86868b; font-weight: 500;")
        self.timer_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.timer_label)

        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.cancel_button = QPushButton("Cancel Scraping")
        self.cancel_button.setObjectName("stopBtn")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.clicked.connect(self._on_cancel)

        self.resume_button = QPushButton("Resume Scraping")
        self.resume_button.setObjectName("startBtn")
        self.resume_button.setCursor(Qt.PointingHandCursor)
        self.resume_button.clicked.connect(self._on_resume)

        btn_layout.addWidget(self.cancel_button)
        btn_layout.addWidget(self.resume_button)
        layout.addLayout(btn_layout)

        # Setup local UI timer for countdown
        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self._on_timer_tick)
        self.countdown_timer.start()

    def _format_timer_text(self, seconds: int) -> str:
        minutes = seconds // 60
        secs = seconds % 60
        return f"Timeout in: {minutes:02d}:{secs:02d} (safe cancellation if unanswered)"

    def _on_timer_tick(self) -> None:
        self.timeout_remaining -= 1
        if self.timeout_remaining <= 0:
            self.timer_label.setText("Human intervention timeout reached.")
            self.countdown_timer.stop()
            self.alert_label.setText("Timeout reached. Cancelling scraping...")
            self.alert_label.setVisible(True)
            self.resume_button.setEnabled(False)
        else:
            self.timer_label.setText(self._format_timer_text(self.timeout_remaining))

    def show_still_present_warning(self, message: str) -> None:
        """Displays warning banner when verification is still detected after clicking Resume."""
        self.alert_label.setText(f"⚠️ {message}")
        self.alert_label.setVisible(True)

    def _on_resume(self) -> None:
        self.alert_label.setVisible(False)
        self.resume_clicked.emit()

    def _on_cancel(self) -> None:
        self.countdown_timer.stop()
        self.cancel_clicked.emit()
        self.reject()

    def closeEvent(self, event) -> None:
        """Treat closing the dialog via 'X' as Cancel."""
        self.countdown_timer.stop()
        self.cancel_clicked.emit()
        super().closeEvent(event)
