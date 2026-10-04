import os
import logging
from typing import List, Optional
from PySide6.QtCore import QThread, Signal

from src.core.models import BusinessItem, BatchJob, BatchJobResult
from src.core.batch_queue import BatchQueue, generate_batch_output_path
from src.core.interfaces.scraper import ScraperInterface
from src.core.interfaces.exporter import ExporterInterface

logger = logging.getLogger(__name__)


class BatchScrapeOrchestrator(QThread):
    """
    QThread worker that orchestrates sequential batch processing of multiple search jobs.
    Runs in the background without freezing the GUI thread.
    Communicates progress and lifecycle events via Qt signals.
    """
    # Signals
    batch_started = Signal(int)                          # total_jobs
    job_started = Signal(int, int, BatchJob)             # current_job_num (1-based), total_jobs, BatchJob
    job_item_scraped = Signal(int, int, BusinessItem)    # current_job_num, total_jobs, BusinessItem
    job_progress = Signal(int, int, int, int)            # current_job_num, total_jobs, scraped_count, limit
    job_finished = Signal(int, int, BatchJobResult)      # current_job_num, total_jobs, BatchJobResult
    batch_finished = Signal(str, list)                   # summary_report_text, list of BatchJobResult
    batch_cancelled = Signal()                           # Triggered when user cancels
    batch_failed = Signal(str)                           # Fatal error preventing batch run

    def __init__(
        self,
        queue: BatchQueue,
        scraper: ScraperInterface,
        exporter: ExporterInterface,
        output_dir: str,
        parent=None
    ) -> None:
        super().__init__(parent)
        self.queue = queue
        self.scraper = scraper
        self.exporter = exporter
        self.output_dir = output_dir
        self._is_cancelled = False

    def run(self) -> None:
        """Executes the batch processing loop sequentially."""
        if self.queue.is_empty():
            self.batch_failed.emit("Batch queue is empty. No jobs to process.")
            return

        total_jobs = self.queue.total_jobs
        logger.info(f"Starting batch queue execution ({total_jobs} jobs total)...")
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

            try:
                # Dynamic cancellation check for scraper
                self.scraper.is_cancelled = lambda: self._is_cancelled

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
            self.batch_cancelled.emit()
        else:
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

    def cancel(self) -> None:
        """Sets flag to gracefully cancel batch processing."""
        self._is_cancelled = True
        self.queue.cancel()
