from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QProgressBar, QCheckBox, QTabWidget, QPlainTextEdit
)
from PySide6.QtCore import Qt


class BatchPanel(QWidget):
    """
    Dedicated control panel widget for autonomous multi-query batch queue processing.
    Supports two input methods:
        1. Simple Input: Direct comma-separated lines (e.g. 'Dentist, Ahmedabad, 20')
        2. Upload JSON: Pre-configured batch JSON file
    Displays live execution status and queue progress.
    """
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setObjectName("BatchPanel")
        self._json_jobs_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(12)

        # Mode Selection Sub-tabs (Simple Input vs Upload JSON)
        self.input_mode_tabs = QTabWidget()
        self.input_mode_tabs.setObjectName("batchModeTabs")

        # -------------------------------------------------------------
        # Tab 1: Simple Input (Direct text entry)
        # -------------------------------------------------------------
        simple_tab = QWidget()
        simple_layout = QVBoxLayout(simple_tab)
        simple_layout.setContentsMargins(4, 8, 4, 4)
        simple_layout.setSpacing(6)

        self.simple_text_edit = QPlainTextEdit()
        self.simple_text_edit.setObjectName("simpleBatchInput")
        self.simple_text_edit.setPlaceholderText(
            "Dentist, Ahmedabad, 20\nRestaurant, Ahmedabad, 20\nHotel, Surat, 20"
        )
        self.simple_text_edit.setFixedHeight(95)
        self.simple_text_edit.textChanged.connect(self._on_simple_text_changed)

        simple_meta_layout = QHBoxLayout()
        simple_hint_label = QLabel("Keyword, Location, Limit")
        simple_hint_label.setStyleSheet("font-size: 11px; color: #86868b;")

        self.simple_count_label = QLabel("0 jobs detected")
        self.simple_count_label.setStyleSheet("font-size: 11px; color: #0071e3; font-weight: 600;")
        self.simple_count_label.setAlignment(Qt.AlignRight)

        simple_meta_layout.addWidget(simple_hint_label)
        simple_meta_layout.addStretch()
        simple_meta_layout.addWidget(self.simple_count_label)

        simple_layout.addWidget(self.simple_text_edit)
        simple_layout.addLayout(simple_meta_layout)

        # -------------------------------------------------------------
        # Tab 2: Upload JSON
        # -------------------------------------------------------------
        json_tab = QWidget()
        json_layout = QVBoxLayout(json_tab)
        json_layout.setContentsMargins(4, 8, 4, 4)
        json_layout.setSpacing(8)

        self.load_button = QPushButton("Load Batch File (.json)")
        self.load_button.setObjectName("loadBatchBtn")
        self.load_button.setCursor(Qt.PointingHandCursor)
        json_layout.addWidget(self.load_button)

        info_card = QFrame()
        info_card.setObjectName("batchInfoCard")
        info_card.setStyleSheet("""
            QFrame#batchInfoCard {
                background-color: #f5f5f7;
                border: 1px solid #d2d2d7;
                border-radius: 8px;
                padding: 6px 10px;
            }
        """)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(6, 6, 6, 6)
        info_layout.setSpacing(4)

        self.file_label = QLabel("Selected file: None")
        self.file_label.setStyleSheet("font-size: 12px; color: #1d1d1f; font-weight: 500;")
        self.file_label.setWordWrap(True)

        self.jobs_count_label = QLabel("Jobs: 0")
        self.jobs_count_label.setStyleSheet("font-size: 12px; color: #86868b; font-weight: 600;")

        info_layout.addWidget(self.file_label)
        info_layout.addWidget(self.jobs_count_label)
        json_layout.addWidget(info_card)

        # Add tabs
        self.input_mode_tabs.addTab(simple_tab, "Simple Input")
        self.input_mode_tabs.addTab(json_tab, "Upload JSON")
        self.input_mode_tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.input_mode_tabs)

        # Headed/Headless Checkbox
        self.headed_checkbox = QCheckBox("Show browser window")
        self.headed_checkbox.setObjectName("batchHeadedCheckbox")
        self.headed_checkbox.setChecked(False)
        layout.addWidget(self.headed_checkbox)

        # Faculty Demonstration / Testing Trigger Checkbox (Step 14)
        self.simulate_challenge_checkbox = QCheckBox("Simulate challenge (Demo/Test)")
        self.simulate_challenge_checkbox.setObjectName("batchSimulateChallengeCheckbox")
        self.simulate_challenge_checkbox.setChecked(False)
        self.simulate_challenge_checkbox.setToolTip(
            "Development/Testing Mode: Simulates a verification challenge exception in batch mode."
        )
        layout.addWidget(self.simulate_challenge_checkbox)


        # Action Buttons (Run / Cancel)
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        self.run_button = QPushButton("Run Batch")
        self.run_button.setObjectName("startBtn")
        self.run_button.setEnabled(False)
        self.run_button.setCursor(Qt.PointingHandCursor)

        self.cancel_button = QPushButton("Cancel Batch")
        self.cancel_button.setObjectName("stopBtn")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setCursor(Qt.PointingHandCursor)

        buttons_layout.addWidget(self.run_button)
        buttons_layout.addWidget(self.cancel_button)
        layout.addLayout(buttons_layout)

        # Live Queue Execution Status Box
        status_box = QFrame()
        status_box.setObjectName("batchStatusBox")
        status_box.setStyleSheet("""
            QFrame#batchStatusBox {
                background-color: #f5f5f7;
                border: 1px solid #e8e8ed;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        status_layout = QVBoxLayout(status_box)
        status_layout.setContentsMargins(10, 8, 10, 8)
        status_layout.setSpacing(5)

        self.current_job_label = QLabel("Current Job: - / -")
        self.current_job_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #1d1d1f;")

        self.current_query_label = QLabel("Current Query: -")
        self.current_query_label.setStyleSheet("font-size: 12px; color: #515154;")
        self.current_query_label.setWordWrap(True)

        self.lead_progress_label = QLabel("Job Leads: - / -")
        self.lead_progress_label.setStyleSheet("font-size: 11px; color: #86868b;")

        # Overall Batch Progress Bar
        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.setRange(0, 100)
        self.batch_progress_bar.setValue(0)
        self.batch_progress_bar.setTextVisible(False)
        self.batch_progress_bar.setFixedHeight(6)

        status_layout.addWidget(self.current_job_label)
        status_layout.addWidget(self.current_query_label)
        status_layout.addWidget(self.lead_progress_label)
        status_layout.addWidget(self.batch_progress_bar)

        layout.addWidget(status_box)
        layout.addStretch()

    def get_input_mode(self) -> str:
        """Returns 'simple' if on Simple Input tab, else 'json'."""
        return "simple" if self.input_mode_tabs.currentIndex() == 0 else "json"

    def get_simple_input_text(self) -> str:
        """Returns text content from the Simple Input text area."""
        return self.simple_text_edit.toPlainText().strip()

    def get_simulate_challenge(self) -> bool:
        """Returns whether simulated bot challenge test trigger is enabled."""
        return self.simulate_challenge_checkbox.isChecked()

    def set_batch_loaded(self, file_name: str, file_path: str, count: int) -> None:
        """Updates UI state when a batch JSON file is parsed."""
        self._json_jobs_count = count
        self.file_label.setText(f"Selected file: {file_name}")
        self.file_label.setToolTip(file_path)
        self.jobs_count_label.setText(f"Jobs: {count}")
        self.current_job_label.setText(f"Current Job: 0 / {count}")
        self.current_query_label.setText("Current Query: Ready to run")
        self.batch_progress_bar.setValue(0)
        self._sync_run_button_state()

    def set_running(self, is_running: bool) -> None:
        """Toggles widget interactability when batch begins or completes."""
        self.input_mode_tabs.setEnabled(not is_running)
        self.simple_text_edit.setEnabled(not is_running)
        self.load_button.setEnabled(not is_running)
        self.run_button.setEnabled(not is_running)
        self.cancel_button.setEnabled(is_running)
        self.headed_checkbox.setEnabled(not is_running)
        self.simulate_challenge_checkbox.setEnabled(not is_running)


    def update_job_status(self, current: int, total: int, keyword: str, location: str) -> None:
        """Updates display for active job in the batch."""
        self.current_job_label.setText(f"Current Job: {current} / {total}")
        self.current_query_label.setText(f"Current Query: {keyword} - {location}")
        self.lead_progress_label.setText("Job Leads: 0 / -")
        if total > 0:
            batch_pct = int(((current - 1) / total) * 100)
            self.batch_progress_bar.setValue(batch_pct)

    def update_job_progress(self, scraped: int, target: int) -> None:
        """Updates lead count for the currently executing job."""
        self.lead_progress_label.setText(f"Job Leads: {scraped} / {target}")

    def complete_job_progress(self, current: int, total: int) -> None:
        """Advances overall progress bar when a job finishes."""
        if total > 0:
            batch_pct = int((current / total) * 100)
            self.batch_progress_bar.setValue(batch_pct)

    def reset_status(self) -> None:
        """Resets the live execution display fields."""
        self.current_job_label.setText("Current Job: - / -")
        self.current_query_label.setText("Current Query: -")
        self.lead_progress_label.setText("Job Leads: - / -")
        self.batch_progress_bar.setValue(0)

    def _on_simple_text_changed(self) -> None:
        """Slot invoked when simple input text changes to update detected jobs count."""
        raw_text = self.simple_text_edit.toPlainText().strip()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip() and not line.strip().startswith("#")]
        count = len(lines)
        label_text = f"{count} job{'s' if count != 1 else ''} detected"
        self.simple_count_label.setText(label_text)
        self._sync_run_button_state()

    def _on_tab_changed(self, index: int) -> None:
        """Slot invoked when user switches between Simple Input and Upload JSON."""
        self._sync_run_button_state()

    def _sync_run_button_state(self) -> None:
        """Enables Run Batch button if active input method has valid data."""
        if self.get_input_mode() == "simple":
            has_input = bool(self.simple_text_edit.toPlainText().strip())
            self.run_button.setEnabled(has_input)
        else:
            self.run_button.setEnabled(self._json_jobs_count > 0)
