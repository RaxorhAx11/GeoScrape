import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import tempfile

from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from PySide6.QtCore import Qt

# Ensure QApplication exists for UI component tests
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from src.core.models import BusinessItem, BatchJob
from src.core.batch_queue import BatchQueue
from src.core.batch_orchestrator import BatchScrapeOrchestrator
from src.exporter.excel_exporter import ExcelExporter
from src.ui.components.review_panel import ReviewPanel, EditLeadDialog
from src.ui.main_window import MainWindow
from src.ui.controller import MainWindowController


def create_sample_business(index: int = 1) -> BusinessItem:
    return BusinessItem(
        name=f"Dental Clinic {index}",
        rating=4.5 + (index * 0.1),
        reviews_count=50 + index,
        category="Dentist",
        address=f"12{index} Main Street, Austin, TX",
        phone=f"+1 512-555-010{index}",
        website=f"https://dental{index}.com",
        maps_url=f"https://maps.google.com/?cid={index}",
        email=f"info@dental{index}.com",
        linkedin=f"https://linkedin.com/company/dental{index}",
        facebook=f"https://facebook.com/dental{index}",
        instagram=f"https://instagram.com/dental{index}"
    )


class TestReviewPanelAndHITLWorkflow(unittest.TestCase):
    """
    Comprehensive tests for Human-in-the-Loop Workflow #4:
    Interactive Data Review & Lead Approval before Excel Export.
    """

    def setUp(self):
        self.panel = ReviewPanel()
        self.items = [create_sample_business(i) for i in range(1, 4)]  # 3 items

    def tearDown(self):
        self.panel.clear()

    # 1. Review table receives BusinessItem records
    def test_1_review_table_receives_business_items(self):
        self.panel.load_items(self.items, export_path="test_path.xlsx")
        self.assertEqual(self.panel.table.rowCount(), 3)
        self.assertEqual(self.panel.original_count, 3)
        self.assertEqual(len(self.panel.items), 3)
        self.assertEqual(self.panel.export_path, "test_path.xlsx")

    # 2. Records are displayed correctly
    def test_2_records_displayed_correctly(self):
        self.panel.load_items(self.items)
        first = self.items[0]

        # Column 0: Checkbox
        chk = self.panel.table.item(0, 0)
        self.assertIsNotNone(chk)
        self.assertEqual(chk.checkState(), Qt.Checked)

        # Columns 1..12: Attributes
        self.assertEqual(self.panel.table.item(0, 1).text(), first.name)
        self.assertIn(str(first.rating), self.panel.table.item(0, 2).text())
        self.assertEqual(self.panel.table.item(0, 3).text(), str(first.reviews_count))
        self.assertEqual(self.panel.table.item(0, 4).text(), first.category)
        self.assertEqual(self.panel.table.item(0, 5).text(), first.phone)
        self.assertEqual(self.panel.table.item(0, 6).text(), first.website)
        self.assertEqual(self.panel.table.item(0, 7).text(), first.email)
        self.assertEqual(self.panel.table.item(0, 8).text(), first.linkedin)
        self.assertEqual(self.panel.table.item(0, 9).text(), first.facebook)
        self.assertEqual(self.panel.table.item(0, 10).text(), first.instagram)
        self.assertEqual(self.panel.table.item(0, 11).text(), first.address)
        self.assertEqual(self.panel.table.item(0, 12).text(), first.maps_url)

    # 3. Select all
    def test_3_select_all(self):
        self.panel.load_items(self.items)
        self.panel.deselect_all()
        self.assertEqual(len(self.panel.get_approved_items()), 0)

        self.panel.select_all()
        self.assertEqual(len(self.panel.get_approved_items()), 3)
        for row in range(self.panel.table.rowCount()):
            self.assertEqual(self.panel.table.item(row, 0).checkState(), Qt.Checked)

    # 4. Deselect all
    def test_4_deselect_all(self):
        self.panel.load_items(self.items)
        self.panel.deselect_all()

        self.assertEqual(len(self.panel.get_approved_items()), 0)
        self.assertFalse(self.panel.approve_btn.isEnabled())
        for row in range(self.panel.table.rowCount()):
            self.assertEqual(self.panel.table.item(row, 0).checkState(), Qt.Unchecked)

    # 5. Delete selected records
    def test_5_delete_selected_records(self):
        self.panel.load_items(self.items)

        # Highlight row 1
        self.panel.table.selectRow(1)
        deleted_signals = []
        self.panel.records_deleted.connect(lambda count: deleted_signals.append(count))

        # Confirm delete
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.panel.delete_selected()

        self.assertEqual(self.panel.table.rowCount(), 2)
        self.assertEqual(len(self.panel.items), 2)
        self.assertEqual(self.panel.removed_count, 1)
        self.assertEqual(len(deleted_signals), 1)
        self.assertEqual(deleted_signals[0], 1)
        # Ensure Dental Clinic 2 was removed
        remaining_names = [it.name for it in self.panel.items]
        self.assertNotIn("Dental Clinic 2", remaining_names)

    # 6. Edit a record (dialog validation and item update)
    def test_6_edit_record_validation_and_update(self):
        item = self.items[0]
        dialog = EditLeadDialog(item)

        # Test empty name validation
        dialog.name_edit.setText("")
        with patch.object(QMessageBox, "warning") as mock_warn:
            dialog.validate_and_save()
            mock_warn.assert_called_once()
            self.assertIsNone(dialog.updated_item)

        # Test valid edit
        dialog.name_edit.setText("Updated Dental Care")
        dialog.rating_spin.setValue(4.9)
        dialog.reviews_spin.setValue(200)
        dialog.phone_edit.setText("+1 512-999-8888")
        dialog.email_edit.setText("contact@updateddental.com")

        with patch.object(dialog, "accept"):
            dialog.validate_and_save()

        self.assertIsNotNone(dialog.updated_item)
        self.assertEqual(dialog.updated_item.name, "Updated Dental Care")
        self.assertEqual(dialog.updated_item.rating, 4.9)
        self.assertEqual(dialog.updated_item.reviews_count, 200)
        self.assertEqual(dialog.updated_item.phone, "+1 512-999-8888")
        self.assertEqual(dialog.updated_item.email, "contact@updateddental.com")

    # 7. Approved records are returned correctly
    def test_7_approved_records_returned_correctly(self):
        self.panel.load_items(self.items)

        # Deselect row 1
        chk1 = self.panel.table.item(1, 0)
        chk1.setCheckState(Qt.Unchecked)
        self.panel.on_item_changed(chk1)

        approved = self.panel.get_approved_items()
        self.assertEqual(len(approved), 2)
        self.assertEqual(approved[0].name, "Dental Clinic 1")
        self.assertEqual(approved[1].name, "Dental Clinic 3")

    # 8. Deleted records are not exported
    def test_8_deleted_records_not_exported(self):
        self.panel.load_items(self.items)

        self.panel.table.selectRow(0)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.panel.delete_selected()

        approved = self.panel.get_approved_items()
        self.assertEqual(len(approved), 2)
        self.assertNotIn("Dental Clinic 1", [it.name for it in approved])

    # 9. Approval triggers Excel export
    def test_9_approval_triggers_excel_export(self):
        self.panel.load_items(self.items, export_path="target_leads.xlsx")

        approved_data = []
        self.panel.approved.connect(lambda items, path: approved_data.append((items, path)))

        self.panel.approve_and_export()
        self.assertEqual(len(approved_data), 1)
        items, path = approved_data[0]
        self.assertEqual(len(items), 3)
        self.assertEqual(path, "target_leads.xlsx")

    # 10. Cancel review does not export
    def test_10_cancel_review_does_not_export(self):
        self.panel.load_items(self.items, export_path="target_leads.xlsx")

        cancelled_signals = []
        self.panel.cancelled.connect(lambda: cancelled_signals.append(True))

        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.panel.cancel_review()

        self.assertEqual(len(cancelled_signals), 1)
        self.assertEqual(self.panel.table.rowCount(), 0)
        self.assertEqual(len(self.panel.items), 0)

    # 11. Empty dataset handling
    def test_11_empty_dataset_handling(self):
        self.panel.load_items([])
        self.assertEqual(self.panel.table.rowCount(), 0)
        self.assertEqual(len(self.panel.get_approved_items()), 0)
        self.assertFalse(self.panel.approve_btn.isEnabled())

        # Clicking approve with 0 items displays a warning
        with patch.object(QMessageBox, "warning") as mock_warn:
            self.panel.approve_and_export()
            mock_warn.assert_called_once()

    # 12. Existing Excel exporter still works with review output
    def test_12_existing_excel_exporter_works(self):
        self.panel.load_items(self.items)
        approved = self.panel.get_approved_items()

        exporter = ExcelExporter()
        with tempfile.TemporaryDirectory() as temp_dir:
            out_file = os.path.join(temp_dir, "reviewed_leads.xlsx")
            result_path = exporter.export(approved, out_file)
            self.assertTrue(os.path.exists(result_path))
            self.assertGreater(os.path.getsize(result_path), 0)

    # 13. Existing single scraping workflow review integration
    def test_13_single_scraping_workflow_review_integration(self):
        mock_scraper = MagicMock()
        mock_exporter = MagicMock()
        mock_exporter.export.return_value = "final.xlsx"

        window = MainWindow()
        controller = MainWindowController(window, mock_scraper, mock_exporter)

        # Simulate data_ready signal received by controller
        sample_items = [create_sample_business(1), create_sample_business(2)]
        controller.pending_export_path = "export.xlsx"
        controller.on_scrape_data_ready(sample_items)

        # Verify UI transitions to review mode
        self.assertEqual(window.status_label.text(), "Waiting for human review.")
        self.assertEqual(window.review_panel.table.rowCount(), 2)
        self.assertEqual(window.right_tabs.currentIndex(), 1)  # Tab 1: Data Review
        self.assertEqual(window.right_tabs.tabText(1), "Data Review (2)")

        # Review approval triggers export
        with patch.object(QMessageBox, "information"):
            controller.on_review_approved(sample_items, "export.xlsx")

        mock_exporter.export.assert_called_once_with(sample_items, "export.xlsx")
        self.assertEqual(window.status_label.text(), "Export completed.")

        # Cleanup
        controller.cleanup()

    # 14. Existing batch workflow still works
    def test_14_existing_batch_workflow_still_works(self):
        jobs = [BatchJob("Cafe", "Ahmedabad", 2)]
        queue = BatchQueue(jobs)

        mock_scraper = MagicMock()
        def mock_scrape(query, location, limit, progress_callback):
            for i in range(limit):
                progress_callback(create_sample_business(i + 1))

        mock_scraper.scrape.side_effect = mock_scrape
        mock_exporter = MagicMock()
        mock_exporter.export.side_effect = lambda items, path: path

        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = BatchScrapeOrchestrator(
                queue=queue,
                scraper=mock_scraper,
                exporter=mock_exporter,
                output_dir=temp_dir
            )
            orchestrator.run()

            self.assertEqual(mock_exporter.export.call_count, 1)
            self.assertEqual(queue.completed_count, 1)
            self.assertEqual(queue.failed_count, 0)
