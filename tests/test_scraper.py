import unittest
from unittest.mock import MagicMock, patch
from src.scraper.playwright_scraper import PlaywrightScraper, ScraperConfig, BrowserSession, MapsParser
from src.scraper.exceptions import BrowserLaunchError
from src.core.models import BusinessItem

class TestPlaywrightScraper(unittest.TestCase):
    """Unit tests for the refactored PlaywrightScraper and its sub-components."""

    def test_scraper_config_default_values(self):
        config = ScraperConfig()
        self.assertTrue(config.headless)
        self.assertEqual(config.timeout_ms, 30000)
        self.assertEqual(config.scroll_delay_ms, 1500)
        self.assertEqual(config.max_scrolls, 40)
        self.assertEqual(config.viewport["width"], 1280)
        self.assertEqual(config.viewport["height"], 800)

    def test_scraper_config_custom_values(self):
        config = ScraperConfig(headless=False, timeout_ms=5000, scroll_delay_ms=500, max_scrolls=10)
        self.assertFalse(config.headless)
        self.assertEqual(config.timeout_ms, 5000)
        self.assertEqual(config.scroll_delay_ms, 500)
        self.assertEqual(config.max_scrolls, 10)

    def test_maps_parser_clean_element_text(self):
        # Empty string should yield default "N/A"
        self.assertEqual(MapsParser._clean_element_text(""), "N/A")
        self.assertEqual(MapsParser._clean_element_text("   \n  "), "N/A")
        
        # Leading icon stripping
        self.assertEqual(MapsParser._clean_element_text("\n123 Main St\nAustin, TX"), "123 Main St, Austin, TX")
        self.assertEqual(MapsParser._clean_element_text("\n+1 512-555-0100"), "+1 512-555-0100")
        
        # Multi line addresses with icon
        self.assertEqual(
            MapsParser._clean_element_text("\nBuilding 4\n8745 N Lamar Blvd\nAustin, TX"),
            "Building 4, 8745 N Lamar Blvd, Austin, TX"
        )

    @patch("src.scraper.playwright_scraper.sync_playwright")
    def test_browser_session_launch_failure(self, mock_sync_playwright):
        mock_sync_playwright.side_effect = Exception("Fatal launch")
        session = BrowserSession(ScraperConfig())
        with self.assertRaises(BrowserLaunchError):
            with session:
                pass

    @patch("src.scraper.playwright_scraper.sync_playwright")
    def test_browser_session_cleanup_on_exit(self, mock_sync_playwright):
        mock_playwright = MagicMock()
        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
        mock_browser = MagicMock()
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page

        session = BrowserSession(ScraperConfig())
        with session as page:
            self.assertEqual(page, mock_page)
        
        # Verify browser close was triggered on exit
        mock_browser.close.assert_called_once()
        mock_sync_playwright.return_value.__exit__.assert_called_once()

    def test_maps_parser_extract_details_success(self):
        mock_page = MagicMock()
        
        # Set up mock locators for elements
        mock_name_locator = MagicMock()
        mock_name_locator.first = mock_name_locator
        mock_name_locator.is_visible.return_value = True
        mock_name_locator.inner_text.return_value = "Test Dental"
        mock_page.locator.return_value = mock_name_locator
        
        # Mock rating container
        mock_rating_container = MagicMock()
        mock_rating_container.first = mock_rating_container
        mock_rating_container.is_visible.return_value = True
        
        mock_span_1 = MagicMock()
        mock_span_1.inner_text.return_value = "4.7"
        mock_span_2 = MagicMock()
        mock_span_2.inner_text.return_value = "(45)"
        mock_rating_container.locator.return_value.all.return_value = [mock_span_1, mock_span_2]
        
        # Mock locator returns based on selector matching
        def locator_side_effect(selector):
            loc = MagicMock()
            loc.first = loc
            if "DUwDvf" in selector: # Business name
                loc.is_visible.return_value = True
                loc.inner_text.return_value = "Test Dental"
            elif "F7nice" in selector: # Rating container
                return mock_rating_container
            elif "category" in selector:
                loc.is_visible.return_value = True
                loc.inner_text.return_value = "Dentist"
            elif "address" in selector:
                loc.is_visible.return_value = True
                loc.inner_text.return_value = "\n123 Main St"
            elif "phone" in selector:
                loc.is_visible.return_value = True
                loc.inner_text.return_value = "\n+1 512-555-1234"
            elif "authority" in selector:
                loc.is_visible.return_value = True
                loc.get_attribute.return_value = "https://testdental.com"
            else:
                loc.is_visible.return_value = False
            return loc
            
        mock_page.locator.side_effect = locator_side_effect
        mock_page.url = "https://google.com/maps/place/test"
        
        item = MapsParser.extract_details(mock_page, "https://google.com/maps/place/test")
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Test Dental")
        self.assertEqual(item.rating, 4.7)
        self.assertEqual(item.reviews_count, 45)
        self.assertEqual(item.category, "Dentist")
        self.assertEqual(item.address, "123 Main St")
        self.assertEqual(item.phone, "+1 512-555-1234")
        self.assertEqual(item.website, "https://testdental.com")
        self.assertEqual(item.maps_url, "https://google.com/maps/place/test")

    def test_normalize_maps_url(self):
        scraper = PlaywrightScraper()
        
        # URL with coordinates
        url_with_coords = "https://www.google.com/maps/place/Austin+Dental/@30.274722,-97.740556,17z/data=!3m1!4b1!"
        normalized = scraper._normalize_maps_url(url_with_coords)
        self.assertEqual(normalized, "https://www.google.com/maps/place/Austin+Dental/data=!3m1!4b1!")
        
        # URL with coordinates at the end of string
        url_coords_end = "https://www.google.com/maps/place/Austin+Dental/@30.274722,-97.740556,17z"
        normalized_end = scraper._normalize_maps_url(url_coords_end)
        self.assertEqual(normalized_end, "https://www.google.com/maps/place/Austin+Dental")
        
        # Already normalized URL
        url_clean = "https://www.google.com/maps/place/Austin+Dental/data=!3m1!4b1!"
        self.assertEqual(scraper._normalize_maps_url(url_clean), url_clean)

    def test_collect_business_links_deduplication(self):
        scraper = PlaywrightScraper()
        mock_page = MagicMock()
        
        # Create mock elements returned by locator.all()
        mock_loc1 = MagicMock()
        mock_loc1.get_attribute.return_value = "https://www.google.com/maps/place/Dentist1/@12.3,45.6,15z/data=1"
        
        # A duplicate listing (same place, slightly different coordinates/url formatting)
        mock_loc2 = MagicMock()
        mock_loc2.get_attribute.return_value = "https://www.google.com/maps/place/Dentist1/@12.4,45.7,15z/data=1"
        
        mock_loc3 = MagicMock()
        mock_loc3.get_attribute.return_value = "https://www.google.com/maps/place/Dentist2/@12.3,45.6,15z/data=2"
        
        mock_locator = MagicMock()
        mock_locator.all.return_value = [mock_loc1, mock_loc2, mock_loc3]
        mock_page.locator.return_value = mock_locator
        
        unique_links = scraper._collect_business_links(mock_page)
        # Should filter out the duplicate mock_loc2 since it normalizes to the same base URL as mock_loc1
        self.assertEqual(len(unique_links), 2)
        self.assertEqual(unique_links[0], "https://www.google.com/maps/place/Dentist1/@12.3,45.6,15z/data=1")
        self.assertEqual(unique_links[1], "https://www.google.com/maps/place/Dentist2/@12.3,45.6,15z/data=2")

