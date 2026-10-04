import os
import logging
from typing import List, Optional
from PySide6.QtCore import QThread, Signal

from src.core.models import BusinessItem, BatchJob, BatchJobResult, AutomationState
from src.core.batch_queue import BatchQueue, generate_batch_output_path
from src.core.interfaces.scraper import ScraperInterface
from src.core.interfaces.exporter import ExporterInterface
from src.core.challenge_coordinator import HumanChallengeCoordinator

logger = logging.getLogger(__name__)


class BatchScrapeOrchestrator(QThread):
    """
    QThread worker that orchestrates sequential batch processing of multiple search jobs.
    Runs in the background without freezing the GUI thread.
    Communicates progress and lifecycle events via Qt signals.
    Supports Human-in-the-Loop Bot Challenge Resolution (HITL Workflow #5).
    """
    # Signals
    batch_started = Signal(int)                          # total_jobs
    job_started = Signal(int, int, BatchJob)             # current_job_num (1-based), total_jobs, BatchJob
    job_item_scraped = Signal(int, int, BusinessItem)    # current_job_num, total_jobs, BusinessItem
    job_progress = Signal(int, int, int, int)            # current_job_num, total_jobs, scraped_count, limit
    job_data_ready = Signal(int, int, BatchJob, list, str) # current_job_num, total_jobs, job, items, export_path
    job_finished = Signal(int, int, BatchJobResult)      # current_job_num, total_jobs, BatchJobResult
    batch_finished = Signal(str, list)                   # summary_report_text, list of BatchJobResult
    batch_cancelled = Signal()                           # Triggered when user cancels
    batch_failed = Signal(str)                           # Fatal error preventing batch run
    challenge_detected = Signal(int, int, str)           # current_job_num, total_jobs, reason
    challenge_still_present = Signal(str)                # warning message
    challenge_resolved = Signal()                        # challenge cleared
    state_changed = Signal(str)                          # AutomationState

    def __init__(
        self,
        queue: BatchQueue,
        scraper: ScraperInterface,
        exporter: ExporterInterface,
        output_dir: str,
        auto_export: bool = True,
        challenge_timeout_seconds: int = 300,
        parent=None
    ) -> None:
        super().__init__(parent)
        self.queue = queue
        self.scraper = scraper
        self.exporter = exporter
        self.output_dir = output_dir
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

    def run(self) -> None:
        """Executes the batch processing loop sequentially."""
        if self.queue.is_empty():
            self.state = AutomationState.FAILED
            self.batch_failed.emit("Batch queue is empty. No jobs to process.")
            return

        total_jobs = self.queue.total_jobs
        logger.info(f"Starting batch queue execution ({total_jobs} jobs total)...")
        self.state = AutomationState.RUNNING
        self.batch_started.emit(total_jobs)

        while not self.queue.is_finished():
            # Check for cancellation before starting the next job
            if self._is_cancelled:
                logger.warning("Batch processing halted by user request.")
                break

            job = self.queue.get_next_job()
            if job is None:
                break

            current_job_num = self.queue.current_index  # 1-based because get_next_job increments
            logger.info(
                f"Starting batch job {current_job_num}/{total_jobs}: "
                f"'{job.keyword}' in '{job.location}' (Limit: {job.max_results})"
            )
            self.job_started.emit(current_job_num, total_jobs, job)

            scraped_items: List[BusinessItem] = []
            export_path = generate_batch_output_path(job, self.output_dir)

            def progress_callback(item: BusinessItem) -> None:
                if self._is_cancelled:
                    raise InterruptedError("Batch cancelled by user.")
                scraped_items.append(item)
                self.job_item_scraped.emit(current_job_num, total_jobs, item)
                self.job_progress.emit(current_job_num, total_jobs, len(scraped_items), job.max_results)

            def on_challenge_detected(reason: str) -> None:
                self.state = AutomationState.PAUSED_FOR_HUMAN
                self.challenge_detected.emit(current_job_num, total_jobs, reason)

            def on_challenge_still_present(msg: str) -> None:
                self.challenge_still_present.emit(msg)

            def on_challenge_resolved() -> None:
                self.state = AutomationState.RUNNING
                self.challenge_resolved.emit()

            try:
                # Dynamic cancellation check for scraper
                self.scraper.is_cancelled = lambda: self._is_cancelled

                # Setup challenge coordinator for this batch job
                self.coordinator = HumanChallengeCoordinator(
                    scraper=self.scraper,
                    timeout_seconds=self.challenge_timeout_seconds,
                    on_detected=on_challenge_detected,
                    on_still_present=on_challenge_still_present,
                    on_resolved=on_challenge_resolved,
                    is_cancelled_func=lambda: self._is_cancelled
                )
                self.scraper.on_challenge = self.coordinator.handle_challenge

                # 1. Scrape with automated website enrichment (reused from scraper)
                self.scraper.scrape(
                    query=job.keyword,
                    location=job.location,
                    limit=job.max_results,
                    progress_callback=progress_callback
                )

                if self._is_cancelled:
                    raise InterruptedError("Batch cancelled by user.")

                if not scraped_items:
                    raise ValueError(f"No business listings found for query '{job.keyword}' in '{job.location}'.")

                if self.auto_export:
                    # 2. Export collected leads to dedicated Excel file
                    final_path = self.exporter.export(scraped_items, export_path)
                    logger.info(
                        f"Job {current_job_num} completed: {len(scraped_items)} businesses. "
                        f"Export completed: {os.path.basename(final_path)}"
                    )

                    result = BatchJobResult(
                        job=job,
                        success=True,
                        count=len(scraped_items),
                        export_path=final_path
                    )
                    self.queue.record_result(result)
                    self.job_finished.emit(current_job_num, total_jobs, result)
                else:
                    self.job_data_ready.emit(current_job_num, total_jobs, job, scraped_items, export_path)

            except InterruptedError:
                logger.warning(f"Job {current_job_num} interrupted by user.")
                # Save partial results if any
                if scraped_items:
                    try:
                        final_path = self.exporter.export(scraped_items, export_path)
                        logger.info(f"Saved {len(scraped_items)} partial leads to {os.path.basename(final_path)}")
                        self.queue.record_result(BatchJobResult(
                            job=job,
                            success=True,
                            count=len(scraped_items),
                            export_path=final_path
                        ))
                    except Exception as export_err:
                        logger.error(f"Failed to export partial leads: {export_err}")
                break

            except Exception as e:
                # Job failure: Log error, record result, and DO NOT terminate the entire batch!
                logger.error(f"Job {current_job_num} failed: {e}")
                logger.info("Continuing with next batch job.")
                
                result = BatchJobResult(
                    job=job,
                    success=False,
                    count=0,
                    error_message=str(e)
                )
                self.queue.record_result(result)
                self.job_finished.emit(current_job_num, total_jobs, result)

        # Batch finalization
        if self._is_cancelled:
            self.state = AutomationState.CANCELLING
            self.batch_cancelled.emit()
        else:
            self.state = AutomationState.COMPLETED
            summary = self.queue.generate_summary()
            logger.info(f"Batch completed: {self.queue.completed_count} successful, {self.queue.failed_count} failed.")
            
            # Save summary text file in the output directory
            try:
                summary_file = os.path.join(self.output_dir, "batch_summary.txt")
                with open(summary_file, "w", encoding="utf-8") as f:
                    f.write(summary)
            except Exception as err:
                logger.warning(f"Could not save batch_summary.txt: {err}")
                
            self.batch_finished.emit(summary, self.queue.results)

    def resume(self) -> None:
        """Signals paused worker thread to resume scraping after human intervention."""
        if self.coordinator:
            self.coordinator.resume()

    def cancel(self) -> None:
        """Sets flag to gracefully cancel batch processing."""
        self._is_cancelled = True
        self.state = AutomationState.CANCELLING
        if self.coordinator:
            self.coordinator.cancel()
        self.queue.cancel()
