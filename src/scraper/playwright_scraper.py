import logging
import re
import random
from dataclasses import dataclass, field
from typing import List, Callable, Dict, Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError

from src.core.models import BusinessItem
from src.core.interfaces.scraper import ScraperInterface
from src.scraper.exceptions import (
    BrowserLaunchError,
    NavigationError,
    SearchError
)
import src.scraper.selectors as selectors

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class ScraperConfig:
    """Configuration options for the Playwright scraper service."""
    headless: bool = True
    timeout_ms: int = 30000
    scroll_delay_ms: int = 1500
    max_scrolls: int = 40
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    viewport: Dict[str, int] = field(default_factory=lambda: {"width": 1280, "height": 800})


class BrowserSession:
    """
    Context manager that encapsulates Playwright engine lifecycle,
    browser launching, context settings, and tab creation.
    
    Ensures safe, leak-free browser teardown on exit or exceptions.
    """
    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self._playwright_mgr = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def __enter__(self) -> Page:
        logger.debug("Entering BrowserSession, initializing Playwright...")
        try:
            self._playwright_mgr = sync_playwright()
            p = self._playwright_mgr.__enter__()
        except Exception as e:
            logger.error(f"Playwright sync framework failed to start: {e}")
            raise BrowserLaunchError(f"Could not start Playwright engine: {e}") from e

        logger.info(f"Launching Chromium (headless={self.config.headless})...")
        try:
            self._browser = p.chromium.launch(
                headless=self.config.headless,
                args=[
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            )
        except Exception as e:
            self.__exit__(None, None, None)
            logger.error(f"Failed to launch Chromium browser process: {e}")
            raise BrowserLaunchError(f"Failed to launch browser: {e}") from e

        logger.debug("Creating new browser context and page tab...")
        try:
            self._context = self._browser.new_context(
                viewport=self.config.viewport,
                user_agent=self.config.user_agent
            )
            self._page = self._context.new_page()
            self._page.set_default_timeout(self.config.timeout_ms)
            return self._page
        except Exception as e:
            self.__exit__(None, None, None)
            logger.error(f"Failed to initialize context or open page tab: {e}")
            raise BrowserLaunchError(f"Failed to setup browser context: {e}") from e

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        logger.debug("Exiting BrowserSession, performing browser cleanup...")
        if self._browser:
            try:
                self._browser.close()
            except Exception as e:
                logger.warning(f"Error while closing browser: {e}")
        if self._playwright_mgr:
            try:
                self._playwright_mgr.__exit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error exiting Playwright: {e}")


class MapsParser:
    """
    Parser service that extracts business details from the active Google Maps page.
    Translates DOM query selections into clean domain models (BusinessItem).
    """
    @staticmethod
    def extract_details(page: Page, maps_url: str) -> Optional[BusinessItem]:
        """
        Parses details from the open business panel of the page.
        Returns a BusinessItem if parsing succeeds, or None if extraction is critically broken.
        """
        try:
            # 1. Name (Critical field)
            name = "N/A"
            name_el = page.locator(selectors.BUSINESS_NAME).first
            if name_el.is_visible(timeout=2000):
                name = name_el.inner_text().strip()
            
            if name == "N/A":
                logger.warning(f"Failed to find business name on details page: {maps_url}")

            # 2. Rating & Reviews
            rating = 0.0
            reviews_count = 0
            rating_container = page.locator(selectors.BUSINESS_RATING_CONTAINER).first
            if rating_container.is_visible(timeout=1000):
                spans = rating_container.locator("span").all()
                if len(spans) >= 1:
                    try:
                        rating = float(spans[0].inner_text().replace(",", ".").strip())
                    except ValueError:
                        pass
                if len(spans) >= 2:
                    try:
                        reviews_text = spans[1].inner_text().strip()
                        match = re.search(r'\d[\d,]*', reviews_text)
                        if match:
                            reviews_count = int(match.group().replace(",", ""))
                    except Exception:
                        pass
            else:
                rating_el = page.locator(selectors.BUSINESS_RATING).first
                if rating_el.is_visible(timeout=500):
                    try:
                        rating = float(rating_el.inner_text().replace(",", ".").strip())
                    except ValueError:
                        pass

            # 3. Category
            category = "N/A"
            category_el = page.locator(selectors.BUSINESS_CATEGORY).first
            if category_el.is_visible(timeout=500):
                category = category_el.inner_text().strip()

            # 4. Address
            address = "N/A"
            address_el = page.locator(selectors.BUSINESS_ADDRESS).first
            if address_el.is_visible(timeout=500):
                raw_address = address_el.inner_text().strip()
                address = MapsParser._clean_element_text(raw_address, join_delimiter=", ")

            # 5. Phone
            phone = "N/A"
            phone_el = page.locator(selectors.BUSINESS_PHONE).first
            if phone_el.is_visible(timeout=500):
                raw_phone = phone_el.inner_text().strip()
                phone = MapsParser._clean_element_text(raw_phone, join_delimiter=" ")

            # 6. Website
            website = "N/A"
            website_el = page.locator(selectors.BUSINESS_WEBSITE).first
            if website_el.is_visible(timeout=500):
                href_attr = website_el.get_attribute("href")
                if href_attr:
                    website = href_attr.strip()
                else:
                    a_el = website_el.locator("a").first
                    if a_el.is_visible(timeout=500):
                        href_attr = a_el.get_attribute("href")
                        if href_attr:
                            website = href_attr.strip()

            # 7. Maps URL
            current_url = page.url if page.url else maps_url

            return BusinessItem(
                name=name,
                rating=rating,
                reviews_count=reviews_count,
                category=category,
                address=address,
                phone=phone,
                website=website,
                maps_url=current_url
            )
        except Exception as e:
            logger.error(f"Unexpected parser failure on details card: {e}")
            return None

    @staticmethod
    def _clean_element_text(raw_text: str, join_delimiter: str = ", ") -> str:
        """Helper to clean leading icon tags and empty lines from element labels."""
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
        if lines:
            # If the first line is a single icon character, remove it
            if len(lines[0]) <= 2 and not lines[0].isalnum():
                lines = lines[1:]
            return join_delimiter.join(lines)
        return "N/A"


class PlaywrightScraper(ScraperInterface):
    """
    Refactored Google Maps scraper implementing ScraperInterface.
    Delegates browser lifecycle to BrowserSession and parses content via MapsParser.
    """
    def __init__(self, headless: bool = True, config: Optional[ScraperConfig] = None) -> None:
        self.headless = headless
        self.config = config if config is not None else ScraperConfig(headless=headless)

    def scrape(
        self,
        query: str,
        location: str,
        limit: int,
        progress_callback: Callable[[BusinessItem], None]
    ) -> List[BusinessItem]:
        """
        Executes Google Maps automation to search and scrape business details.
        """
        logger.info(f"Starting scraping service (Limit={limit})...")
        
        with BrowserSession(self.config) as page:
            # Step 1: Navigate to Maps & Accept consent
            self._navigate_to_maps(page)
            
            # Step 2: Fill and Submit Search Form
            self._search_for_query(page, query, location)
            
            # Step 3: Wait for Results Feed OR Single Place View
            is_single_place = self._wait_for_results(page)
            
            if is_single_place:
                logger.info("Search query matched single location directly.")
                item = MapsParser.extract_details(page, page.url)
                if item:
                    progress_callback(item)
                    return [item]
                return []
            
            # Step 4: Scroll results sidebar container to lazy-load more entries
            self._scroll_results_feed(page, limit)
            
            # Step 5: Gather and process each card
            business_links = self._collect_business_links(page)
            logger.info(f"Gathered {len(business_links)} business listings. Beginning details extraction...")
            
            return self._extract_listings(page, business_links, limit, progress_callback)

    def _navigate_to_maps(self, page: Page) -> None:
        """Navigates to the Google Maps homepage and handles cookies consent."""
        logger.info("Navigating to https://www.google.com/maps...")
        try:
            page.goto("https://www.google.com/maps", wait_until="domcontentloaded")
        except PlaywrightTimeoutError as e:
            raise NavigationError("Navigation to Google Maps timed out.") from e
        except Exception as e:
            raise NavigationError(f"Google Maps loading failed: {e}") from e

        self._handle_cookie_consent(page)

    def _handle_cookie_consent(self, page: Page) -> None:
        """Checks and accepts cookie screens if blocking the browser."""
        consent_buttons = [
            'button[aria-label="Accept all"]',
            'button[aria-label="Accept all cookies"]',
            'button:has-text("Accept all")',
            'button:has-text("Accept")',
            'button:has-text("I agree")',
            'button:has-text("Agree")'
        ]
        for selector in consent_buttons:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=1500):
                    logger.info("Dismissing Google consent modal page...")
                    btn.click(timeout=2000)
                    page.wait_for_load_state("domcontentloaded")
                    return
            except Exception:
                continue

    def _search_for_query(self, page: Page, query: str, location: str) -> None:
        """Fills the search textbox with f'{query} {location}' and triggers submit."""
        search_query = f"{query} {location}"
        logger.info(f"Submitting query: '{search_query}'")
        
        try:
            page.wait_for_selector(selectors.SEARCH_INPUT, state="visible", timeout=10000)
            page.locator(selectors.SEARCH_INPUT).fill(search_query)
            page.keyboard.press("Enter")
        except PlaywrightTimeoutError as e:
            raise SearchError("Maps search textbox was not loaded or visible.") from e
        except Exception as e:
            raise SearchError(f"Failed to enter search values: {e}") from e

    def _wait_for_results(self, page: Page) -> bool:
        """
        Waits for results list to populate OR direct details panel redirect.
        Returns True if redirected directly to a single business, False for list feed.
        """
        combined_selector = (
            f"{selectors.RESULTS_LIST_PANEL}, {selectors.BUSINESS_NAME}, {selectors.BUSINESS_ADDRESS}, "
            ":text(\"Google Maps can't find\"), :text(\"No results found\")"
        )
        try:
            page.wait_for_selector(combined_selector, state="visible", timeout=20000)
        except PlaywrightTimeoutError as e:
            if page.locator("text=Google Maps can't find").is_visible() or page.locator("text=No results found").is_visible():
                logger.warning("Google Maps search returned zero results.")
                return False
            raise SearchError("No search results were loaded in time.") from e

        # Check if Google Maps returned zero results
        if page.locator("text=Google Maps can't find").is_visible() or page.locator("text=No results found").is_visible():
            logger.warning("Google Maps search returned zero results.")
            return False

        # If details name is immediately visible, it is a single place page redirect
        if page.locator(selectors.BUSINESS_NAME).is_visible():
            return True
        return False

    def _scroll_results_feed(self, page: Page, limit: int) -> None:
        """Scrolls the left-hand search results panel to load enough elements."""
        feed = page.locator(selectors.RESULTS_LIST_PANEL).first
        if not feed.is_visible(timeout=2000):
            logger.debug("No scrollable feed container found.")
            return

        logger.info("Scrolling side panel for lazy loading...")
        prev_count = 0
        no_change = 0
        
        for attempt in range(self.config.max_scrolls):
            # Check for active cancellation request
            if getattr(self, "is_cancelled", lambda: False)():
                raise InterruptedError("Scraping halted by user.")
                
            # Collect unique business links dynamically to check against configurable limit
            unique_links = self._collect_business_links(page)
            count = len(unique_links)
            logger.debug(f"Scroll step {attempt + 1}: Found {count} unique items.")
            
            if count >= limit:
                logger.info(f"Reached configurable results limit of {limit} items.")
                break
            
            # Detect if we have reached the end of the results feed
            end_of_list_selectors = [
                "text=\"You've reached the end of the list.\"",
                "text=\"No more results\"",
                "text=\"End of list\""
            ]
            reached_end = False
            for sel in end_of_list_selectors:
                try:
                    if page.locator(sel).first.is_visible(timeout=100):
                        logger.info("Reached end of list via Google Maps footer message.")
                        reached_end = True
                        break
                except Exception:
                    pass
            if reached_end:
                break
                
            try:
                page.evaluate(
                    "([selector]) => {const el = document.querySelector(selector); if (el) { el.scrollTop = el.scrollHeight; }}",
                    [selectors.RESULTS_LIST_PANEL]
                )
            except Exception as e:
                logger.warning(f"Scrolling evaluation script failed: {e}")
                break

            page.wait_for_timeout(self.config.scroll_delay_ms)
            
            if count == prev_count:
                no_change += 1
                if no_change >= 5:
                    logger.debug("Scrolling reached bottom: no new card items detected.")
                    break
            else:
                no_change = 0
            prev_count = count

    def _normalize_maps_url(self, url: str) -> str:
        """Helper to extract the unique path/place identifier from Google Maps URL."""
        try:
            # Remove coordinate segment like @30.274722,-97.740556,17z/ or @30.274722,-97.740556,17z
            normalized = re.sub(r'@[^/]+(?:/|$)', '', url)
            return normalized.strip().rstrip('/')
        except Exception:
            return url

    def _collect_business_links(self, page: Page) -> List[str]:
        """Gathers unique place URLs from the result feed list."""
        links = page.locator(selectors.BUSINESS_CARD_LINK).all()
        seen = set()
        unique_urls = []
        for loc in links:
            try:
                href = loc.get_attribute("href")
                if href:
                    normalized = self._normalize_maps_url(href)
                    if normalized and normalized not in seen:
                        seen.add(normalized)
                        unique_urls.append(href)  # Store original href for navigation
            except Exception:
                continue
        return unique_urls

    def _extract_listings(
        self,
        page: Page,
        links: List[str],
        limit: int,
        progress_callback: Callable[[BusinessItem], None]
    ) -> List[BusinessItem]:
        """Iterates over card links, loading and parsing each item's details."""
        results = []
        seen_business_urls = set()
        target_count = min(len(links), limit)
        
        for idx, href in enumerate(links[:limit]):
            # Check for active cancellation request
            if getattr(self, "is_cancelled", lambda: False)():
                raise InterruptedError("Scraping halted by user.")
                
            # Polite Scraping: Add a random delay between details navigations (NFR-5.2)
            # Avoid delaying the very first listing navigation to keep startup snappy
            if idx > 0:
                polite_delay = random.uniform(2.0, 5.0)
                logger.debug(f"Applying polite delay of {polite_delay:.2f} seconds...")
                page.wait_for_timeout(int(polite_delay * 1000))
                
            logger.info(f"Processing listing {idx + 1}/{target_count}...")
            
            try:
                card_locator = page.locator(f'a[href="{href}"]').first
                card_locator.scroll_into_view_if_needed(timeout=3000)
                card_locator.click(timeout=3000)
                
                page.wait_for_selector(selectors.BUSINESS_NAME, state="visible", timeout=5000)
                page.wait_for_timeout(500)
                
                item = MapsParser.extract_details(page, href)
                if item:
                    normalized_url = self._normalize_maps_url(item.maps_url)
                    if normalized_url in seen_business_urls:
                        logger.info(f"Skipping duplicate business listing: {item.name} ({normalized_url})")
                        continue
                    seen_business_urls.add(normalized_url)
                    progress_callback(item)
                    results.append(item)
                    
            except PlaywrightTimeoutError:
                logger.warning(f"Timeout waiting for details of listing {idx + 1}. Skipping.")
                continue
            except InterruptedError:
                logger.warning("Scraping execution halted by user request.")
                raise
            except Exception as e:
                logger.error(f"Error scraping details of listing {idx + 1}: {e}")
                continue
                
        return results
