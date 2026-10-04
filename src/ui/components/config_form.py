from PySide6.QtWidgets import QWidget, QFormLayout, QLineEdit, QSpinBox, QLabel, QCheckBox
from PySide6.QtCore import Qt

class ConfigForm(QWidget):
    """
    Form component for capturing search criteria parameters.
    
    Provides inline verification validation and highlights missing entries.
    """
    
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setObjectName("ConfigForm")
        
        # Configure spacious form layout
        form_layout = QFormLayout(self)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # Business Keyword Input Textbox
        self.keyword_input = QLineEdit()
        self.keyword_input.setObjectName("queryInput")  # Keep original styling selector
        self.keyword_input.setPlaceholderText("e.g. Dentist, Cafe, Boutique")
        self.keyword_input.textChanged.connect(self._clear_keyword_error)
        
        # Location Input Textbox
        self.location_input = QLineEdit()
        self.location_input.setObjectName("locationInput")
        self.location_input.setPlaceholderText("e.g. Boston, MA or Chicago")
        self.location_input.textChanged.connect(self._clear_location_error)
        
        # Max Results Input Spinbox
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setObjectName("limitSpin")  # Keep original styling selector
        self.max_results_spin.setRange(1, 1000)
        self.max_results_spin.setValue(50)
        self.max_results_spin.setButtonSymbols(QSpinBox.NoButtons)
        
        # Labels
        self.keyword_label = QLabel("Business Keyword:")
        self.keyword_label.setObjectName("formLabel")
        
        self.location_label = QLabel("Location:")
        self.location_label.setObjectName("formLabel")
        
        self.max_results_label = QLabel("Maximum Results:")
        self.max_results_label.setObjectName("formLabel")
        
        # Headless/Headed selection checkbox
        self.headed_checkbox = QCheckBox("Show browser window")
        self.headed_checkbox.setObjectName("headedCheckbox")
        self.headed_checkbox.setChecked(False)  # Default to false (run headless)

        # Faculty Demonstration / Testing Trigger Checkbox (Step 14)
        self.simulate_challenge_checkbox = QCheckBox("Simulate challenge (Demo/Test)")
        self.simulate_challenge_checkbox.setObjectName("simulateChallengeCheckbox")
        self.simulate_challenge_checkbox.setChecked(False)
        self.simulate_challenge_checkbox.setToolTip(
            "Development/Testing Mode: Simulates a verification challenge exception to demonstrate "
            "Human-in-the-Loop Workflow #5 without depending on live CAPTCHAs."
        )
        
        # Add widget rows
        form_layout.addRow(self.keyword_label, self.keyword_input)
        form_layout.addRow(self.location_label, self.location_input)
        form_layout.addRow(self.max_results_label, self.max_results_spin)
        form_layout.addRow("", self.headed_checkbox)
        form_layout.addRow("", self.simulate_challenge_checkbox)

    def get_data(self) -> dict:
        """
        Retrieves user input parameters formatted as a dictionary.
        
        Returns:
            dict: Containing 'query' (str), 'location' (str), 'limit' (int), 'headless' (bool),
                  and 'simulate_challenge' (bool).
        """
        return {
            "query": self.keyword_input.text().strip(),
            "location": self.location_input.text().strip(),
            "limit": self.max_results_spin.value(),
            "headless": not self.headed_checkbox.isChecked(),
            "simulate_challenge": self.simulate_challenge_checkbox.isChecked()
        }

    def validate(self) -> bool:
        """
        Validates text input fields are not empty.
        
        Applies dynamic error styling visual cue to fields failing validation.
        
        Returns:
            bool: True if inputs pass validation, False otherwise.
        """
        is_valid = True
        
        if not self.keyword_input.text().strip():
            self._set_error_state(self.keyword_input, True)
            is_valid = False
            
        if not self.location_input.text().strip():
            self._set_error_state(self.location_input, True)
            is_valid = False
            
        return is_valid

    def set_inputs_enabled(self, enabled: bool) -> None:
        """
        Enables or disables form inputs.
        
        Args:
            enabled (bool): Whether input fields should accept user interaction.
        """
        self.keyword_input.setEnabled(enabled)
        self.location_input.setEnabled(enabled)
        self.max_results_spin.setEnabled(enabled)
        self.headed_checkbox.setEnabled(enabled)
        self.simulate_challenge_checkbox.setEnabled(enabled)


    def _set_error_state(self, widget: QLineEdit, has_error: bool) -> None:
        """Applies dynamic stylesheet properties and forces redrawing."""
        widget.setProperty("error", has_error)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _clear_keyword_error(self) -> None:
        """Slot invoked to clear error styling on the keyword text box."""
        self._set_error_state(self.keyword_input, False)

    def _clear_location_error(self) -> None:
        """Slot invoked to clear error styling on the location text box."""
        self._set_error_state(self.location_input, False)
