import os
import datetime
import logging
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtCore import QObject, Signal

from src.core.orchestrator import ScrapeOrchestrator
from src.core.models import BusinessItem
from src.ui.main_window import MainWindow
from src.scraper.playwright_scraper import ScraperConfig

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
    Controller that coordinates actions between the MainWindow View and the background scraper thread.
    
    Adheres strictly to the MVC design pattern, mediating UI events and model processing.
    """

    def __init__(self, view: MainWindow, scraper, exporter) -> None:
        """
        Initializes the controller and binds visual buttons to logic handlers.
        
        Args:
            view (MainWindow): The application GUI view instance.
            scraper: The concrete scraping engine implementation.
            exporter: The concrete file output exporter implementation.
        """
        super().__init__()
        self.view = view
        self.view.controller = self  # Establish back-reference for window close events
        self.scraper = scraper
        self.exporter = exporter
        self.orchestrator = None

        # Bind View buttons to Controller slots
        self.view.control_panel.start_button.clicked.connect(self.start_scraping)
        self.view.control_panel.stop_button.clicked.connect(self.stop_scraping)

        # Setup custom log redirection to the UI console (PRD 7.2)
        self.log_handler = QtLogHandler()
        self.log_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(message)s')
        self.log_handler.setFormatter(formatter)
        self.log_handler.emitter.log_signal.connect(self.view.log_console.log)
        logging.getLogger("src").addHandler(self.log_handler)

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

        # 3. Transition GUI Controls into 'Running' states
        self.view.config_form.set_inputs_enabled(False)
        self.view.control_panel.set_running(True)
        self.view.log_console.clear()
        
        self.view.log_console.log("Initializing scraper browser process...", "INFO")
        self.view.set_status("running", "Initializing scraper...")

        # 4. Extract parameters data from View
        config = self.view.config_form.get_data()

        # Update scraper headless mode configuration dynamically
        self.scraper.headless = config["headless"]
        self.scraper.config = ScraperConfig(headless=config["headless"])

        # 5. Spin up background QThread Orchestration worker
        self.orchestrator = ScrapeOrchestrator(
            scraper=self.scraper,
            exporter=self.exporter,
            query=config["query"],
            location=config["location"],
            limit=config["limit"],
            export_path=export_path,
            parent=self
        )

        # Wire worker event signals to slots
        self.orchestrator.item_scraped.connect(self.on_item_scraped)
        self.orchestrator.progress_changed.connect(self.on_progress_changed)
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

    def on_scraping_finished(self, export_path: str) -> None:
        """Slot invoked when work succeeds and spreadsheet writes are completed."""
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
        self.view.config_form.set_inputs_enabled(True)
        self.view.control_panel.set_running(False)
        self.orchestrator = None

    def cleanup(self) -> None:
        """Removes the custom logging handler to prevent memory leaks."""
        if hasattr(self, "log_handler"):
            logging.getLogger("src").removeHandler(self.log_handler)

    def handle_close(self, event) -> None:
        """Coordinates proper thread shutdown on window close event."""
        if self.orchestrator and self.orchestrator.isRunning():
            reply = QMessageBox.question(
                self.view,
                "Confirm Exit",
                "A scrape is currently in progress.\nAre you sure you want to stop the scrape and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.view.log_console.log("Window closing: Cancelling active scrape thread...", "WARNING")
                self.orchestrator.cancel()
                
                # Disable main window input and wait for thread termination
                self.view.setEnabled(False)
                if not self.orchestrator.wait(2000):
                    # We avoid terminating the thread directly as it can cause deadlocks/GIL corruption
                    print("Warning: Scraper thread did not finish inside timeout. Force closing.")
                self.cleanup()
                event.accept()
            else:
                event.ignore()
        else:
            self.cleanup()
            event.accept()
