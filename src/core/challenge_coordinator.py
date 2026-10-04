import logging
import threading
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


class HumanChallengeCoordinator:
    """
    Coordinates safe, thread-safe pause and resume for Human-in-the-Loop Bot-Challenge Resolution.
    
    Shared by both single-job ScrapeOrchestrator and BatchScrapeOrchestrator to avoid
    code duplication and guarantee identical, deterministic behavior.
    """
    def __init__(
        self,
        scraper: Any,
        timeout_seconds: int = 300,
        on_detected: Optional[Callable[[str], None]] = None,
        on_still_present: Optional[Callable[[str], None]] = None,
        on_resolved: Optional[Callable[[], None]] = None,
        is_cancelled_func: Optional[Callable[[], bool]] = None
    ) -> None:
        self.scraper = scraper
        self.timeout_seconds = timeout_seconds
        self.on_detected = on_detected
        self.on_still_present = on_still_present
        self.on_resolved = on_resolved
        self.is_cancelled_func = is_cancelled_func or (lambda: False)
        self._resume_event = threading.Event()

    def handle_challenge(self, page: Any, reason: str) -> bool:
        """
        Executes the pause loop when a challenge is detected.
        Safely blocks the background worker thread without busy-waiting.
        
        Returns:
            bool: True if challenge was resolved and scraping should resume;
                  False if cancelled or timed out.
        """
        logger.warning("Potential verification challenge detected.")
        logger.info("Automation paused for human intervention.")
        logger.info("Waiting for user action.")

        if self.on_detected:
            self.on_detected(reason)

        elapsed = 0.0
        step = 0.25

        while True:
            self._resume_event.clear()

            while not self._resume_event.wait(timeout=step):
                if self.is_cancelled_func():
                    logger.warning("Human intervention cancelled.")
                    logger.info("Scraping cancelled.")
                    return False

                elapsed += step
                if elapsed >= self.timeout_seconds:
                    logger.warning("Human intervention timeout reached.")
                    logger.info("Scraping cancelled safely.")
                    return False

            # Resume event was set
            logger.info("Human selected Resume.")

            if self.is_cancelled_func():
                logger.warning("Human intervention cancelled.")
                logger.info("Scraping cancelled.")
                return False

            # Re-check challenge presence
            detector = getattr(self.scraper, "challenge_detector", None)
            still_present = False
            if detector and hasattr(detector, "is_challenge_detected"):
                still_present = detector.is_challenge_detected(page)

            if still_present:
                logger.warning("Verification challenge still detected.")
                if self.on_still_present:
                    self.on_still_present(
                        "Verification challenge is still detected in the browser. Please complete it, then click Resume."
                    )
                continue
            else:
                logger.info("Verification no longer detected.")
                logger.info("Human intervention completed.")
                logger.info("Resuming automated scraping.")
                if self.on_resolved:
                    self.on_resolved()
                return True

    def resume(self) -> None:
        """Signals the waiting pause loop to re-check and resume."""
        detector = getattr(self.scraper, "challenge_detector", None)
        if detector and hasattr(detector, "resolve_simulated_challenge"):
            detector.resolve_simulated_challenge()
        self._resume_event.set()

    def cancel(self) -> None:
        """Unblocks the pause loop immediately on user cancellation."""
        self._resume_event.set()
