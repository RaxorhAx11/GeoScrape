from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QGraphicsDropShadowEffect, QSplitter
from PySide6.QtCore import Qt, QPropertyAnimation
from PySide6.QtGui import QColor, QShowEvent

from src.ui.components import ConfigForm, ControlPanel, LogConsole, StatusIndicatorDot
from src.ui.styles import APPLE_STYLE_SHEET

class MainWindow(QMainWindow):
    """
    Main Application window container displaying the central control dashboard.
    
    Houses the sidebar configurations panel, output action logs feed, 
    and handles global styles and window load animations.
    """
    
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GeoScrape - RPA Lead Generator")
        self.resize(920, 600)
        self.setMinimumSize(850, 520)
        
        # Apply the global stylesheet loaded from styles module
        self.setStyleSheet(APPLE_STYLE_SHEET)
        
        # Central layout container setup
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Root layout
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(12)
        
        # Splitter to support flexible layout resizing
        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("mainSplitter")
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        
        # --- LEFT SIDEBAR CARD FRAME ---
        self.sidebar_card = QFrame()
        self.sidebar_card.setObjectName("sidebarCard")
        
        # Responsiveness constraints: Keep sidebar aspect ratio clean
        self.sidebar_card.setMinimumWidth(320)
        self.sidebar_card.setMaximumWidth(400)
        
        # Shadows to add modern depth
        sidebar_shadow = QGraphicsDropShadowEffect(self)
        sidebar_shadow.setBlurRadius(15)
        sidebar_shadow.setColor(QColor(0, 0, 0, 10))
        sidebar_shadow.setOffset(0, 4)
        self.sidebar_card.setGraphicsEffect(sidebar_shadow)
        
        sidebar_layout = QVBoxLayout(self.sidebar_card)
        sidebar_layout.setContentsMargins(16, 24, 16, 24)
        sidebar_layout.setSpacing(16)
        
        # Title Header Block
        title_block_layout = QVBoxLayout()
        title_block_layout.setSpacing(0)
        
        self.title_label = QLabel("GeoScrape")
        self.title_label.setObjectName("mainTitle")
        
        self.subtitle_label = QLabel("RPA Lead Generator")
        self.subtitle_label.setObjectName("subtitle")
        
        title_block_layout.addWidget(self.title_label)
        title_block_layout.addWidget(self.subtitle_label)
        sidebar_layout.addLayout(title_block_layout)
        
        sidebar_layout.addSpacing(8)
        
        # Config Form input widget
        self.config_form = ConfigForm()
        sidebar_layout.addWidget(self.config_form)
        
        # Control buttons panel widget
        self.control_panel = ControlPanel()
        sidebar_layout.addWidget(self.control_panel)
        
        sidebar_layout.addStretch()
        
        # Status Box setup
        status_box = QFrame()
        status_box.setStyleSheet("background: transparent; border: none;")
        status_layout = QVBoxLayout(status_box)
        status_layout.setContentsMargins(16, 0, 16, 0)
        status_layout.setSpacing(4)
        
        status_title_label = QLabel("Status")
        status_title_label.setObjectName("statusTitleLabel")
        
        status_value_layout = QHBoxLayout()
        status_value_layout.setSpacing(8)
        
        self.status_dot = StatusIndicatorDot()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusTextLabel")
        
        status_value_layout.addWidget(self.status_dot)
        status_value_layout.addWidget(self.status_label)
        status_value_layout.addStretch()
        
        status_layout.addWidget(status_title_label)
        status_layout.addLayout(status_value_layout)
        
        sidebar_layout.addWidget(status_box)
        
        # --- RIGHT CONSOLE CARD FRAME ---
        self.console_card = QFrame()
        self.console_card.setObjectName("consoleCard")
        
        console_shadow = QGraphicsDropShadowEffect(self)
        console_shadow.setBlurRadius(15)
        console_shadow.setColor(QColor(0, 0, 0, 10))
        console_shadow.setOffset(0, 4)
        self.console_card.setGraphicsEffect(console_shadow)
        
        console_layout = QVBoxLayout(self.console_card)
        console_layout.setContentsMargins(0, 0, 0, 0)
        
        self.log_console = LogConsole()
        console_layout.addWidget(self.log_console)
        
        # Add widgets to splitter
        splitter.addWidget(self.sidebar_card)
        splitter.addWidget(self.console_card)
        
        # Establish default split proportions (340px sidebar, remainder console)
        splitter.setSizes([340, 540])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        
        root_layout.addWidget(splitter)
        
        # Setup modern fade-in transition
        self.setWindowOpacity(0.0)
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(500)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(1.0)

    def showEvent(self, event: QShowEvent) -> None:
        """
        Overrides show event hook to start startup fade-in animation.
        
        Args:
            event (QShowEvent): event instance.
        """
        super().showEvent(event)
        self.fade_animation.start()

    def set_status(self, state: str, text: str) -> None:
        """
        Updates status dot indicator state and text description.
        
        Args:
            state (str): Name of state ("idle", "running", "success", "error", "cancelling").
            text (str): Readable status description message text.
        """
        self.status_dot.set_state(state)
        self.status_label.setText(text)

    def closeEvent(self, event) -> None:
        """
        Overrides close event hook to delegate cleanup tasks to the controller.
        
        Args:
            event: close event instance.
        """
        if hasattr(self, "controller") and self.controller:
            self.controller.handle_close(event)
        else:
            event.accept()
