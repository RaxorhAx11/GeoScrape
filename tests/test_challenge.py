import unittest
import time
import threading
import tempfile
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.core.models import BusinessItem, BatchJob, BatchJobResult, AutomationState

from src.core.batch_queue import BatchQueue
from src.core.orchestrator import ScrapeOrchestrator
from src.core.batch_orchestrator import BatchScrapeOrchestrator
from src.scraper.challenge_detector import ChallengeDetector
from src.scraper.playwright_scraper import PlaywrightScraper, ScraperConfig
from src.ui.components.challenge_dialog import ChallengeDialog

# Ensure QApplication exists for UI tests
app = QApplication.instance()
if app is None:
    app = QApplication([])


class MockPage:
    """Helper mock simulating a Playwright Page."""
    def __init__(self, url: str = "https://www.google.com/maps", title: str = "Google Maps", body_text: str = "") -> None:
        self._url = url
        self._title = title
        self._body_text = body_text
        self._selectors = {}
        self._is_closed = False

    @property
    def url(self) -> str:
        return self._url

    def title(self) -> str:
        return self._title

    def is_closed(self) -> bool:
        return self._is_closed

    def locator(self, selector: str):
        mock_loc = MagicMock()
        if selector == "body":
            mock_loc.inner_text.return_value = self._body_text
        else:
            first_mock = MagicMock()
            is_visible = self._selectors.get(selector, False)
            first_mock.is_visible.return_value = is_visible
            mock_loc.first = first_mock
        return mock_loc

    def set_selector_visible(self, selector: str, visible: bool) -> None:
        self._selectors[selector] = visible


class TestChallengeDetector(unittest.TestCase):
    """Unit tests for ChallengeDetector (Step 2 & Step 13)."""

    def setUp(self):
        self.detector = ChallengeDetector(simulate_challenge=False)

    def test_no_challenge_detected_on_clean_page(self):
        """1. Clean normal Google Maps page detects no challenge."""
        page = MockPage(
            url="https://www.google.com/maps/search/dentist+boston",
            title="Google Maps",
            body_text="Boston Dental Care - 4.8 stars - Open now"
        )
        self.assertFalse(self.detector.is_challenge_detected(page))
        detected, reason = self.detector.detect_challenge(page)
        self.assertFalse(detected)
        self.assertIsNone(reason)

    def test_challenge_detected_from_supported_indicators(self):
        """2. Detects challenge from each supported visible indicator."""
        indicators = [
            ("verify you are human", "Please verify you are human to continue"),
            ("unusual traffic", "Our systems have detected unusual traffic from your computer network"),
            ("before you continue", "Before you continue to Google"),
            ("verification required", "Verification required to proceed"),
            ("prove you're not a robot", "Prove you're not a robot"),
            ("type the characters you see", "Type the characters you see in this picture"),
            ("security check", "Security check required")
        ]

        for phrase, body_content in indicators:
            page = MockPage(body_text=body_content)
            detected, reason = self.detector.detect_challenge(page)
            self.assertTrue(detected, f"Failed to detect indicator phrase: '{phrase}'")
            self.assertIn("Verification text detected", reason)

    def test_challenge_detected_from_url_and_selectors(self):
        """Detects challenge from redirect URL or captcha elements."""
        # URL indicator
        sorry_page = MockPage(url="https://www.google.com/sorry/index?continue=https://www.google.com/maps")
        detected, reason = self.detector.detect_challenge(sorry_page)
        self.assertTrue(detected)
        self.assertIn("Google unusual traffic block URL", reason)

        # DOM Selector indicator
        recaptcha_page = MockPage()
        recaptcha_page.set_selector_visible('iframe[src*="recaptcha"]', True)
        detected, reason = self.detector.detect_challenge(recaptcha_page)
        self.assertTrue(detected)
        self.assertIn("Challenge DOM element visible", reason)

    def test_false_positive_resistance(self):
        """3. Normal business listings with incidental text do not trigger false positive."""
        page = MockPage(
            url="https://www.google.com/maps/place/Human+Dynamics+Consulting",
            title="Human Dynamics Consulting - Google Maps",
            body_text="Human Dynamics Consulting provides workplace analytics and traffic optimization solutions."
        )
        self.assertFalse(self.detector.is_challenge_detected(page))

    def test_simulated_challenge_test_trigger(self):
        """4. Simulated development/test trigger activates and resolves cleanly."""
        sim_detector = ChallengeDetector(simulate_challenge=True)
        page = MockPage()
        detected, reason = sim_detector.detect_challenge(page)
        self.assertTrue(detected)
        self.assertIn("[TEST/DEVELOPMENT]", reason)

        # Resolve simulation
        sim_detector.resolve_simulated_challenge()
        self.assertFalse(sim_detector.is_challenge_detected(page))


class TestChallengeWorkflowOrchestrator(unittest.TestCase):
    """Tests for Worker Pause, Resume, Cancel, and Timeout (Steps 3-10)."""

    def setUp(self):
        self.mock_scraper = MagicMock()
        self.mock_scraper.is_cancelled = lambda: False
        self.mock_scraper.challenge_detector = ChallengeDetector(simulate_challenge=False)
        self.mock_exporter = MagicMock()

    def test_worker_enters_paused_for_human_state(self):
        """4. Worker enters PAUSED_FOR_HUMAN state when challenge is detected."""
        orchestrator = ScrapeOrchestrator(
            scraper=self.mock_scraper,
            exporter=self.mock_exporter,
            query="Dentist",
            location="Boston",
            limit=5,
            challenge_timeout_seconds=5
        )

        detected_signal_received = []
        orchestrator.challenge_detected.connect(lambda r: detected_signal_received.append(r), Qt.DirectConnection)

        def fake_scrape(query, location, limit, progress_callback):
            # Simulate scraper encountering challenge
            orchestrator.scraper.on_challenge(MockPage(), "Simulated bot test")
            return []

        self.mock_scraper.scrape.side_effect = fake_scrape

        # Run worker thread briefly
        orchestrator.start()
        time.sleep(0.3)

        # Verify state and signal
        self.assertEqual(orchestrator.state, AutomationState.PAUSED_FOR_HUMAN)
        self.assertEqual(len(detected_signal_received), 1)
        self.assertIn("Simulated bot test", detected_signal_received[0])

        # Cleanly cancel to terminate test thread
        orchestrator.cancel()
        orchestrator.wait(2000)

    def test_resume_signal_continues_worker(self):
        """5. Resume signal unblocks worker and continues automated scraping."""
        orchestrator = ScrapeOrchestrator(
            scraper=self.mock_scraper,
            exporter=self.mock_exporter,
            query="Dentist",
            location="Boston",
            limit=5,
            challenge_timeout_seconds=5
        )

        resolved_signal_received = []
        orchestrator.challenge_resolved.connect(lambda: resolved_signal_received.append(True), Qt.DirectConnection)
        data_ready_received = []
        orchestrator.data_ready.connect(lambda items: data_ready_received.append(items), Qt.DirectConnection)


        sample_item = BusinessItem(
            name="Alpha Dental", rating=4.5, reviews_count=10,
            category="Dentist", address="123 Main St", phone="555-0100",
            website="N/A", maps_url="https://maps.google.com"
        )

        def fake_scrape(query, location, limit, progress_callback):
            # 1. Trigger challenge
            resolved = orchestrator.scraper.on_challenge(MockPage(), "Simulated test")
            if resolved:
                # 2. Resumed: emit item and return
                progress_callback(sample_item)
                return [sample_item]
            return []

        self.mock_scraper.scrape.side_effect = fake_scrape

        orchestrator.start()
        time.sleep(0.3)
        self.assertEqual(orchestrator.state, AutomationState.PAUSED_FOR_HUMAN)

        # Human clicks Resume
        orchestrator.resume()
        orchestrator.wait(2000)

        # Verify resumed and finished
        self.assertEqual(len(resolved_signal_received), 1)
        self.assertEqual(len(data_ready_received), 1)
        self.assertEqual(data_ready_received[0][0].name, "Alpha Dental")

    def test_cancel_signal_cancels_worker_safely(self):
        """6. Cancel signal during challenge pauses halts worker safely."""
        orchestrator = ScrapeOrchestrator(
            scraper=self.mock_scraper,
            exporter=self.mock_exporter,
            query="Dentist",
            location="Boston",
            limit=5,
            challenge_timeout_seconds=5
        )

        def fake_scrape(query, location, limit, progress_callback):
            resolved = orchestrator.scraper.on_challenge(MockPage(), "Simulated test")
            if not resolved:
                raise InterruptedError("Cancelled during challenge")
            return []

        self.mock_scraper.scrape.side_effect = fake_scrape

        orchestrator.start()
        time.sleep(0.3)
        self.assertEqual(orchestrator.state, AutomationState.PAUSED_FOR_HUMAN)

        # Human clicks Cancel
        orchestrator.cancel()
        orchestrator.wait(2000)

        self.assertEqual(orchestrator.state, AutomationState.CANCELLING)
        self.assertFalse(orchestrator.isRunning())

    def test_human_timeout_cancels_safely(self):
        """7. Human intervention timeout triggers safe automated cancellation."""
        orchestrator = ScrapeOrchestrator(
            scraper=self.mock_scraper,
            exporter=self.mock_exporter,
            query="Dentist",
            location="Boston",
            limit=5,
            challenge_timeout_seconds=1  # 1 second timeout
        )

        def fake_scrape(query, location, limit, progress_callback):
            resolved = orchestrator.scraper.on_challenge(MockPage(), "Simulated test")
            if not resolved:
                raise InterruptedError("Timeout reached")
            return []

        self.mock_scraper.scrape.side_effect = fake_scrape

        orchestrator.start()
        # Wait for timeout to elapse
        time.sleep(1.5)
        orchestrator.wait(2000)

        self.assertEqual(orchestrator.state, AutomationState.CANCELLING)
        self.assertFalse(orchestrator.isRunning())

    def test_challenge_still_present_recheck(self):
        """Re-checks challenge upon Resume; stays paused if challenge still detected."""
        detector = MagicMock()
        # First check when resuming returns True (still present), second check returns False (solved)
        detector.is_challenge_detected.side_effect = [True, False]
        self.mock_scraper.challenge_detector = detector

        orchestrator = ScrapeOrchestrator(
            scraper=self.mock_scraper,
            exporter=self.mock_exporter,
            query="Dentist",
            location="Boston",
            limit=5,
            challenge_timeout_seconds=5
        )

        still_present_warnings = []
        orchestrator.challenge_still_present.connect(lambda msg: still_present_warnings.append(msg), Qt.DirectConnection)

        sample_item = BusinessItem(
            name="Alpha Dental", rating=4.5, reviews_count=10,
            category="Dentist", address="123 Main St", phone="555-0100",
            website="N/A", maps_url="https://maps.google.com"
        )

        def fake_scrape(query, location, limit, progress_callback):
            resolved = orchestrator.scraper.on_challenge(MockPage(), "Simulated test")
            if resolved:
                progress_callback(sample_item)
                return [sample_item]
            return []

        self.mock_scraper.scrape.side_effect = fake_scrape


        orchestrator.start()
        time.sleep(0.3)

        # 1. User clicks Resume while challenge is STILL present
        orchestrator.resume()
        time.sleep(0.3)
        self.assertEqual(len(still_present_warnings), 1)
        self.assertEqual(orchestrator.state, AutomationState.PAUSED_FOR_HUMAN)

        # 2. User solves challenge and clicks Resume again
        orchestrator.resume()
        orchestrator.wait(2000)
        self.assertEqual(orchestrator.state, AutomationState.COMPLETED)


class TestBatchChallengeWorkflow(unittest.TestCase):
    """Tests for Bot Challenge Resolution in Multi-Job Batch Processing."""

    def test_batch_challenge_resolves_and_continues_to_next_job(self):
        """Batch Job 1 encounters challenge -> Human resolves -> Job 1 completes -> Job 2 runs."""
        job1 = BatchJob("Dentist", "Boston", 1)
        job2 = BatchJob("Bakery", "Boston", 1)
        queue = BatchQueue([job1, job2])

        mock_scraper = MagicMock()
        mock_scraper.is_cancelled = lambda: False
        mock_scraper.challenge_detector = MagicMock()
        mock_scraper.challenge_detector.is_challenge_detected.return_value = False

        mock_exporter = MagicMock()
        mock_exporter.export.return_value = "/path/to/leads.xlsx"

        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = BatchScrapeOrchestrator(
                queue=queue,
                scraper=mock_scraper,
                exporter=mock_exporter,
                output_dir=temp_dir,
                auto_export=True,
                challenge_timeout_seconds=5
            )

            challenge_signals = []
            orchestrator.challenge_detected.connect(
                lambda cur, tot, r: challenge_signals.append((cur, tot, r)),
                Qt.DirectConnection
            )

            item1 = BusinessItem("Dental Care", 5.0, 10, "Dentist", "1 St", "555-1", "w1", "m1")
            item2 = BusinessItem("Sweet Bakery", 4.8, 15, "Bakery", "2 St", "555-2", "w2", "m2")

            call_count = 0
            def fake_batch_scrape(query, location, limit, progress_callback):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # Job 1 encounters challenge
                    resolved = orchestrator.scraper.on_challenge(MockPage(), "Simulated Job 1 Challenge")
                    if resolved:
                        progress_callback(item1)
                        return [item1]
                    return []
                else:
                    # Job 2 runs normally
                    progress_callback(item2)
                    return [item2]

            mock_scraper.scrape.side_effect = fake_batch_scrape

            orchestrator.start()
            time.sleep(0.3)

            # Verify Job 1 paused for human
            self.assertEqual(orchestrator.state, AutomationState.PAUSED_FOR_HUMAN)
            self.assertEqual(len(challenge_signals), 1)
            self.assertEqual(challenge_signals[0][0], 1)  # current job = 1

            # Human clicks Resume
            orchestrator.resume()
            orchestrator.wait(3000)

            # Verify both jobs completed!
            self.assertEqual(orchestrator.state, AutomationState.COMPLETED)
            self.assertEqual(queue.completed_count, 2)
            self.assertEqual(queue.failed_count, 0)



class TestChallengeDialogUI(unittest.TestCase):
    """Tests for ChallengeDialog UI component (Step 4)."""

    def test_challenge_dialog_elements_and_signals(self):
        """Verifies ChallengeDialog structure, buttons, timer and events."""
        dialog = ChallengeDialog(reason="Simulated reCAPTCHA block", timeout_seconds=60)
        self.assertIsNotNone(dialog.resume_button)
        self.assertIsNotNone(dialog.cancel_button)
        self.assertIsNotNone(dialog.alert_label)

        resume_fired = []
        cancel_fired = []
        dialog.resume_clicked.connect(lambda: resume_fired.append(True))
        dialog.cancel_clicked.connect(lambda: cancel_fired.append(True))

        # Test warning display
        dialog.show_still_present_warning("Verification still detected")
        self.assertFalse(dialog.alert_label.isHidden())
        self.assertIn("Verification still detected", dialog.alert_label.text())

        # Test resume button
        dialog.resume_button.click()
        self.assertEqual(len(resume_fired), 1)

        # Test cancel button
        dialog.cancel_button.click()
        self.assertEqual(len(cancel_fired), 1)
        dialog.close()


class TestControllerChallengeIntegration(unittest.TestCase):
    """Tests for Controller Challenge & Exception Resolution flow."""

    def setUp(self):
        from src.ui.main_window import MainWindow
        from src.ui.controller import MainWindowController

        self.view = MainWindow()
        self.mock_scraper = MagicMock()
        self.mock_exporter = MagicMock()
        self.controller = MainWindowController(self.view, self.mock_scraper, self.mock_exporter)

    def tearDown(self):
        self.controller.cleanup()
        self.view.close()

    def test_controller_challenge_detected_creates_dialog_and_pauses(self):
        """Controller creates ChallengeDialog and sets status to paused on challenge."""
        self.controller.on_challenge_detected("Unusual traffic detected")
        self.assertIsNotNone(self.controller.challenge_dialog)
        self.assertEqual(self.view.status_label.text(), "Human verification required.")

        # Re-check warning display
        self.controller.on_challenge_still_present("Verification is still active")
        self.assertFalse(self.controller.challenge_dialog.alert_label.isHidden())

        # Resolved closes dialog and updates status
        self.controller.on_challenge_resolved()
        self.assertIsNone(self.controller.challenge_dialog)
        self.assertEqual(self.view.status_label.text(), "Resuming automated scraping...")

    def test_controller_challenge_cancelled(self):
        """User clicking Cancel in ChallengeDialog cleanly resets dialog."""
        mock_orch = MagicMock()
        self.controller.orchestrator = mock_orch

        self.controller.on_challenge_detected("CAPTCHA prompt")
        self.assertIsNotNone(self.controller.challenge_dialog)

        self.controller.on_challenge_cancel_clicked()
        mock_orch.cancel.assert_called_once()
        self.assertIsNone(self.controller.challenge_dialog)


if __name__ == "__main__":
    unittest.main()

