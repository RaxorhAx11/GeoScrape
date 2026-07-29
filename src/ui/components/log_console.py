from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QProgressBar, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

class LogConsole(QWidget):
    """
    Console log viewer widget displaying output progress, details, and operations logging.
    """
    
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setObjectName("LogConsole")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header bar setup
        header_layout = QHBoxLayout()
        header_label = QLabel("Live Execution Activity")
        header_label.setObjectName("consoleHeader")
        
        # Reset button control
        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("clearBtn")
        self.clear_button.setCursor(Qt.PointingHandCursor)
        self.clear_button.clicked.connect(self.clear)
        
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        header_layout.addWidget(self.clear_button)
        
        # Progress Bar setup
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        
        # Rich Text Area Log display
        self.log_display = QTextEdit()
        self.log_display.setObjectName("logTextArea")
        self.log_display.setReadOnly(True)
        self.log_display.setPlaceholderText("Start scraping to see activity log here...")
        
        layout.addLayout(header_layout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_display)

    def log(self, message: str, level: str = "INFO") -> None:
        """
        Appends log messages inside text panel with appropriate color styling.
        
        Args:
            message (str): Log message description text.
            level (str): Log level category: "INFO", "SUCCESS", "WARNING", "ERROR".
        """
        color = "#86868b"  # Default gray
        if level == "INFO":
            color = "#1d1d1f"  # Text black
        elif level == "SUCCESS":
            color = "#34c759"  # Apple Green
        elif level == "WARNING":
            color = "#ff9500"  # Apple Orange
        elif level == "ERROR":
            color = "#ff3b30"  # Apple Red
            
        formatted_message = (
            f'<div style="margin-bottom: 4px; font-family: Consolas, Monaco, monospace; '
            f'font-size: 12px; color: {color};"><b>[{level}]</b> {message}</div>'
        )
        self.log_display.append(formatted_message)
        
        # Force autoscroll behaviour to track new appends
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_progress(self, value: int) -> None:
        """
        Updates progress bar value percentage.
        
        Args:
            value (int): Integer scale between 0 and 100.
        """
        self.progress_bar.setValue(value)

    def clear(self) -> None:
        """Clears existing console logs and resets progress meter."""
        self.log_display.clear()
        self.progress_bar.setValue(0)
