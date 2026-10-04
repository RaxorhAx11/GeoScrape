from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QBrush
from PySide6.QtCore import Qt, QPropertyAnimation, Property

class StatusIndicatorDot(QWidget):
    """A small circular status indicator that pulses gently during background operations."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self._color = QColor("#86868b")  # Default gray (Idle)
        self._opacity = 1.0
        
        # Setup gentle pulse animation for the running state
        self.pulse_anim = QPropertyAnimation(self, b"dotOpacity")
        self.pulse_anim.setDuration(1000)
        self.pulse_anim.setStartValue(1.0)
        self.pulse_anim.setKeyValueAt(0.5, 0.4)
        self.pulse_anim.setEndValue(1.0)
        self.pulse_anim.setLoopCount(-1)  # Loop indefinitely

    def get_dot_opacity(self) -> float:
        return self._opacity

    def set_dot_opacity(self, opacity: float):
        self._opacity = opacity
        self.update()

    # Define a Qt Property to enable QPropertyAnimation to target the opacity
    dotOpacity = Property(float, get_dot_opacity, set_dot_opacity)

    def set_state(self, state: str):
        """Sets the visual state of the status dot and updates/pulses styling."""
        self.pulse_anim.stop()
        self._opacity = 1.0
        
        state = state.lower()
        if state == "idle":
            self._color = QColor("#86868b")  # Gray
        elif state == "running":
            self._color = QColor("#0071e3")  # Apple Blue
            self.pulse_anim.start()
        elif state == "success":
            self._color = QColor("#34c759")  # Apple Green
        elif state == "error":
            self._color = QColor("#ff3b30")  # Apple Red
        elif state == "cancelling":
            self._color = QColor("#ff9500")  # Apple Orange
        elif state in ("review", "waiting"):
            self._color = QColor("#ff9500")  # Amber/Orange for Human Attention Required
            self.pulse_anim.start()
        else:
            self._color = QColor("#86868b")
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        color = QColor(self._color)
        color.setAlphaF(self._opacity)
        
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, self.width(), self.height())
