import dataclasses
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QDoubleSpinBox, QSpinBox,
    QMessageBox, QFrame, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from src.core.models import BusinessItem


class EditLeadDialog(QDialog):
    """
    Modal dialog allowing human review and manual correction of business lead fields.
    Validates numeric ranges and required strings before updating.
    """
    def __init__(self, item: BusinessItem, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Lead - Human Review")
        self.setMinimumWidth(440)
        self.item = item
        self.updated_item: Optional[BusinessItem] = None

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        header_label = QLabel("Edit Business Listing")
        header_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #1d1d1f;")
        layout.addWidget(header_label)

        sub_label = QLabel("Correct any inaccurate data extracted by the automated scraper.")
        sub_label.setStyleSheet("font-size: 12px; color: #86868b; margin-bottom: 6px;")
        layout.addWidget(sub_label)

        # Form fields
        form = QFormLayout()
        form.setSpacing(10)

        self.name_edit = QLineEdit(item.name)
        self.category_edit = QLineEdit(item.category)
        self.phone_edit = QLineEdit(item.phone)
        self.website_edit = QLineEdit(item.website)
        self.email_edit = QLineEdit(item.email)
        self.address_edit = QLineEdit(item.address)
        self.linkedin_edit = QLineEdit(item.linkedin)
        self.facebook_edit = QLineEdit(item.facebook)
        self.instagram_edit = QLineEdit(item.instagram)
        self.maps_url_edit = QLineEdit(item.maps_url)

        # Rating spinbox: 0.0 to 5.0 with step 0.1
        self.rating_spin = QDoubleSpinBox()
        self.rating_spin.setRange(0.0, 5.0)
        self.rating_spin.setSingleStep(0.1)
        self.rating_spin.setDecimals(1)
        self.rating_spin.setValue(float(item.rating) if item.rating is not None else 0.0)

        # Reviews spinbox: 0 to 999999
        self.reviews_spin = QSpinBox()
        self.reviews_spin.setRange(0, 999999)
        self.reviews_spin.setValue(int(item.reviews_count) if item.reviews_count is not None else 0)

        form.addRow("Business Name*:", self.name_edit)
        form.addRow("Rating (0.0-5.0):", self.rating_spin)
        form.addRow("Reviews Count:", self.reviews_spin)
        form.addRow("Category:", self.category_edit)
        form.addRow("Phone:", self.phone_edit)
        form.addRow("Website:", self.website_edit)
        form.addRow("Email:", self.email_edit)
        form.addRow("Address:", self.address_edit)
        form.addRow("LinkedIn:", self.linkedin_edit)
        form.addRow("Facebook:", self.facebook_edit)
        form.addRow("Instagram:", self.instagram_edit)
        form.addRow("Maps URL:", self.maps_url_edit)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f5f5f7;
                color: #1d1d1f;
                border: 1px solid #d2d2d7;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #e8e8ed; }
        """)
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #0071e3;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #0077ed; }
        """)
        self.save_btn.clicked.connect(self.validate_and_save)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def validate_and_save(self) -> None:
        """Validates input values and constructs updated BusinessItem."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Business Name cannot be empty.")
            self.name_edit.setFocus()
            return

        rating = round(self.rating_spin.value(), 1)
        if rating < 0.0 or rating > 5.0:
            QMessageBox.warning(self, "Validation Error", "Rating must be between 0.0 and 5.0.")
            return

        reviews = self.reviews_spin.value()
        if reviews < 0:
            QMessageBox.warning(self, "Validation Error", "Reviews count cannot be negative.")
            return

        self.updated_item = dataclasses.replace(
            self.item,
            name=name,
            rating=rating,
            reviews_count=reviews,
            category=self.category_edit.text().strip(),
            phone=self.phone_edit.text().strip() or "N/A",
            website=self.website_edit.text().strip() or "N/A",
            email=self.email_edit.text().strip() or "N/A",
            address=self.address_edit.text().strip(),
            linkedin=self.linkedin_edit.text().strip() or "N/A",
            facebook=self.facebook_edit.text().strip() or "N/A",
            instagram=self.instagram_edit.text().strip() or "N/A",
            maps_url=self.maps_url_edit.text().strip()
        )
        self.accept()


class ReviewPanel(QWidget):
    """
    Dedicated Human-in-the-Loop (HITL) Review UI component.
    Displays scraped leads in an interactive QTableWidget, allowing reviewers to:
    - Select/deselect individual records for export
    - Edit and correct record attributes with validation
    - Delete/reject unwanted records
    - Approve final dataset before triggering Excel export
    - Safely cancel review without exporting
    """
    approved = Signal(list, str)   # approved_items: List[BusinessItem], export_path: str
    cancelled = Signal()
    record_edited = Signal(str)    # business name
    records_deleted = Signal(int)  # count deleted
    metrics_updated = Signal(int, int, int)  # total_scraped, approved_count, removed_count

    COLUMNS = [
        "Export", "Business Name", "Rating", "Reviews", "Category",
        "Phone", "Website", "Email", "LinkedIn", "Facebook",
        "Instagram", "Address", "Google Maps URL"
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.items: List[BusinessItem] = []
        self.original_count: int = 0
        self.removed_count: int = 0
        self.export_path: str = ""

        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 1. State Banner (HITL Workflow #4 indicator)
        self.banner = QFrame()
        self.banner.setObjectName("reviewBanner")
        self.banner.setStyleSheet("""
            QFrame#reviewBanner {
                background-color: #fff9e6;
                border: 1px solid #ffd666;
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        banner_layout = QVBoxLayout(self.banner)
        banner_layout.setContentsMargins(6, 6, 6, 6)
        banner_layout.setSpacing(2)

        self.banner_title = QLabel("⚠️ HUMAN REVIEW REQUIRED — HITL Workflow #4")
        self.banner_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #b78103;")
        self.banner_subtitle = QLabel(
            "Automated scraping & enrichment complete. Inspect, correct, or exclude records before final Excel export."
        )
        self.banner_subtitle.setStyleSheet("font-size: 11px; color: #7d5900;")

        banner_layout.addWidget(self.banner_title)
        banner_layout.addWidget(self.banner_subtitle)
        layout.addWidget(self.banner)

        # 2. Metrics summary bar
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(16)

        self.lbl_scraped = QLabel("Scraped: 0")
        self.lbl_scraped.setStyleSheet("font-size: 12px; font-weight: 600; color: #515154;")

        self.lbl_approved = QLabel("Selected for Export: 0")
        self.lbl_approved.setStyleSheet("font-size: 12px; font-weight: 700; color: #34c759;")

        self.lbl_removed = QLabel("Removed: 0")
        self.lbl_removed.setStyleSheet("font-size: 12px; font-weight: 600; color: #ff3b30;")

        metrics_layout.addWidget(self.lbl_scraped)
        metrics_layout.addWidget(self.lbl_approved)
        metrics_layout.addWidget(self.lbl_removed)
        metrics_layout.addStretch()
        layout.addLayout(metrics_layout)

        # 3. Action Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setObjectName("reviewActionBtn")
        self.select_all_btn.clicked.connect(self.select_all)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.setObjectName("reviewActionBtn")
        self.deselect_all_btn.clicked.connect(self.deselect_all)

        self.edit_btn = QPushButton("Edit Selected")
        self.edit_btn.setObjectName("reviewActionBtn")
        self.edit_btn.clicked.connect(self.edit_selected)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setObjectName("reviewDeleteBtn")
        self.delete_btn.setStyleSheet("""
            QPushButton#reviewDeleteBtn {
                background-color: #fff2f2;
                color: #ff3b30;
                border: 1px solid #ffccd0;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#reviewDeleteBtn:hover {
                background-color: #ffe5e5;
                border-color: #ff3b30;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_selected)

        toolbar_layout.addWidget(self.select_all_btn)
        toolbar_layout.addWidget(self.deselect_all_btn)
        toolbar_layout.addWidget(self.edit_btn)
        toolbar_layout.addWidget(self.delete_btn)
        toolbar_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel Review")
        self.cancel_btn.setObjectName("reviewCancelBtn")
        self.cancel_btn.setStyleSheet("""
            QPushButton#reviewCancelBtn {
                background-color: #f5f5f7;
                color: #515154;
                border: 1px solid #d2d2d7;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#reviewCancelBtn:hover {
                background-color: #e8e8ed;
                color: #1d1d1f;
            }
        """)
        self.cancel_btn.clicked.connect(self.cancel_review)

        self.approve_btn = QPushButton("✓ Approve & Export (0)")
        self.approve_btn.setObjectName("approveExportBtn")
        self.approve_btn.setStyleSheet("""
            QPushButton#approveExportBtn {
                background-color: #34c759;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#approveExportBtn:hover {
                background-color: #2fb34f;
            }
            QPushButton#approveExportBtn:disabled {
                background-color: #e8e8ed;
                color: #aeaeb2;
            }
        """)
        self.approve_btn.clicked.connect(self.approve_and_export)

        toolbar_layout.addWidget(self.cancel_btn)
        toolbar_layout.addWidget(self.approve_btn)
        layout.addLayout(toolbar_layout)

        # 4. Data Review Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.on_table_double_clicked)
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e8e8ed;
                border-radius: 8px;
                gridline-color: #f0f0f2;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #f5f5f7;
                color: #1d1d1f;
                font-weight: 600;
                font-size: 11px;
                border: none;
                border-bottom: 1px solid #d2d2d7;
                padding: 6px 8px;
            }
            QTableWidget::item:selected {
                background-color: #e5f1fb;
                color: #1d1d1f;
            }
        """)
        layout.addWidget(self.table)

    # =========================================================================
    # DATA LOADING & SYNCHRONIZATION
    # =========================================================================

    def load_items(self, items: List[BusinessItem], export_path: str = "") -> None:
        """
        Loads scraped records into the review table and initializes counts.
        """
        self.table.blockSignals(True)
        self.items = list(items)
        self.original_count = len(items)
        self.removed_count = 0
        self.export_path = export_path

        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            # Checkbox item for column 0
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk_item.setCheckState(Qt.Checked)
            chk_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, chk_item)

            self._set_row_data(row, item)

        self.table.blockSignals(False)
        self._update_metrics()

    def _set_row_data(self, row: int, item: BusinessItem) -> None:
        """Populates columns 1..12 with formatted BusinessItem attributes."""
        rating_str = f"{item.rating} ⭐" if item.rating else "N/A"
        reviews_str = str(item.reviews_count) if item.reviews_count is not None else "0"

        col_values = [
            item.name,
            rating_str,
            reviews_str,
            item.category or "N/A",
            item.phone or "N/A",
            item.website or "N/A",
            item.email or "N/A",
            item.linkedin or "N/A",
            item.facebook or "N/A",
            item.instagram or "N/A",
            item.address or "N/A",
            item.maps_url or "N/A"
        ]

        for col_idx, val in enumerate(col_values, start=1):
            cell = QTableWidgetItem(str(val))
            # Align numeric ratings and reviews to right
            if col_idx in (2, 3):
                cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, col_idx, cell)

    def _update_metrics(self) -> None:
        """Recalculates counts for display and updates approve button label."""
        total = len(self.items)
        approved_count = len(self.get_approved_indices())

        self.lbl_scraped.setText(f"Scraped: {self.original_count}")
        self.lbl_approved.setText(f"Selected for Export: {approved_count}")
        self.lbl_removed.setText(f"Removed: {self.removed_count}")

        self.approve_btn.setText(f"✓ Approve & Export ({approved_count})")
        self.approve_btn.setEnabled(approved_count > 0)

        self.metrics_updated.emit(self.original_count, approved_count, self.removed_count)

    def on_item_changed(self, item: QTableWidgetItem) -> None:
        """Handles checkbox toggling in column 0."""
        if item.column() == 0:
            self._update_metrics()

    # =========================================================================
    # HUMAN ACTIONS: SELECTION, EDITING, DELETION
    # =========================================================================

    def select_all(self) -> None:
        """Checks all row checkboxes for export."""
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            if chk:
                chk.setCheckState(Qt.Checked)
        self.table.blockSignals(False)
        self._update_metrics()

    def deselect_all(self) -> None:
        """Unchecks all row checkboxes."""
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            if chk:
                chk.setCheckState(Qt.Unchecked)
        self.table.blockSignals(False)
        self._update_metrics()

    def get_approved_indices(self) -> List[int]:
        """Returns indices of rows where the Export checkbox is checked."""
        indices: List[int] = []
        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            if chk and chk.checkState() == Qt.Checked:
                indices.append(row)
        return indices

    def get_approved_items(self) -> List[BusinessItem]:
        """Returns List[BusinessItem] representing user-approved records."""
        approved: List[BusinessItem] = []
        for idx in self.get_approved_indices():
            if idx < len(self.items):
                approved.append(self.items[idx])
        return approved

    def edit_selected(self) -> None:
        """Opens Edit dialog for the currently selected table row."""
        selected_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        if not selected_rows:
            QMessageBox.information(
                self,
                "Select a Record",
                "Please select a record from the table to edit."
            )
            return

        row = selected_rows[0]
        self._edit_row(row)

    def on_table_double_clicked(self, index) -> None:
        """Double clicking a table row opens the edit dialog."""
        row = index.row()
        if index.column() != 0:  # Clicking column 0 toggles checkbox
            self._edit_row(row)

    def _edit_row(self, row: int) -> None:
        """Launches EditLeadDialog for specified row index and updates item on save."""
        if row < 0 or row >= len(self.items):
            return

        current_item = self.items[row]
        dialog = EditLeadDialog(current_item, self)
        if dialog.exec() == QDialog.Accepted and dialog.updated_item:
            updated = dialog.updated_item
            self.items[row] = updated
            self.table.blockSignals(True)
            self._set_row_data(row, updated)
            self.table.blockSignals(False)
            self.record_edited.emit(updated.name)

    def delete_selected(self) -> None:
        """
        Deletes selected/highlighted rows from the review table and internal collection.
        If no rows are highlighted, informs user.
        """
        selected_rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        if not selected_rows:
            QMessageBox.information(
                self,
                "No Selection",
                "Please highlight one or more rows in the table to delete."
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to remove {len(selected_rows)} selected record(s) from export?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        count = len(selected_rows)
        self.table.blockSignals(True)
        for row in selected_rows:
            if 0 <= row < len(self.items):
                self.items.pop(row)
                self.table.removeRow(row)
        self.table.blockSignals(False)

        self.removed_count += count
        self._update_metrics()
        self.records_deleted.emit(count)

    # =========================================================================
    # APPROVAL & CANCELLATION
    # =========================================================================

    def approve_and_export(self) -> None:
        """
        Collects approved items and emits approved signal for controller to export.
        Validates that at least one record is selected.
        """
        approved_items = self.get_approved_items()
        if not approved_items:
            QMessageBox.warning(
                self,
                "No Records Approved",
                "Please select at least one record for export."
            )
            return

        self.approved.emit(approved_items, self.export_path)

    def cancel_review(self) -> None:
        """Prompts confirmation to cancel review and discard data safely."""
        reply = QMessageBox.question(
            self,
            "Confirm Cancellation",
            "Are you sure you want to cancel the review?\n\nScraped records will not be exported.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.clear()
            self.cancelled.emit()

    def clear(self) -> None:
        """Resets the review panel to empty state."""
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.table.blockSignals(False)
        self.items.clear()
        self.original_count = 0
        self.removed_count = 0
        self.export_path = ""
        self._update_metrics()
