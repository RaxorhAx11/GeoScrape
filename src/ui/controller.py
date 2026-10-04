import os
import datetime
import logging
from typing import List, Optional
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtCore import QObject, Signal

from src.core.orchestrator import ScrapeOrchestrator
from src.core.batch_orchestrator import BatchScrapeOrchestrator
from src.core.batch_queue import BatchQueue, load_batch_jobs_from_file, parse_simple_batch_input
from src.core.models import BusinessItem, BatchJob, BatchJobResult
from src.ui.main_window import MainWindow
from src.scraper.playwright_scraper import ScraperConfig

logger = logging.getLogger(__name__)


class LogSignalEmitter(QObject):
    log_signal = Signal(str, str)  # message, level


class QtLogHandler(logging.Handler):
    """Custom logging Handler to redirect log records thread-safely to PySide UI."""
    def __init__(self) -> None:
        super().__init__()
        self.emitter = LogSignalEmitter()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            level = record.levelname
            
            # Map logging levels to LogConsole levels
            if level == "WARNING":
                ui_level = "WARNING"
            elif level in ("ERROR", "CRITICAL"):
                ui_level = "ERROR"
            elif "success" in msg.lower() or msg.startswith("Extracted:"):
                ui_level = "SUCCESS"
            else:
                ui_level = "INFO"
                
            self.emitter.log_signal.emit(msg, ui_level)
        except Exception:
            self.handleError(record)


class MainWindowController(QObject):
    """
    Controller that coordinates actions between the MainWindow View and background scraping threads.
    Supports both Single Job Search and Autonomous Multi-Query Batch Processing.
    Adheres strictly to the MVC design pattern.
    """

    def __init__(self, view: MainWindow, scraper, exporter) -> None:
        super().__init__()
        self.view = view
        self.view.controller = self  # Establish back-reference for window close events
        self.scraper = scraper
        self.exporter = exporter
        self.orchestrator = None
        self.batch_orchestrator = None
        self.batch_queue = None
        self.batch_file_path = None
        self.pending_export_path = None
        self.current_review_items = []

        # Bind Single Scrape View buttons to Controller slots
        self.view.control_panel.start_button.clicked.connect(self.start_scraping)
        self.view.control_panel.stop_button.clicked.connect(self.stop_scraping)

        # Bind Human-in-the-Loop Review Panel slots (HITL Workflow #4)
        self.view.review_panel.approved.connect(self.on_review_approved)
        self.view.review_panel.cancelled.connect(self.on_review_cancelled)
        self.view.review_panel.record_edited.connect(self.on_record_edited)
        self.view.review_panel.records_deleted.connect(self.on_records_deleted)
        self.view.review_panel.metrics_updated.connect(self.on_review_metrics_updated)

        # Bind Batch Queue View buttons to Controller slots
        self.view.batch_panel.load_button.clicked.connect(self.load_batch_file)
        self.view.batch_panel.run_button.clicked.connect(self.start_batch_scraping)
        self.view.batch_panel.cancel_button.clicked.connect(self.stop_batch_scraping)

        # Setup custom log redirection to the UI console (PRD 7.2)
        self.log_handler = QtLogHandler()
        self.log_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(message)s')
        self.log_handler.setFormatter(formatter)
        self.log_handler.emitter.log_signal.connect(self.view.log_console.log)
        logging.getLogger("src").addHandler(self.log_handler)

    # =========================================================================
    # SINGLE SCRAPE WORKFLOW (Unchanged, 100% Backward Compatible)
    # =========================================================================

    def start_scraping(self) -> None:
        """
        Validates configurations input form and kicks off background lead collection thread.
        """
        # 1. Run Input Form Validation
        if not self.view.config_form.validate():
            self.view.log_console.log("Please fill in all required search fields.", "ERROR")
            self.view.set_status("error", "Validation failed. Fill form fields.")
            return

        # 2. Query File Save Destination Path
        default_dir = os.path.expanduser("~/Desktop")
        if not os.path.exists(default_dir):
            default_dir = os.getcwd()
            
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        default_filename = f"leads_{today_str}.xlsx"
        
        export_path, _ = QFileDialog.getSaveFileName(
            self.view,
            "Export Scraped Leads",
            os.path.join(default_dir, default_filename),
            "Excel Spreadsheet (*.xlsx)"
        )

        if not export_path:
            self.view.log_console.log("Scrape cancelled: Export path was not specified.", "WARNING")
            self.view.set_status("idle", "Export path not specified.")
            return

        self.pending_export_path = export_path

        # 3. Transition GUI Controls into 'Running' states
        self.view.tab_widget.tabBar().setEnabled(False)
        self.view.config_form.set_inputs_enabled(False)
        self.view.control_panel.set_running(True)
        self.view.log_console.clear()
        self.view.show_console_tab()
        
        self.view.log_console.log("Initializing scraper browser process...", "INFO")
        self.view.set_status("running", "Initializing scraper...")

        # 4. Extract parameters data from View
        config = self.view.config_form.get_data()

        # Update scraper headless mode configuration dynamically
        self.scraper.headless = config["headless"]
        self.scraper.config = ScraperConfig(headless=config["headless"])

        # 5. Spin up background QThread Orchestration worker with auto_export=False (HITL Review)
        self.orchestrator = ScrapeOrchestrator(
            scraper=self.scraper,
            exporter=self.exporter,
            query=config["query"],
            location=config["location"],
            limit=config["limit"],
            export_path=export_path,
            auto_export=False,
            parent=self
        )

        # Wire worker event signals to slots
        self.orchestrator.item_scraped.connect(self.on_item_scraped)
        self.orchestrator.progress_changed.connect(self.on_progress_changed)
        self.orchestrator.data_ready.connect(self.on_scrape_data_ready)
        self.orchestrator.scraping_finished.connect(self.on_scraping_finished)
        self.orchestrator.failed.connect(self.on_scraping_failed)
        
        # Safely clean up the thread object from memory only after execution loop fully stops
        self.orchestrator.finished.connect(self.orchestrator.deleteLater)

        # 6. Execute background processing loop
        self.orchestrator.start()

    def stop_scraping(self) -> None:
        """Sends signal requests to cancel processing execution."""
        if self.orchestrator and self.orchestrator.isRunning():
            self.view.log_console.log("Cancellation request received. Stopping scraper...", "WARNING")
            self.view.set_status("cancelling", "Stopping scraper...")
            self.orchestrator.cancel()

    def on_item_scraped(self, item: BusinessItem) -> None:
        """Slot invoked when a BusinessItem record is successfully parsed."""
        self.view.log_console.log(
            f"Extracted: {item.name} | Rating: {item.rating}⭐ | Phone: {item.phone}",
            "SUCCESS"
        )

    def on_progress_changed(self, current: int, total: int) -> None:
        """Slot invoked to update progress values."""
        percent = int((current / total) * 100) if total > 0 else 0
        self.view.log_console.set_progress(percent)
        self.view.set_status("running", f"Scraped {current} of {total} leads...")

    def on_scrape_data_ready(self, items: List[BusinessItem]) -> None:
        """
        Slot invoked when scraping & enrichment finishes.
        Transitions the workflow to HITL Workflow #4: Human Review & Approval.
        """
        count = len(items)
        self.current_review_items = items
        self.view.log_console.log(f"Scraping completed. Records collected: {count}", "SUCCESS")
        logger.info(f"Review stage started: {count} records")
        self.view.log_console.log(f"Review stage started: {count} records", "INFO")
        self.view.log_console.log("Waiting for human review before final export...", "WARNING")
        
        self.view.set_status("review", "Waiting for human review.")
        self.view.review_panel.load_items(items, self.pending_export_path or "")
        self.view.update_review_tab_label(count)
        self.view.show_review_tab()
        
        # Scrape worker has finished, allow user to operate review UI
        self.view.control_panel.set_running(False)
        self.orchestrator = None

    def on_record_edited(self, name: str) -> None:
        """Slot invoked when human reviewer modifies a record."""
        logger.info(f"User edited record: {name}")
        self.view.log_console.log(f"User edited record: {name}", "INFO")

    def on_records_deleted(self, count: int) -> None:
        """Slot invoked when human reviewer deletes records."""
        logger.info(f"User removed {count} records")
        self.view.log_console.log(f"User removed {count} records", "WARNING")
        self.view.set_status("review", f"Records removed: {count}. Waiting for human review.")

    def on_review_metrics_updated(self, total: int, approved: int, removed: int) -> None:
        """Slot invoked when record selection or deletion changes approved count."""
        self.view.update_review_tab_label(approved)

    def on_review_approved(self, approved_items: List[BusinessItem], export_path: str) -> None:
        """
        Slot invoked when reviewer clicks 'Approve & Export'.
        Exports only the approved records to Excel using the existing ExcelExporter.
        """
        if not approved_items:
            self.view.log_console.log("Approval failed: No records selected for export.", "ERROR")
            self.view.set_status("error", "No records selected.")
            QMessageBox.warning(self.view, "No Records", "No records are selected for export.")
            return

        if not export_path:
            default_dir = os.path.expanduser("~/Desktop")
            if not os.path.exists(default_dir):
                default_dir = os.getcwd()
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            export_path, _ = QFileDialog.getSaveFileName(
                self.view,
                "Export Approved Leads",
                os.path.join(default_dir, f"leads_{today_str}.xlsx"),
                "Excel Spreadsheet (*.xlsx)"
            )
            if not export_path:
                self.view.log_console.log("Export cancelled: Export path was not specified.", "WARNING")
                return

        count = len(approved_items)
        logger.info(f"User approved {count} records")
        self.view.log_console.log(f"User approved {count} records", "SUCCESS")
        self.view.log_console.log(f"Exporting approved records to: {export_path}", "INFO")
        self.view.set_status("running", f"Exporting {count} records...")

        try:
            logger.info("Exporting approved records")
            final_path = self.exporter.export(approved_items, export_path)
            self.view.log_console.log(f"Export completed: {final_path}", "SUCCESS")
            self.view.set_status("success", "Export completed.")

            QMessageBox.information(
                self.view,
                "Review Approved",
                f"Human Review Approved!\n\n"
                f"Successfully exported {count} approved records to:\n"
                f"{final_path}"
            )
            self.reset_review_state()

        except Exception as e:
            logger.error(f"Failed to export approved records: {e}")
            self.view.log_console.log(f"Failed to export approved records: {e}", "ERROR")
            self.view.set_status("error", "Export failed.")
            QMessageBox.critical(
                self.view,
                "Export Error",
                f"Failed to export approved records:\n\n{e}"
            )

    def on_review_cancelled(self) -> None:
        """Slot invoked when reviewer cancels review without exporting."""
        logger.info("Review cancelled")
        self.view.log_console.log("Review cancelled by user. No data was exported.", "WARNING")
        self.view.set_status("idle", "Review cancelled.")
        self.reset_review_state()

    def reset_review_state(self) -> None:
        """Clears the review panel and restores main window to idle state."""
        self.view.review_panel.clear()
        self.view.update_review_tab_label(0)
        self.view.show_console_tab()
        self.reset_ui_state()

    def on_scraping_finished(self, export_path: str) -> None:
        """Slot invoked when work succeeds (direct export fallback)."""
        self.view.log_console.log(f"All data successfully written to: {export_path}", "SUCCESS")
        self.view.set_status("success", "Scrape completed successfully!")
        
        QMessageBox.information(
            self.view,
            "Success",
            f"Scraping finished successfully!\n\nSaved to:\n{export_path}"
        )
        self.reset_ui_state()

    def on_scraping_failed(self, error_message: str) -> None:
        """Slot invoked if background process fails or was aborted."""
        self.view.log_console.log(f"Scraper execution halted: {error_message}", "ERROR")
        self.view.set_status("error", "Execution stopped.")
        
        QMessageBox.critical(
            self.view,
            "Scraper Notice",
            f"Scraper execution stopped:\n{error_message}"
        )
        self.reset_ui_state()

    def reset_ui_state(self) -> None:
        """Restores dashboard inputs and control states to default editable view."""
        self.view.tab_widget.tabBar().setEnabled(True)
        self.view.config_form.set_inputs_enabled(True)
        self.view.control_panel.set_running(False)
        self.orchestrator = None

    # =========================================================================
    # BATCH QUEUE WORKFLOW (Autonomous Multi-Query Processing)
    # =========================================================================

    def load_batch_file(self) -> None:
        """Opens file dialog for user to select a batch JSON file, validates it, and loads queue."""
        initial_dir = os.getcwd()
        file_path, _ = QFileDialog.getOpenFileName(
            self.view,
            "Load Batch Jobs JSON File",
            initial_dir,
            "JSON Files (*.json);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            jobs = load_batch_jobs_from_file(file_path)
            self.batch_queue = BatchQueue(jobs)
            self.batch_file_path = file_path
            
            file_name = os.path.basename(file_path)
            self.view.batch_panel.set_batch_loaded(file_name, file_path, len(jobs))
            self.view.log_console.log(f"Batch loaded: {len(jobs)} jobs from {file_name}", "INFO")
            self.view.set_status("idle", f"Batch loaded ({len(jobs)} jobs ready).")
            
        except Exception as e:
            self.view.log_console.log(f"Failed to load batch file: {e}", "ERROR")
            self.view.set_status("error", "Batch load error.")
            QMessageBox.critical(
                self.view,
                "Batch File Error",
                f"Failed to load batch file:\n\n{e}"
            )

    def start_batch_scraping(self) -> None:
        """Validates queue (Simple Input or JSON), selects export destination directory, and kicks off batch thread."""
        if self.view.batch_panel.get_input_mode() == "simple":
            simple_text = self.view.batch_panel.get_simple_input_text()
            if not simple_text:
                self.view.log_console.log("Simple batch input is empty. Please enter jobs like 'Dentist, Ahmedabad, 20'.", "ERROR")
                self.view.set_status("error", "No batch jobs entered.")
                return
            try:
                jobs = parse_simple_batch_input(simple_text)
                self.batch_queue = BatchQueue(jobs)
                self.view.log_console.log(f"Converted simple input into {len(jobs)} batch jobs.", "INFO")
            except Exception as e:
                self.view.log_console.log(f"Invalid simple batch input: {e}", "ERROR")
                self.view.set_status("error", "Input parsing error.")
                QMessageBox.critical(
                    self.view,
                    "Batch Input Error",
                    f"Failed to parse batch input:\n\n{e}\n\nExpected format per line:\nKeyword, Location, Limit\nExample: Dentist, Ahmedabad, 20"
                )
                return
        else:
            if not self.batch_queue or self.batch_queue.is_empty():
                self.view.log_console.log("No batch jobs loaded. Please load a valid JSON file first.", "ERROR")
                self.view.set_status("error", "No batch JSON file loaded.")
                return

        # Prompt user for destination output folder where each job's Excel file will be placed
        default_dir = os.path.expanduser("~/Desktop")
        if not os.path.exists(default_dir):
            default_dir = os.getcwd()

        output_dir = QFileDialog.getExistingDirectory(
            self.view,
            "Select Directory to Save Excel Batch Output Files",
            default_dir
        )
        if not output_dir:
            self.view.log_console.log("Batch cancelled: Output directory was not specified.", "WARNING")
            self.view.set_status("idle", "Export directory not specified.")
            return

        # Prepare GUI controls for active batch run
        self.view.tab_widget.tabBar().setEnabled(False)
        self.view.batch_panel.set_running(True)
        self.view.log_console.clear()
        
        total_jobs = self.batch_queue.total_jobs
        self.view.log_console.log(f"Starting batch queue execution ({total_jobs} jobs total)...", "INFO")
        self.view.set_status("running", f"Starting batch queue ({total_jobs} jobs)...")

        # Reset queue counters
        self.batch_queue.reset()

        # Update scraper headless mode configuration dynamically
        is_headless = not self.view.batch_panel.headed_checkbox.isChecked()
        self.scraper.headless = is_headless
        self.scraper.config = ScraperConfig(headless=is_headless)

        # Instantiate background BatchScrapeOrchestrator worker
        self.batch_orchestrator = BatchScrapeOrchestrator(
            queue=self.batch_queue,
            scraper=self.scraper,
            exporter=self.exporter,
            output_dir=output_dir,
            parent=self
        )

        # Wire batch orchestrator signals
        self.batch_orchestrator.batch_started.connect(self.on_batch_started)
        self.batch_orchestrator.job_started.connect(self.on_batch_job_started)
        self.batch_orchestrator.job_item_scraped.connect(self.on_batch_item_scraped)
        self.batch_orchestrator.job_progress.connect(self.on_batch_job_progress)
        self.batch_orchestrator.job_finished.connect(self.on_batch_job_finished)
        self.batch_orchestrator.batch_finished.connect(self.on_batch_finished)
        self.batch_orchestrator.batch_cancelled.connect(self.on_batch_cancelled)
        self.batch_orchestrator.batch_failed.connect(self.on_batch_failed)
        
        self.batch_orchestrator.finished.connect(self.batch_orchestrator.deleteLater)

        self.batch_orchestrator.start()

    def stop_batch_scraping(self) -> None:
        """Sends cancellation request to halt batch queue execution."""
        if self.batch_orchestrator and self.batch_orchestrator.isRunning():
            self.view.log_console.log("Cancellation request received. Halting batch queue...", "WARNING")
            self.view.set_status("cancelling", "Stopping batch queue...")
            self.batch_orchestrator.cancel()

    def on_batch_started(self, total: int) -> None:
        """Slot invoked when batch run starts."""
        self.view.set_status("running", f"Batch in progress: 0 of {total} jobs completed...")

    def on_batch_job_started(self, current: int, total: int, job: BatchJob) -> None:
        """Slot invoked when a new sequential job begins processing."""
        self.view.batch_panel.update_job_status(current, total, job.keyword, job.location)
        self.view.set_status("running", f"Batch Job {current}/{total}: {job.keyword} - {job.location}")
        self.view.log_console.log(
            f"Starting batch job {current}/{total}: {job.keyword} - {job.location} (Limit: {job.max_results})",
            "INFO"
        )

    def on_batch_item_scraped(self, current: int, total: int, item: BusinessItem) -> None:
        """Slot invoked when a business is scraped and enriched in batch mode."""
        self.view.log_console.log(
            f"Extracted: {item.name} | Rating: {item.rating}⭐ | Phone: {item.phone}",
            "SUCCESS"
        )

    def on_batch_job_progress(self, current: int, total: int, scraped: int, limit: int) -> None:
        """Slot invoked to update current job lead progress."""
        self.view.batch_panel.update_job_progress(scraped, limit)
        percent = int((scraped / limit) * 100) if limit > 0 else 0
        self.view.log_console.set_progress(percent)
        self.view.set_status("running", f"Job {current}/{total} | Scraped {scraped} of {limit} leads...")

    def on_batch_job_finished(self, current: int, total: int, result: BatchJobResult) -> None:
        """Slot invoked when an individual batch job finishes (successfully or failed)."""
        self.view.batch_panel.complete_job_progress(current, total)
        if result.success:
            self.view.log_console.log(
                f"Job {current} completed: {result.count} businesses",
                "SUCCESS"
            )
            if result.export_path:
                self.view.log_console.log(
                    f"Export completed: {os.path.basename(result.export_path)}",
                    "INFO"
                )
        else:
            self.view.log_console.log(f"Job {current} failed: {result.error_message}", "ERROR")
            if current < total:
                self.view.log_console.log("Continuing with next batch job.", "WARNING")

    def on_batch_finished(self, summary_text: str, results: list) -> None:
        """Slot invoked when all batch jobs have been executed sequentially."""
        for line in summary_text.splitlines():
            self.view.log_console.log(line, "INFO")

        success_count = sum(1 for r in results if r.success)
        failed_count = sum(1 for r in results if not r.success)
        self.view.log_console.log(
            f"Batch completed: {success_count} successful, {failed_count} failed",
            "SUCCESS" if failed_count == 0 else "WARNING"
        )
        self.view.set_status("success", "Batch queue completed!")

        QMessageBox.information(
            self.view,
            "Batch Completed",
            f"Batch execution finished!\n\n"
            f"Total Jobs: {len(results)}\n"
            f"Successful: {success_count}\n"
            f"Failed: {failed_count}\n\n"
            f"Summary saved to output folder."
        )
        self.reset_batch_ui_state()

    def on_batch_cancelled(self) -> None:
        """Slot invoked when batch processing is cancelled by user."""
        self.view.log_console.log("Batch cancelled by user.", "WARNING")
        self.view.set_status("idle", "Batch cancelled by user.")
        QMessageBox.warning(
            self.view,
            "Batch Cancelled",
            "Batch processing was cancelled by user.\nCompleted job outputs were preserved."
        )
        self.reset_batch_ui_state()

    def on_batch_failed(self, error_message: str) -> None:
        """Slot invoked if a fatal batch queue error occurs."""
        self.view.log_console.log(f"Batch execution halted: {error_message}", "ERROR")
        self.view.set_status("error", "Batch halted.")
        QMessageBox.critical(
            self.view,
            "Batch Notice",
            f"Batch execution stopped:\n{error_message}"
        )
        self.reset_batch_ui_state()

    def reset_batch_ui_state(self) -> None:
        """Restores batch panel controls and tab bar to idle state."""
        self.view.tab_widget.tabBar().setEnabled(True)
        self.view.batch_panel.set_running(False)
        self.batch_orchestrator = None

    # =========================================================================
    # APPLICATION SHUTDOWN & CLEANUP
    # =========================================================================

    def cleanup(self) -> None:
        """Removes the custom logging handler to prevent memory leaks."""
        if hasattr(self, "log_handler"):
            logging.getLogger("src").removeHandler(self.log_handler)

    def handle_close(self, event) -> None:
        """Coordinates proper thread shutdown on window close event."""
        active_worker = None
        if self.orchestrator and self.orchestrator.isRunning():
            active_worker = self.orchestrator
        elif self.batch_orchestrator and self.batch_orchestrator.isRunning():
            active_worker = self.batch_orchestrator

        if active_worker:
            reply = QMessageBox.question(
                self.view,
                "Confirm Exit",
                "A scrape or batch process is currently running.\nAre you sure you want to stop and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.view.log_console.log("Window closing: Cancelling active worker thread...", "WARNING")
                active_worker.cancel()
                
                # Disable main window input and wait for thread termination
                self.view.setEnabled(False)
                if not active_worker.wait(2000):
                    print("Warning: Worker thread did not finish inside timeout. Force closing.")
                self.cleanup()
                event.accept()
            else:
                event.ignore()
        else:
            self.cleanup()
            event.accept()
