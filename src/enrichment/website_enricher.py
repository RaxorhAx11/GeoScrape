"""
Website contact and social profile enrichment service.

Visits business websites and extracts publicly visible emails, LinkedIn,
Facebook, and Instagram profiles using polite and safe DOM inspection.
"""

import logging
import re
import urllib.parse
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Set, Tuple
from playwright.sync_api import BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from src.core.models import BusinessItem

logger = logging.getLogger(__name__)

# Regex patterns for email and social links
EMAIL_REGEX = re.compile(
    r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
)

# Common image/static asset extensions that might look like email false positives
INVALID_EMAIL_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot"
}

# Dummy/placeholder domains and usernames to ignore
IGNORE_EMAIL_DOMAINS = {
    "example.com", "example.org", "domain.com", "yourdomain.com",
    "yoursite.com", "email.com", "test.com", "sample.com", "company.com"
}

IGNORE_EMAIL_USERNAMES = {
    "user", "username", "yourname", "name", "someone", "test", "email",
    "placeholder"
}


@dataclass(frozen=True)
class EnricherConfig:
    """Configuration options for website contact and social enrichment."""
    max_pages_per_website: int = 3
    timeout_ms: int = 10000
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    enabled: bool = True


class WebsiteEnricher:
    """
    Dedicated service that enriches a BusinessItem with publicly accessible
    contact information and social profile links from its official website.
    """

    def __init__(self, config: Optional[EnricherConfig] = None) -> None:
        self.config = config if config is not None else EnricherConfig()

    def enrich(
        self,
        item: BusinessItem,
        context: Optional[BrowserContext] = None
    ) -> BusinessItem:
        """
        Visits the business website (if available) and attempts to find:
        - email (mailto: link or page text)
        - linkedin profile
        - facebook page/profile
        - instagram profile

        Args:
            item: The BusinessItem extracted from Google Maps.
            context: An optional existing Playwright BrowserContext to reuse.

        Returns:
            An updated BusinessItem with discovered contact info or 'N/A'.
        """
        if not self.config.enabled:
            return item

        raw_url = item.website.strip() if item.website else ""
        if not raw_url or raw_url.upper() == "N/A" or not self._is_valid_url(raw_url):
            logger.debug(f"Skipping enrichment: No valid website URL for '{item.name}'.")
            return item

        normalized_url = self._normalize_initial_url(raw_url)
        domain = urllib.parse.urlparse(normalized_url).netloc
        logger.info(f"Enriching website: {domain}")

        # If a Playwright context is provided (preferred), use it directly.
        # Otherwise, manage a standalone Playwright browser session.
        if context is not None:
            return self._enrich_with_context(item, normalized_url, context)
        else:
            return self._enrich_standalone(item, normalized_url)

    def _enrich_with_context(
        self,
        item: BusinessItem,
        start_url: str,
        context: BrowserContext
    ) -> BusinessItem:
        """Performs enrichment using an existing Playwright BrowserContext."""
        page: Optional[Page] = None
        try:
            page = context.new_page()
            page.set_default_timeout(self.config.timeout_ms)
            return self._run_enrichment_flow(item, start_url, page)
        except Exception as e:
            logger.warning(f"Website enrichment failed: {e}")
            return item
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass

    def _enrich_standalone(
        self,
        item: BusinessItem,
        start_url: str
    ) -> BusinessItem:
        """Performs enrichment by spinning up a lightweight Playwright session."""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--disable-setuid-sandbox"
                    ]
                )
                try:
                    context = browser.new_context(user_agent=self.config.user_agent)
                    page = context.new_page()
                    page.set_default_timeout(self.config.timeout_ms)
                    return self._run_enrichment_flow(item, start_url, page)
                finally:
                    browser.close()
        except Exception as e:
            logger.warning(f"Website enrichment failed: {e}")
            return item

    def _run_enrichment_flow(
        self,
        item: BusinessItem,
        start_url: str,
        page: Page
    ) -> BusinessItem:
        """
        Visits the homepage and up to (max_pages_per_website - 1) candidate internal pages.
        Extracts contact info and stops when all 4 fields are found or page limit reached.
        """
        discovered: Dict[str, str] = {
            "email": "N/A",
            "linkedin": "N/A",
            "facebook": "N/A",
            "instagram": "N/A",
        }

        pages_visited = 0
        visited_urls: Set[str] = set()
        queue: List[str] = [start_url]
        base_domain = urllib.parse.urlparse(start_url).netloc.lower()

        while queue and pages_visited < self.config.max_pages_per_website:
            current_url = queue.pop(0)
            clean_current = self._strip_fragment(current_url)
            if clean_current in visited_urls:
                continue

            visited_urls.add(clean_current)
            pages_visited += 1

            logger.debug(f"Inspecting page {pages_visited}/{self.config.max_pages_per_website}: {clean_current}")
            try:
                page.goto(clean_current, wait_until="domcontentloaded", timeout=self.config.timeout_ms)
            except PlaywrightTimeoutError:
                logger.warning(f"Website enrichment failed: timeout on {clean_current}")
                # Timeout on homepage means site is unresponsive; don't crawl further
                if pages_visited == 1:
                    break
                continue
            except Exception as e:
                logger.warning(f"Website enrichment failed on {clean_current}: {e}")
                if pages_visited == 1:
                    break
                continue

            # Extract content from current page
            try:
                html_content = page.content()
                page_text = page.inner_text("body") if page.locator("body").is_visible(timeout=1000) else ""
            except Exception as e:
                logger.warning(f"Error reading page content: {e}")
                continue

            # 1. Email extraction (prefer mailto, then text)
            if discovered["email"] == "N/A":
                found_email = self.extract_email(html_content, page_text)
                if found_email:
                    discovered["email"] = found_email
                    logger.info(f"Email found: {found_email}")

            # 2. Social profile links extraction
            socials = self.extract_social_links(html_content)
            for platform in ("linkedin", "facebook", "instagram"):
                if discovered[platform] == "N/A" and socials.get(platform):
                    discovered[platform] = socials[platform]
                    platform_title = "LinkedIn profile" if platform == "linkedin" else f"{platform.capitalize()} profile"
                    logger.info(f"{platform_title} found: {socials[platform]}")

            # Check if all 4 fields are found - early exit if complete
            if all(val != "N/A" for val in discovered.values()):
                logger.debug("All enrichment fields discovered. Concluding website inspection.")
                break

            # If still missing fields and more pages allowed, discover internal candidate pages
            if pages_visited < self.config.max_pages_per_website:
                candidate_links = self.find_internal_candidate_links(html_content, clean_current, base_domain)
                for cand in candidate_links:
                    if cand not in visited_urls and cand not in queue:
                        queue.append(cand)

        return replace(
            item,
            email=discovered["email"],
            linkedin=discovered["linkedin"],
            facebook=discovered["facebook"],
            instagram=discovered["instagram"]
        )

    # -------------------------------------------------------------------------
    # Pure Extraction & Parsing Methods (Unit Testable)
    # -------------------------------------------------------------------------

    @staticmethod
    def extract_email(html: str, text: str = "") -> Optional[str]:
        """
        Extracts a valid business email address from HTML content and plain text.
        Prefers mailto: links over plain text occurrences.
        Filters out false positives and placeholder domains.
        """
        # Step A: Inspect mailto: links in HTML
        mailto_matches = re.findall(r'href=["\']mailto:([^"\'?#]+)', html, re.IGNORECASE)
        for raw_email in mailto_matches:
            email = urllib.parse.unquote(raw_email).strip().lower()
            if WebsiteEnricher._is_valid_email(email):
                return email

        # Step B: Fallback to text matching across text and HTML
        combined_text = f"{text}\n{html}"
        text_matches = EMAIL_REGEX.findall(combined_text)
        for match in text_matches:
            email = match.strip().lower()
            if WebsiteEnricher._is_valid_email(email):
                return email

        return None

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Validates that an email is legitimate and not a placeholder or asset."""
        if not email or "@" not in email:
            return False

        # Check for false-positive file extensions (e.g., logo@2x.png)
        for ext in INVALID_EMAIL_EXTENSIONS:
            if email.endswith(ext):
                return False

        parts = email.split("@")
        if len(parts) != 2:
            return False

        username, domain = parts[0], parts[1]

        # Filter out common placeholders
        if domain in IGNORE_EMAIL_DOMAINS:
            return False
        if username in IGNORE_EMAIL_USERNAMES:
            return False

        # Domain must have at least one dot and a valid TLD
        if "." not in domain:
            return False
        tld = domain.split(".")[-1]
        if len(tld) < 2 or not tld.isalpha():
            return False

        return True

    @staticmethod
    def extract_social_links(html: str) -> Dict[str, Optional[str]]:
        """
        Extracts LinkedIn, Facebook, and Instagram profile URLs from HTML content.
        Filters out sharing widgets, legal pages, and irrelevant endpoints.
        """
        socials: Dict[str, Optional[str]] = {
            "linkedin": None,
            "facebook": None,
            "instagram": None,
        }

        # Find all href attributes
        raw_hrefs = re.findall(r'href=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE)

        for href in raw_hrefs:
            href_clean = href.strip()

            # LinkedIn profile / company / school
            if not socials["linkedin"] and WebsiteEnricher._is_linkedin_profile(href_clean):
                socials["linkedin"] = WebsiteEnricher._normalize_social_url(href_clean)

            # Facebook profile or page
            if not socials["facebook"] and WebsiteEnricher._is_facebook_profile(href_clean):
                socials["facebook"] = WebsiteEnricher._normalize_social_url(href_clean)

            # Instagram profile
            if not socials["instagram"] and WebsiteEnricher._is_instagram_profile(href_clean):
                socials["instagram"] = WebsiteEnricher._normalize_social_url(href_clean)

        return socials

    @staticmethod
    def _is_linkedin_profile(url: str) -> bool:
        """Determines if a URL is an authentic LinkedIn profile/company page."""
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if "linkedin.com" not in netloc:
            return False

        path = parsed.path.lower().rstrip("/")
        # Valid profile indicators
        if any(path.startswith(prefix) for prefix in ("/in/", "/company/", "/school/", "/pub/")):
            slug = path.split("/")[-1]
            return len(slug) > 0 and slug not in ("share", "sharing", "login")
        return False

    @staticmethod
    def _is_facebook_profile(url: str) -> bool:
        """Determines if a URL is an authentic Facebook page/profile."""
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if "facebook.com" not in netloc and "fb.com" not in netloc:
            return False

        path = parsed.path.strip("/")
        if not path:
            return False

        # Exclude non-profile Facebook utility endpoints
        excluded_paths = {
            "sharer", "sharer.php", "share.php", "share", "dialog", "login",
            "policies", "help", "recover", "terms", "tr", "v2.0", "events"
        }
        first_segment = path.split("/")[0].lower()
        if first_segment in excluded_paths:
            return False

        return True

    @staticmethod
    def _is_instagram_profile(url: str) -> bool:
        """Determines if a URL is an authentic Instagram profile."""
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if "instagram.com" not in netloc:
            return False

        path = parsed.path.strip("/")
        if not path:
            return False

        # Exclude post links, reels, explore, and account settings
        excluded_paths = {
            "p", "reel", "reels", "explore", "accounts", "about",
            "legal", "developer", "directory"
        }
        first_segment = path.split("/")[0].lower()
        if first_segment in excluded_paths:
            return False

        return True

    @staticmethod
    def _normalize_social_url(url: str) -> str:
        """Strips tracking parameters and normalizes profile URLs."""
        parsed = urllib.parse.urlparse(url)
        # Rebuild without query or fragment for clean output
        clean_url = urllib.parse.urlunparse((
            parsed.scheme or "https",
            parsed.netloc,
            parsed.path.rstrip("/"),
            "", "", ""
        ))
        return clean_url

    @staticmethod
    def find_internal_candidate_links(
        html: str,
        current_url: str,
        base_domain: str
    ) -> List[str]:
        """
        Finds obvious internal contact/about page URLs on the same domain.
        Inspects links matching patterns such as /contact, /contact-us, /about, /about-us.
        """
        candidate_keywords = ["contact", "contact-us", "contact_us", "about", "about-us", "about_us", "get-in-touch"]
        found_links: List[str] = []
        seen: Set[str] = set()

        raw_hrefs = re.findall(r'href=["\']([^"\'#]+)["\']', html, re.IGNORECASE)

        for href in raw_hrefs:
            href_clean = href.strip()
            if not href_clean or href_clean.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue

            # Resolve relative URLs
            resolved = urllib.parse.urljoin(current_url, href_clean)
            parsed = urllib.parse.urlparse(resolved)

            # Must be same-domain
            if parsed.netloc.lower() != base_domain:
                continue

            path_lower = parsed.path.lower()
            if any(kw in path_lower for kw in candidate_keywords):
                clean_resolved = WebsiteEnricher._strip_fragment(resolved)
                if clean_resolved not in seen and clean_resolved != current_url:
                    seen.add(clean_resolved)
                    found_links.append(clean_resolved)

        # Prioritize contact pages before about pages
        contact_links = [l for l in found_links if "contact" in l.lower()]
        other_links = [l for l in found_links if "contact" not in l.lower()]
        return contact_links + other_links

    # -------------------------------------------------------------------------
    # URL Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Checks if a string is a potentially valid HTTP/HTTPS URL."""
        if not url:
            return False
        parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
        return bool(parsed.netloc and "." in parsed.netloc)

    @staticmethod
    def _normalize_initial_url(url: str) -> str:
        """Ensures URL starts with https:// if no scheme is specified."""
        if not url.startswith(("http://", "https://")):
            return f"https://{url}"
        return url

    @staticmethod
    def _strip_fragment(url: str) -> str:
        """Removes fragment identifier (#...) and trailing slashes."""
        parsed = urllib.parse.urlparse(url)
        return urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            parsed.params,
            parsed.query,
            ""
        ))
