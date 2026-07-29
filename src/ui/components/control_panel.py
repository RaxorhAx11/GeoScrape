from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt

class ControlPanel(QWidget):
    """
    Button controls widget panel containing scraper start and stop actions.
    """
    
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setObjectName("ControlPanel")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(12)
        
        # Start button control
        self.start_button = QPushButton("Start Scrape")
        self.start_button.setObjectName("startBtn")  # Matches style sheet selector
        self.start_button.setCursor(Qt.PointingHandCursor)
        
        # Stop button control
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stopBtn")    # Matches style sheet selector
        self.stop_button.setEnabled(False)
        self.stop_button.setCursor(Qt.PointingHandCursor)
        
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)

    def set_running(self, is_running: bool) -> None:
        """
        Toggles enabling status of controls based on scrap state.
        
        Args:
            is_running (bool): True if scraping is active, False otherwise.
        """
        self.start_button.setEnabled(not is_running)
        self.stop_button.setEnabled(is_running)
