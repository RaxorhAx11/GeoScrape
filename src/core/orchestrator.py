from PySide6.QtCore import QThread, Signal
from typing import List
from src.core.models import BusinessItem
from src.core.interfaces.scraper import ScraperInterface
from src.core.interfaces.exporter import ExporterInterface

class ScrapeOrchestrator(QThread):
    """
    QThread worker that coordinates the scraping process in the background.
    Communicates with the GUI thread via Qt Signals.
    """
    item_scraped = Signal(BusinessItem)
    progress_changed = Signal(int, int)  # Current, Total
    scraping_finished = Signal(str)     # Export path
    failed = Signal(str)                # Error message

    def __init__(
        self,
        scraper: ScraperInterface,
        exporter: ExporterInterface,
        query: str,
        location: str,
        limit: int,
        export_path: str,
        parent=None
    ):
        super().__init__(parent)
        self.scraper = scraper
        self.exporter = exporter
        self.query = query
        self.location = location
        self.limit = limit
        self.export_path = export_path
        self._is_cancelled = False

    def run(self):
        """Thread worker entry point execution loop."""
        scraped_items: List[BusinessItem] = []
        
        def scraper_progress_callback(item: BusinessItem):
            # Check for cancellation within the scraper callback
            if self._is_cancelled:
                raise InterruptedError("Scraping halted by user.")
            
            scraped_items.append(item)
            self.item_scraped.emit(item)
            self.progress_changed.emit(len(scraped_items), self.limit)

        try:
            # Set cancellation checker dynamically on the scraper
            self.scraper.is_cancelled = lambda: self._is_cancelled

            # 1. Run the scraper logic
            self.scraper.scrape(
                query=self.query,
                location=self.location,
                limit=self.limit,
                progress_callback=scraper_progress_callback
            )
            
            # Check cancellation after scrape completes
            if self._is_cancelled:
                raise InterruptedError("Scraping halted by user.")
                
            if not scraped_items:
                raise ValueError("No business listings were found for the query.")

            # 2. Export scraped results
            final_path = self.exporter.export(scraped_items, self.export_path)
            self.scraping_finished.emit(final_path)

        except InterruptedError as e:
            # Handle cancellation: save what we have, if any
            if scraped_items:
                try:
                    final_path = self.exporter.export(scraped_items, self.export_path)
                    self.scraping_finished.emit(final_path)
                except Exception as save_err:
                    self.failed.emit(f"Scrape cancelled, failed to save partially collected data: {save_err}")
            else:
                self.failed.emit(str(e))
                
        except Exception as e:
            # Catch and bubble up any other fatal errors
            self.failed.emit(str(e))

    def cancel(self):
        """Sets flag to gracefully request cancellation of scraping loop."""
        self._is_cancelled = True
