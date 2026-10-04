import logging
import re
from typing import Optional, Tuple, Any

logger = logging.getLogger(__name__)


class ChallengeDetector:
    """
    Service for conservatively detecting browser verification challenges,
    CAPTCHA prompts, bot-detection screens, and unusual traffic interstitials.
    
    Adheres strictly to the Human-in-the-Loop workflow pattern:
    Detects challenges to pause automation for human resolution, without attempting
    to bypass, defeat, or solve CAPTCHA mechanisms.
    """

    # Conservative indicators of bot challenge or verification walls
    CHALLENGE_TEXT_PATTERNS = [
        re.compile(r"verify\s+you\s+are\s+human", re.IGNORECASE),
        re.compile(r"unusual\s+traffic", re.IGNORECASE),
        re.compile(r"before\s+you\s+continue", re.IGNORECASE),
        re.compile(r"verification\s+required", re.IGNORECASE),
        re.compile(r"our\s+systems\s+have\s+detected\s+unusual\s+traffic", re.IGNORECASE),
        re.compile(r"enter\s+the\s+characters\s+you\s+see", re.IGNORECASE),
        re.compile(r"type\s+the\s+characters\s+you\s+see", re.IGNORECASE),
        re.compile(r"prove\s+you(?:'|’)?re\s+not\s+a\s+robot", re.IGNORECASE),
        re.compile(r"confirm\s+you(?:'|’)?re\s+not\s+a\s+robot", re.IGNORECASE),
        re.compile(r"security\s+check", re.IGNORECASE),
    ]

    CHALLENGE_SELECTORS = [
        'iframe[src*="recaptcha"]',
        'iframe[src*="challenge"]',
        'iframe[src*="turnstile"]',
        'div.g-recaptcha',
        'form#captcha-form',
        'div#captcha',
        'div[id*="recaptcha"]'
    ]

    def __init__(self, simulate_challenge: bool = False) -> None:
        """
        Initializes ChallengeDetector.
        
        Args:
            simulate_challenge (bool): Development/test-only flag to simulate a challenge
                                      state for reliable faculty demonstration without
                                      depending on unpredictable live CAPTCHAs.
        """
        self.simulate_challenge = simulate_challenge
        self._simulated_triggered = False

    def is_challenge_detected(self, page: Any) -> bool:
        """
        Checks whether a challenge/verification prompt is active on the given page.
        
        Args:
            page: Playwright Page instance or mock page object.
            
        Returns:
            bool: True if challenge is detected, False otherwise.
        """
        detected, _ = self.detect_challenge(page)
        return detected

    def detect_challenge(self, page: Any) -> Tuple[bool, Optional[str]]:
        """
        Inspects the page state conservatively for challenge indicators.
        
        Args:
            page: Playwright Page instance or mock page object.
            
        Returns:
            Tuple[bool, Optional[str]]: (is_detected, reason_message)
        """
        logger.debug("Challenge detection check started.")

        # 1. Development/Testing Mode Trigger
        if self.simulate_challenge and not self._simulated_triggered:
            return True, "[TEST/DEVELOPMENT] Simulated verification challenge required."

        if page is None:
            return False, None

        # Check if page is closed
        try:
            if hasattr(page, "is_closed") and page.is_closed():
                return False, None
        except Exception:
            return False, None

        # 2. Inspect Page URL
        try:
            url = getattr(page, "url", "") or ""
            if "/sorry/index" in url or "google.com/sorry" in url:
                return True, f"Google unusual traffic block URL detected: {url}"
            if "captcha" in url.lower():
                return True, f"Challenge redirect URL detected: {url}"
        except Exception as e:
            logger.debug(f"Error checking page URL: {e}")

        # 3. Inspect known challenge DOM selectors
        for selector in self.CHALLENGE_SELECTORS:
            try:
                locator = page.locator(selector).first
                if locator.is_visible(timeout=200):
                    return True, f"Challenge DOM element visible: {selector}"
            except Exception:
                continue

        # 4. Inspect Page Title
        try:
            title = page.title() or ""
            for pattern in self.CHALLENGE_TEXT_PATTERNS:
                if pattern.search(title):
                    return True, f"Challenge phrase matched in page title: '{title}'"
        except Exception as e:
            logger.debug(f"Error checking page title: {e}")

        # 5. Inspect Visible Body Text
        try:
            body_locator = page.locator("body")
            if hasattr(body_locator, "inner_text"):
                body_text = body_locator.inner_text(timeout=500)
                if body_text:
                    for pattern in self.CHALLENGE_TEXT_PATTERNS:
                        match = pattern.search(body_text)
                        if match:
                            matched_str = match.group(0)
                            return True, f"Verification text detected: '{matched_str}'"
        except Exception as e:
            logger.debug(f"Error checking page body text: {e}")

        return False, None

    def resolve_simulated_challenge(self) -> None:
        """Marks the simulated test challenge as resolved."""
        self._simulated_triggered = True
        self.simulate_challenge = False
        logger.debug("Simulated challenge marked as resolved.")
