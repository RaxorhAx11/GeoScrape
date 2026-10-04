from PySide6.QtCore import QThread, Signal
from typing import List, Optional
from src.core.models import BusinessItem, AutomationState
from src.core.interfaces.scraper import ScraperInterface
from src.core.interfaces.exporter import ExporterInterface
from src.core.challenge_coordinator import HumanChallengeCoordinator

class ScrapeOrchestrator(QThread):
    """
    QThread worker that coordinates the scraping process in the background.
    Communicates with the GUI thread via Qt Signals.
    Supports Human-in-the-Loop Bot Challenge Resolution (HITL Workflow #5).
    """
    item_scraped = Signal(BusinessItem)
    progress_changed = Signal(int, int)  # Current, Total
    data_ready = Signal(list)            # Emitted with List[BusinessItem] for human review
    scraping_finished = Signal(str)     # Export path (when auto_export=True)
    failed = Signal(str)                # Error message
    challenge_detected = Signal(str)    # reason description (emitted when challenge detected)
    challenge_still_present = Signal(str) # warning message when user resumes but challenge still exists
    challenge_resolved = Signal()       # Emitted when challenge is resolved and scraping continues
    state_changed = Signal(str)         # AutomationState

    def __init__(
        self,
        scraper: ScraperInterface,
        exporter: ExporterInterface,
        query: str,
        location: str,
        limit: int,
        export_path: str = "",
        auto_export: bool = False,
        challenge_timeout_seconds: int = 300,
        parent=None
    ):
        super().__init__(parent)
        self.scraper = scraper
        self.exporter = exporter
        self.query = query
        self.location = location
        self.limit = limit
        self.export_path = export_path
        self.auto_export = auto_export
        self.challenge_timeout_seconds = challenge_timeout_seconds
        self._is_cancelled = False
        self._state = AutomationState.IDLE
        self.coordinator: Optional[HumanChallengeCoordinator] = None

    @property
    def state(self) -> AutomationState:
        return self._state

    @state.setter
    def state(self, new_state: AutomationState) -> None:
        self._state = new_state
        self.state_changed.emit(new_state.value)

    def run(self):
        """Thread worker entry point execution loop."""
        scraped_items: List[BusinessItem] = []
        self.state = AutomationState.RUNNING
        
        def scraper_progress_callback(item: BusinessItem):
            # Check for cancellation within the scraper callback
            if self._is_cancelled:
                raise InterruptedError("Scraping halted by user.")
            
            scraped_items.append(item)
            self.item_scraped.emit(item)
            self.progress_changed.emit(len(scraped_items), self.limit)

        def on_challenge_detected(reason: str):
            self.state = AutomationState.PAUSED_FOR_HUMAN
            self.challenge_detected.emit(reason)

        def on_challenge_still_present(msg: str):
            self.challenge_still_present.emit(msg)

        def on_challenge_resolved():
            self.state = AutomationState.RUNNING
            self.challenge_resolved.emit()

        try:
            # Set cancellation checker dynamically on the scraper
            self.scraper.is_cancelled = lambda: self._is_cancelled

            # Initialize HumanChallengeCoordinator for HITL Workflow #5
            self.coordinator = HumanChallengeCoordinator(
                scraper=self.scraper,
                timeout_seconds=self.challenge_timeout_seconds,
                on_detected=on_challenge_detected,
                on_still_present=on_challenge_still_present,
                on_resolved=on_challenge_resolved,
                is_cancelled_func=lambda: self._is_cancelled
            )
            self.scraper.on_challenge = self.coordinator.handle_challenge

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

            self.state = AutomationState.COMPLETED

            # 2. Export or hand off for human review (HITL Workflow #4)
            if self.auto_export:
                final_path = self.exporter.export(scraped_items, self.export_path)
                self.scraping_finished.emit(final_path)
            else:
                self.data_ready.emit(scraped_items)

        except InterruptedError as e:
            self.state = AutomationState.CANCELLING
            # Handle cancellation: save what we have or emit for human review
            if scraped_items:
                if self.auto_export:
                    try:
                        final_path = self.exporter.export(scraped_items, self.export_path)
                        self.scraping_finished.emit(final_path)
                    except Exception as save_err:
                        self.failed.emit(f"Scrape cancelled, failed to save partially collected data: {save_err}")
                else:
                    self.data_ready.emit(scraped_items)
            else:
                self.failed.emit(str(e))
                
        except Exception as e:
            self.state = AutomationState.FAILED
            # Catch and bubble up any other fatal errors
            self.failed.emit(str(e))

    def resume(self):
        """Signals the paused worker thread to resume after human intervention."""
        if self.coordinator:
            self.coordinator.resume()

    def cancel(self):
        """Sets flag to gracefully request cancellation of scraping loop."""
        self._is_cancelled = True
        self.state = AutomationState.CANCELLING
        if self.coordinator:
            self.coordinator.cancel()
