"""
Styles module containing the Apple-inspired QSS stylesheet for GeoScrape application.
"""

APPLE_STYLE_SHEET = """
/* Global Window styling */
QMainWindow {
    background-color: #f5f5f7;
}

QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1d1d1f;
}

/* Card layout containers */
QFrame#sidebarCard {
    background-color: #ffffff;
    border: 1px solid #e8e8ed;
    border-radius: 12px;
}

QFrame#consoleCard {
    background-color: #ffffff;
    border: 1px solid #e8e8ed;
    border-radius: 12px;
}

/* Form input elements */
QLineEdit {
    background-color: #f5f5f7;
    border: 1px solid #d2d2d7;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    color: #1d1d1f;
}

QLineEdit:hover {
    border: 1px solid #86868b;
}

QLineEdit:focus {
    border: 2px solid #0071e3;
    background-color: #ffffff;
}

QLineEdit[error="true"] {
    border: 1.5px solid #ff3b30;
    background-color: #fff2f2;
}

QLineEdit:disabled {
    background-color: #f5f5f7;
    color: #86868b;
    border: 1px solid #e8e8ed;
}

/* Plain Text Edit for Batch Simple Input */
QPlainTextEdit {
    background-color: #f5f5f7;
    border: 1px solid #d2d2d7;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 12px;
    font-family: Consolas, "Segoe UI", sans-serif;
    color: #1d1d1f;
}

QPlainTextEdit:hover {
    border: 1px solid #86868b;
}

QPlainTextEdit:focus {
    border: 2px solid #0071e3;
    background-color: #ffffff;
}

QPlainTextEdit:disabled {
    background-color: #f5f5f7;
    color: #86868b;
    border: 1px solid #e8e8ed;
}

/* Spinbox */
QSpinBox {
    background-color: #f5f5f7;
    border: 1px solid #d2d2d7;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    color: #1d1d1f;
}

QSpinBox:hover {
    border: 1px solid #86868b;
}

QSpinBox:focus {
    border: 2px solid #0071e3;
    background-color: #ffffff;
}

QSpinBox:disabled {
    background-color: #f5f5f7;
    color: #86868b;
    border: 1px solid #e8e8ed;
}

/* Buttons */
QPushButton {
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    padding: 11px 20px;
    border: none;
}

QPushButton#startBtn {
    background-color: #0071e3;
    color: #ffffff;
}

QPushButton#startBtn:hover {
    background-color: #0077ed;
}

QPushButton#startBtn:pressed {
    background-color: #0062c3;
}

QPushButton#startBtn:disabled {
    background-color: #e8e8ed;
    color: #aeaeb2;
}

QPushButton#stopBtn {
    background-color: #ff3b30;
    color: #ffffff;
}

QPushButton#stopBtn:hover {
    background-color: #ff453a;
}

QPushButton#stopBtn:pressed {
    background-color: #d72f25;
}

QPushButton#stopBtn:disabled {
    background-color: #e8e8ed;
    color: #aeaeb2;
}

QPushButton#clearBtn {
    background-color: transparent;
    color: #0071e3;
    font-size: 12px;
    font-weight: 500;
    padding: 4px 8px;
}

QPushButton#clearBtn:hover {
    color: #0077ed;
    background-color: #f5f5f7;
    border-radius: 6px;
}

/* Console & Log view */
QTextEdit#logTextArea {
    background-color: #1d1d1f;
    border: none;
    border-radius: 8px;
    padding: 14px;
    color: #f5f5f7;
}

/* Progress bar styling */
QProgressBar {
    border: none;
    background-color: #e8e8ed;
    height: 6px;
    border-radius: 3px;
}

QProgressBar::chunk {
    background-color: #0071e3;
    border-radius: 3px;
}

/* Labels and Texts */
QLabel#mainTitle {
    font-size: 26px;
    font-weight: 700;
    color: #1d1d1f;
    letter-spacing: -0.5px;
}

QLabel#subtitle {
    font-size: 12px;
    font-weight: 400;
    color: #86868b;
    margin-top: 2px;
}

QLabel#formLabel {
    font-size: 13px;
    font-weight: 500;
    color: #515154;
}

QLabel#consoleHeader {
    font-size: 15px;
    font-weight: 600;
    color: #1d1d1f;
}

QLabel#statusTitleLabel {
    font-size: 11px;
    font-weight: 600;
    color: #86868b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

QLabel#statusTextLabel {
    font-size: 13px;
    font-weight: 500;
    color: #1d1d1f;
}

/* Tabs */
QTabWidget::pane {
    border: none;
    background: transparent;
}

QTabBar::tab {
    background-color: #f5f5f7;
    color: #86868b;
    font-size: 12px;
    font-weight: 600;
    padding: 8px 16px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
    border: 1px solid #e8e8ed;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0071e3;
    border-color: #d2d2d7;
}

QTabBar::tab:hover:!selected {
    background-color: #ebebee;
    color: #1d1d1f;
}

/* Secondary Button for Batch Loading */
QPushButton#loadBatchBtn {
    background-color: #f5f5f7;
    border: 1px solid #d2d2d7;
    color: #1d1d1f;
    font-size: 13px;
    font-weight: 600;
    padding: 10px 16px;
    border-radius: 8px;
}

QPushButton#loadBatchBtn:hover {
    background-color: #e8e8ed;
    border-color: #86868b;
}

QPushButton#loadBatchBtn:pressed {
    background-color: #dedee3;
}

QPushButton#loadBatchBtn:disabled {
    background-color: #f5f5f7;
    color: #aeaeb2;
    border-color: #e8e8ed;
}
"""
