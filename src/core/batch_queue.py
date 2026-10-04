import os
import re
import json
import datetime
from typing import List, Optional, Dict, Any
from src.core.models import BatchJob, BatchJobResult


def sanitize_filename(name: str) -> str:
    """
    Sanitizes string to be safe across Windows, Linux, and macOS filesystems.
    Removes invalid characters, punctuation, control characters, and collapses whitespace.
    """
    if not name:
        return "unnamed"
    # Replace any non-alphanumeric, non-hyphen character sequence with a single underscore
    cleaned = re.sub(r'[^\w\-]+', '_', name)
    # Strip leading/trailing underscores and hyphens
    cleaned = cleaned.strip('_-')
    return cleaned if cleaned else "unnamed"


def generate_batch_output_path(
    job: BatchJob,
    base_dir: str,
    timestamp: Optional[datetime.datetime] = None
) -> str:
    """
    Generates a unique, collision-free Excel output file path for a batch job.
    Format: <keyword>_<location>_<timestamp>.xlsx
    Example: Dentist_Ahmedabad_2026-10-04_101530.xlsx
    """
    if timestamp is None:
        timestamp = datetime.datetime.now()
    
    ts_str = timestamp.strftime("%Y-%m-%d_%H%M%S")
    clean_kw = sanitize_filename(job.keyword)
    clean_loc = sanitize_filename(job.location)
    base_name = f"{clean_kw}_{clean_loc}_{ts_str}"
    
    os.makedirs(base_dir, exist_ok=True)
    candidate_path = os.path.join(base_dir, f"{base_name}.xlsx")
    
    # Avoid accidental file overwrite if candidate exists
    counter = 1
    while os.path.exists(candidate_path):
        candidate_path = os.path.join(base_dir, f"{base_name}_{counter}.xlsx")
        counter += 1
        
    return candidate_path


def load_batch_jobs_from_file(file_path: str) -> List[BatchJob]:
    """
    Loads and validates batch jobs from a JSON file.
    
    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If JSON is invalid or job fields fail validation.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Batch file not found: {file_path}")
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in '{os.path.basename(file_path)}': {e}") from e
    except Exception as e:
        raise ValueError(f"Could not read batch file '{os.path.basename(file_path)}': {e}") from e

    if not isinstance(data, list):
        raise ValueError("Batch file must contain a JSON array (list) of job objects.")
        
    if len(data) == 0:
        raise ValueError("Batch file contains 0 jobs. Please provide at least one job.")

    jobs: List[BatchJob] = []
    for idx, entry in enumerate(data, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Job #{idx} must be a JSON object.")
        
        # Check required keys
        for key in ("keyword", "location", "max_results"):
            if key not in entry:
                raise ValueError(f"Job #{idx} is missing required field: '{key}'.")
                
        keyword = entry["keyword"]
        location = entry["location"]
        max_results = entry["max_results"]
        
        if not isinstance(keyword, str) or not keyword.strip():
            raise ValueError(f"Job #{idx} has invalid keyword: must be a non-empty string.")
            
        if not isinstance(location, str) or not location.strip():
            raise ValueError(f"Job #{idx} has invalid location: must be a non-empty string.")
            
        if not isinstance(max_results, int) or isinstance(max_results, bool) or max_results <= 0:
            raise ValueError(f"Job #{idx} has invalid max_results: must be a positive integer greater than 0.")

        jobs.append(BatchJob(
            keyword=keyword.strip(),
            location=location.strip(),
            max_results=max_results
        ))

    return jobs


def parse_simple_batch_input(text: str) -> List[BatchJob]:
    """
    Parses simple user text lines into BatchJob objects.
    Expected format per line:
        Keyword, Location, Limit
    Example:
        Dentist, Ahmedabad, 20
        Restaurant, Ahmedabad, 20
        Hotel, Surat, 20

    Supports:
        - Comma separation (e.g. "Dentist, Ahmedabad, 20")
        - Handling city/state combos with commas when limit is the trailing number (e.g. "Dentist, Boston, MA, 25")
        - Skipping blank lines and comment lines starting with '#'
    """
    if not text or not text.strip():
        raise ValueError("Simple batch input is empty. Please enter at least one job.")

    jobs: List[BatchJob] = []
    lines = text.strip().splitlines()

    for line_num, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 3:
            raise ValueError(
                f"Line {line_num}: Invalid format '{raw_line}'. "
                f"Expected 'Keyword, Location, Limit' (e.g. 'Dentist, Ahmedabad, 20')."
            )

        keyword = parts[0]
        limit_str = parts[-1]
        # Recombine intermediate parts as location in case of commas like "Boston, MA"
        location = ", ".join(parts[1:-1])

        if not limit_str.isdigit() or int(limit_str) <= 0:
            raise ValueError(
                f"Line {line_num}: Limit must be a positive integer greater than 0, got '{limit_str}'."
            )

        jobs.append(BatchJob(
            keyword=keyword,
            location=location,
            max_results=int(limit_str)
        ))

    if not jobs:
        raise ValueError("No valid jobs found. Please provide at least one job in the format 'Keyword, Location, Limit'.")

    return jobs


class BatchQueue:
    """
    Sequential queue abstraction managing an ordered list of BatchJob objects.
    Tracks progression, metrics, and error outcomes across the batch run.
    """
    def __init__(self, jobs: Optional[List[BatchJob]] = None) -> None:
        self._jobs: List[BatchJob] = list(jobs) if jobs else []
        self._current_index: int = 0
        self._results: List[BatchJobResult] = []
        self._is_cancelled: bool = False

    def add_job(self, job: BatchJob) -> None:
        """Appends a new job to the end of the queue."""
        self._jobs.append(job)

    def add_jobs(self, jobs: List[BatchJob]) -> None:
        """Appends multiple jobs preserving their order."""
        self._jobs.extend(jobs)

    @property
    def total_jobs(self) -> int:
        """Returns the total number of jobs in the queue."""
        return len(self._jobs)

    @property
    def current_index(self) -> int:
        """Returns the current 0-based job index."""
        return self._current_index

    @property
    def current_job_number(self) -> int:
        """Returns the current 1-based job number."""
        return min(self._current_index + 1, self.total_jobs)

    def get_next_job(self) -> Optional[BatchJob]:
        """Pops and returns the next BatchJob in sequence, advancing the index."""
        if self._current_index < len(self._jobs):
            job = self._jobs[self._current_index]
            self._current_index += 1
            return job
        return None

    def peek_current(self) -> Optional[BatchJob]:
        """Returns the current BatchJob without advancing the queue."""
        if self._current_index < len(self._jobs):
            return self._jobs[self._current_index]
        return None

    def record_result(self, result: BatchJobResult) -> None:
        """Stores the execution result of a processed job."""
        self._results.append(result)

    @property
    def results(self) -> List[BatchJobResult]:
        """Returns list of recorded BatchJobResult objects."""
        return list(self._results)

    @property
    def completed_count(self) -> int:
        """Count of jobs that completed successfully."""
        return sum(1 for r in self._results if r.success)

    @property
    def failed_count(self) -> int:
        """Count of jobs that encountered errors."""
        return sum(1 for r in self._results if not r.success)

    @property
    def total_leads_collected(self) -> int:
        """Total sum of businesses extracted across all successful jobs."""
        return sum(r.count for r in self._results if r.success)

    def is_finished(self) -> bool:
        """Checks if all queued jobs have been dispatched."""
        return self._current_index >= len(self._jobs)

    def is_empty(self) -> bool:
        """Checks if the queue contains no jobs."""
        return len(self._jobs) == 0

    def cancel(self) -> None:
        """Flags the batch queue as cancelled."""
        self._is_cancelled = True

    @property
    def is_cancelled(self) -> bool:
        """Returns whether the queue has been cancelled."""
        return self._is_cancelled

    def reset(self) -> None:
        """Resets the queue progress counters to start from the beginning."""
        self._current_index = 0
        self._results.clear()
        self._is_cancelled = False

    def generate_summary(self) -> str:
        """
        Builds a human-readable batch execution summary.
        """
        lines = [
            "==================================================",
            "             BATCH EXECUTION SUMMARY              ",
            "==================================================",
            f"Total Jobs:               {self.total_jobs}",
            f"Successful Jobs:          {self.completed_count}",
            f"Failed Jobs:              {self.failed_count}",
            f"Total Businesses Found:   {self.total_leads_collected}",
            "--------------------------------------------------"
        ]
        
        for idx, res in enumerate(self._results, start=1):
            status = "SUCCESS" if res.success else "FAILED"
            details = f"{res.count} records saved" if res.success else f"Error: {res.error_message}"
            lines.append(f"Job {idx}: {res.job.keyword} / {res.job.location} -> [{status}] {details}")
            if res.export_path:
                lines.append(f"       File: {os.path.basename(res.export_path)}")
                
        lines.append("==================================================")
        return "\n".join(lines)
