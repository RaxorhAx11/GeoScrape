import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
import json
import datetime

from src.core.models import BatchJob, BatchJobResult, BusinessItem
from src.core.batch_queue import (
    BatchQueue,
    sanitize_filename,
    generate_batch_output_path,
    load_batch_jobs_from_file,
    parse_simple_batch_input
)
from src.core.batch_orchestrator import BatchScrapeOrchestrator


class TestBatchModelsAndQueue(unittest.TestCase):
    """Unit tests for BatchJob validation, JSON loading, Queue ordering, and Sanitization."""

    def test_batch_job_valid(self):
        job = BatchJob(keyword="Dentist", location="Ahmedabad", max_results=20)
        self.assertEqual(job.keyword, "Dentist")
        self.assertEqual(job.location, "Ahmedabad")
        self.assertEqual(job.max_results, 20)

    def test_batch_job_empty_keyword(self):
        with self.assertRaises(ValueError):
            BatchJob(keyword="", location="Ahmedabad", max_results=20)
        with self.assertRaises(ValueError):
            BatchJob(keyword="   ", location="Ahmedabad", max_results=20)

    def test_batch_job_empty_location(self):
        with self.assertRaises(ValueError):
            BatchJob(keyword="Dentist", location="", max_results=20)
        with self.assertRaises(ValueError):
            BatchJob(keyword="Dentist", location="   ", max_results=20)

    def test_batch_job_invalid_max_results(self):
        with self.assertRaises(ValueError):
            BatchJob(keyword="Dentist", location="Ahmedabad", max_results=0)
        with self.assertRaises(ValueError):
            BatchJob(keyword="Dentist", location="Ahmedabad", max_results=-10)
        with self.assertRaises(ValueError):
            BatchJob(keyword="Dentist", location="Ahmedabad", max_results="20")  # type: ignore
        with self.assertRaises(ValueError):
            BatchJob(keyword="Dentist", location="Ahmedabad", max_results=True)  # type: ignore

    def test_load_batch_jobs_valid_json(self):
        data = [
            {"keyword": "Dentist", "location": "Ahmedabad", "max_results": 20},
            {"keyword": "Restaurant", "location": "Ahmedabad", "max_results": 15},
            {"keyword": "Hotel", "location": "Surat", "max_results": 25}
        ]
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            jobs = load_batch_jobs_from_file(temp_path)
            self.assertEqual(len(jobs), 3)
            self.assertEqual(jobs[0].keyword, "Dentist")
            self.assertEqual(jobs[1].keyword, "Restaurant")
            self.assertEqual(jobs[2].location, "Surat")
        finally:
            os.remove(temp_path)

    def test_load_batch_jobs_nonexistent_file(self):
        with self.assertRaises(FileNotFoundError):
            load_batch_jobs_from_file("non_existent_file_path_12345.json")

    def test_load_batch_jobs_malformed_json(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
            f.write("{ invalid json content ...")
            temp_path = f.name

        try:
            with self.assertRaises(ValueError):
                load_batch_jobs_from_file(temp_path)
        finally:
            os.remove(temp_path)

    def test_load_batch_jobs_not_a_list(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
            json.dump({"keyword": "Dentist", "location": "Ahmedabad", "max_results": 20}, f)
            temp_path = f.name

        try:
            with self.assertRaises(ValueError):
                load_batch_jobs_from_file(temp_path)
        finally:
            os.remove(temp_path)

    def test_load_batch_jobs_empty_list(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
            json.dump([], f)
            temp_path = f.name

        try:
            with self.assertRaises(ValueError):
                load_batch_jobs_from_file(temp_path)
        finally:
            os.remove(temp_path)

    def test_load_batch_jobs_missing_fields(self):
        data = [{"keyword": "Dentist", "location": "Ahmedabad"}]  # missing max_results
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            with self.assertRaises(ValueError):
                load_batch_jobs_from_file(temp_path)
        finally:
            os.remove(temp_path)

    def test_parse_simple_batch_input_valid(self):
        text = (
            "Dentist, Ahmedabad, 20\n"
            "Restaurant, Ahmedabad, 20\n"
            "Hotel, Surat, 20\n"
        )
        jobs = parse_simple_batch_input(text)
        self.assertEqual(len(jobs), 3)
        self.assertEqual(jobs[0].keyword, "Dentist")
        self.assertEqual(jobs[0].location, "Ahmedabad")
        self.assertEqual(jobs[0].max_results, 20)

        self.assertEqual(jobs[1].keyword, "Restaurant")
        self.assertEqual(jobs[1].location, "Ahmedabad")
        self.assertEqual(jobs[1].max_results, 20)

        self.assertEqual(jobs[2].keyword, "Hotel")
        self.assertEqual(jobs[2].location, "Surat")
        self.assertEqual(jobs[2].max_results, 20)

    def test_parse_simple_batch_input_with_commas_in_location(self):
        text = "Dentist, Boston, MA, 25\nCoffee, Austin, TX, 10"
        jobs = parse_simple_batch_input(text)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].keyword, "Dentist")
        self.assertEqual(jobs[0].location, "Boston, MA")
        self.assertEqual(jobs[0].max_results, 25)
        self.assertEqual(jobs[1].keyword, "Coffee")
        self.assertEqual(jobs[1].location, "Austin, TX")
        self.assertEqual(jobs[1].max_results, 10)

    def test_parse_simple_batch_input_comments_and_empty_lines(self):
        text = (
            "# This is a comment\n"
            "Dentist, Ahmedabad, 20\n\n"
            "   \n"
            "# Another comment\n"
            "Restaurant, Ahmedabad, 15\n"
        )
        jobs = parse_simple_batch_input(text)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].keyword, "Dentist")
        self.assertEqual(jobs[1].keyword, "Restaurant")

    def test_parse_simple_batch_input_empty(self):
        with self.assertRaises(ValueError):
            parse_simple_batch_input("")
        with self.assertRaises(ValueError):
            parse_simple_batch_input("   \n\n   ")

    def test_parse_simple_batch_input_invalid_format(self):
        # Missing limit
        with self.assertRaises(ValueError):
            parse_simple_batch_input("Dentist, Ahmedabad")

    def test_parse_simple_batch_input_invalid_limit(self):
        # Non-numeric or non-positive limit
        with self.assertRaises(ValueError):
            parse_simple_batch_input("Dentist, Ahmedabad, zero")
        with self.assertRaises(ValueError):
            parse_simple_batch_input("Dentist, Ahmedabad, 0")
        with self.assertRaises(ValueError):
            parse_simple_batch_input("Dentist, Ahmedabad, -5")

    def test_queue_ordering_and_tracking(self):
        jobs = [
            BatchJob("Job1", "Loc1", 10),
            BatchJob("Job2", "Loc2", 20),
            BatchJob("Job3", "Loc3", 30)
        ]
        queue = BatchQueue(jobs)
        self.assertEqual(queue.total_jobs, 3)
        self.assertFalse(queue.is_finished())
        self.assertFalse(queue.is_empty())

        # Check FIFO sequence
        j1 = queue.get_next_job()
        self.assertEqual(j1.keyword, "Job1")
        self.assertEqual(queue.current_index, 1)

        j2 = queue.get_next_job()
        self.assertEqual(j2.keyword, "Job2")
        self.assertEqual(queue.current_index, 2)

        j3 = queue.get_next_job()
        self.assertEqual(j3.keyword, "Job3")
        self.assertEqual(queue.current_index, 3)

        self.assertTrue(queue.is_finished())
        self.assertIsNone(queue.get_next_job())

        # Test reset
        queue.reset()
        self.assertEqual(queue.current_index, 0)
        self.assertFalse(queue.is_finished())

    def test_filename_sanitization(self):
        raw = 'Dentist / Dental <Care> & Clinic: "Best"? *Ahmedabad*'
        cleaned = sanitize_filename(raw)
        self.assertNotIn("/", cleaned)
        self.assertNotIn("<", cleaned)
        self.assertNotIn(">", cleaned)
        self.assertNotIn(":", cleaned)
        self.assertNotIn('"', cleaned)
        self.assertNotIn("?", cleaned)
        self.assertNotIn("*", cleaned)
        self.assertTrue(len(cleaned) > 0)

        # Empty fallback
        self.assertEqual(sanitize_filename(""), "unnamed")
        self.assertEqual(sanitize_filename("   "), "unnamed")

    def test_generate_batch_output_path(self):
        job = BatchJob("Cafe & Bistro", "Austin / TX", 10)
        temp_dir = tempfile.mkdtemp()
        fixed_time = datetime.datetime(2026, 10, 4, 10, 15, 30)
        
        path = generate_batch_output_path(job, temp_dir, timestamp=fixed_time)
        self.assertTrue(path.endswith(".xlsx"))
        self.assertIn("Cafe_Bistro", path)
        self.assertIn("Austin_TX", path)
        self.assertIn("2026-10-04_101530", path)

        # Collision avoidance test: create a dummy file at the generated path
        with open(path, "w") as f:
            f.write("dummy")

        path2 = generate_batch_output_path(job, temp_dir, timestamp=fixed_time)
        self.assertNotEqual(path, path2)
        self.assertTrue(path2.endswith("_1.xlsx"))

    def test_batch_summary_generation(self):
        queue = BatchQueue()
        job1 = BatchJob("Dentist", "Ahmedabad", 20)
        job2 = BatchJob("Restaurant", "Surat", 20)
        
        queue.add_job(job1)
        queue.add_job(job2)

        queue.record_result(BatchJobResult(
            job=job1,
            success=True,
            count=18,
            export_path="C:/export/Dentist_Ahmedabad.xlsx"
        ))
        queue.record_result(BatchJobResult(
            job=job2,
            success=False,
            count=0,
            error_message="Timeout loading search results"
        ))

        summary = queue.generate_summary()
        self.assertIn("BATCH EXECUTION SUMMARY", summary)
        self.assertIn("Total Jobs:               2", summary)
        self.assertIn("Successful Jobs:          1", summary)
        self.assertIn("Failed Jobs:              1", summary)
        self.assertIn("Total Businesses Found:   18", summary)
        self.assertIn("Dentist / Ahmedabad -> [SUCCESS] 18 records saved", summary)
        self.assertIn("Restaurant / Surat -> [FAILED] Error: Timeout loading search results", summary)


class TestBatchScrapeOrchestrator(unittest.TestCase):
    """Unit tests for BatchScrapeOrchestrator sequential execution, error resilience, and cancellation."""

    def setUp(self):
        self.mock_scraper = MagicMock()
        self.mock_exporter = MagicMock()
        self.temp_dir = tempfile.mkdtemp()

    def test_successful_sequential_processing(self):
        jobs = [
            BatchJob("Dentist", "Ahmedabad", 2),
            BatchJob("Cafe", "Surat", 2)
        ]
        queue = BatchQueue(jobs)

        # Mock scraper to simulate yielding items via progress callback
        def mock_scrape(query, location, limit, progress_callback):
            for i in range(limit):
                progress_callback(BusinessItem(
                    name=f"{query} {i+1}",
                    rating=4.5,
                    reviews_count=10,
                    category=query,
                    address=f"Street {i+1}, {location}",
                    phone="123456",
                    website=f"http://{query.lower()}{i+1}.com",
                    maps_url="http://maps.google.com"
                ))

        self.mock_scraper.scrape.side_effect = mock_scrape
        self.mock_exporter.export.side_effect = lambda items, path: path

        orchestrator = BatchScrapeOrchestrator(
            queue=queue,
            scraper=self.mock_scraper,
            exporter=self.mock_exporter,
            output_dir=self.temp_dir
        )

        job_finished_signals = []
        batch_finished_signals = []
        orchestrator.job_finished.connect(lambda cur, tot, res: job_finished_signals.append(res))
        orchestrator.batch_finished.connect(lambda summary, results: batch_finished_signals.append((summary, results)))

        # Run synchronously in test
        orchestrator.run()

        # Both jobs should have run sequentially
        self.assertEqual(len(job_finished_signals), 2)
        self.assertTrue(job_finished_signals[0].success)
        self.assertEqual(job_finished_signals[0].count, 2)
        self.assertTrue(job_finished_signals[1].success)
        self.assertEqual(job_finished_signals[1].count, 2)

        # 2 exports triggered
        self.assertEqual(self.mock_exporter.export.call_count, 2)

        # Batch finished signal received
        self.assertEqual(len(batch_finished_signals), 1)
        self.assertEqual(queue.completed_count, 2)
        self.assertEqual(queue.failed_count, 0)
        self.assertEqual(queue.total_leads_collected, 4)

    def test_one_failed_job_does_not_stop_remaining_jobs(self):
        """Job 1 -> SUCCESS, Job 2 -> FAILED, Job 3 -> SUCCESS. Entire batch must complete!"""
        jobs = [
            BatchJob("Dentist", "Ahmedabad", 2),
            BatchJob("FaultyQuery", "Nowhere", 2),
            BatchJob("Hotel", "Surat", 2)
        ]
        queue = BatchQueue(jobs)

        def mock_scrape(query, location, limit, progress_callback):
            if query == "FaultyQuery":
                raise RuntimeError("Maps search network error")
            for i in range(limit):
                progress_callback(BusinessItem(
                    name=f"{query} {i+1}",
                    rating=4.0,
                    reviews_count=5,
                    category=query,
                    address=f"Street {i+1}, {location}",
                    phone="123456",
                    website="http://example.com",
                    maps_url="http://maps.google.com"
                ))

        self.mock_scraper.scrape.side_effect = mock_scrape
        self.mock_exporter.export.side_effect = lambda items, path: path

        orchestrator = BatchScrapeOrchestrator(
            queue=queue,
            scraper=self.mock_scraper,
            exporter=self.mock_exporter,
            output_dir=self.temp_dir
        )

        job_results = []
        orchestrator.job_finished.connect(lambda cur, tot, res: job_results.append(res))

        orchestrator.run()

        # All 3 jobs dispatched
        self.assertEqual(len(job_results), 3)
        self.assertTrue(job_results[0].success)
        self.assertEqual(job_results[0].job.keyword, "Dentist")

        self.assertFalse(job_results[1].success)
        self.assertEqual(job_results[1].job.keyword, "FaultyQuery")
        self.assertIn("Maps search network error", job_results[1].error_message)

        self.assertTrue(job_results[2].success)
        self.assertEqual(job_results[2].job.keyword, "Hotel")

        # Exporter called for Job 1 and Job 3
        self.assertEqual(self.mock_exporter.export.call_count, 2)
        self.assertEqual(queue.completed_count, 2)
        self.assertEqual(queue.failed_count, 1)

    def test_batch_cancellation(self):
        """User cancellation halts batch processing immediately."""
        jobs = [
            BatchJob("Job1", "Loc1", 5),
            BatchJob("Job2", "Loc2", 5),
            BatchJob("Job3", "Loc3", 5)
        ]
        queue = BatchQueue(jobs)

        orchestrator = BatchScrapeOrchestrator(
            queue=queue,
            scraper=self.mock_scraper,
            exporter=self.mock_exporter,
            output_dir=self.temp_dir
        )

        cancelled_signals = []
        orchestrator.batch_cancelled.connect(lambda: cancelled_signals.append(True))

        # Simulate user cancelling during the scrape callback of Job 1
        def mock_scrape(query, location, limit, progress_callback):
            # First item scrapes fine
            progress_callback(BusinessItem(
                name="Item 1", rating=4.0, reviews_count=1, category="test",
                address="addr", phone="123", website="N/A", maps_url="maps"
            ))
            # Now user clicks cancel
            orchestrator.cancel()
            # Next callback invocation detects cancellation
            progress_callback(BusinessItem(
                name="Item 2", rating=4.0, reviews_count=1, category="test",
                address="addr", phone="123", website="N/A", maps_url="maps"
            ))

        self.mock_scraper.scrape.side_effect = mock_scrape
        self.mock_exporter.export.side_effect = lambda items, path: path

        orchestrator.run()

        # Cancellation signal received
        self.assertEqual(len(cancelled_signals), 1)
        # Job 2 and Job 3 should NEVER have run
        self.assertFalse(queue.is_finished())
        self.assertLess(queue.current_index, 3)


if __name__ == "__main__":
    unittest.main()
