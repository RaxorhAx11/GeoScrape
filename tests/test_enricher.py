import unittest
from unittest.mock import MagicMock, patch
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from src.core.models import BusinessItem
from src.enrichment.website_enricher import WebsiteEnricher, EnricherConfig


class TestWebsiteEnricher(unittest.TestCase):
    """Unit tests for WebsiteEnricher and contact/social profile extraction."""

    def setUp(self):
        self.enricher = WebsiteEnricher(EnricherConfig(max_pages_per_website=3, timeout_ms=2000))
        self.sample_item = BusinessItem(
            name="Alpha Dental",
            rating=4.9,
            reviews_count=210,
            category="Dentist",
            address="100 Main St, Austin, TX",
            phone="+1 512-555-0155",
            website="https://alphadental.com",
            maps_url="https://google.com/maps/place/alpha"
        )

    # 1. BusinessItem supports new fields
    def test_business_item_supports_new_fields(self):
        # Default initialization should populate "N/A"
        item_default = BusinessItem(
            name="Beta Clinic",
            rating=4.0,
            reviews_count=10,
            category="Clinic",
            address="200 Broad St",
            phone="555-1234",
            website="https://beta.com",
            maps_url="https://maps.google.com/beta"
        )
        self.assertEqual(item_default.email, "N/A")
        self.assertEqual(item_default.linkedin, "N/A")
        self.assertEqual(item_default.facebook, "N/A")
        self.assertEqual(item_default.instagram, "N/A")

        # Explicit initialization with enriched fields
        item_enriched = BusinessItem(
            name="Beta Clinic",
            rating=4.0,
            reviews_count=10,
            category="Clinic",
            address="200 Broad St",
            phone="555-1234",
            website="https://beta.com",
            maps_url="https://maps.google.com/beta",
            email="contact@beta.com",
            linkedin="https://linkedin.com/company/beta",
            facebook="https://facebook.com/beta",
            instagram="https://instagram.com/beta"
        )
        self.assertEqual(item_enriched.email, "contact@beta.com")
        self.assertEqual(item_enriched.linkedin, "https://linkedin.com/company/beta")
        self.assertEqual(item_enriched.facebook, "https://facebook.com/beta")
        self.assertEqual(item_enriched.instagram, "https://instagram.com/beta")

    # 2. Email extraction
    def test_email_extraction_mailto_preference(self):
        # Prefer mailto over text occurrences
        html = '''
            <div>
                <p>Old email text info@fallback-biz.com</p>
                <a href="mailto:primary@alphadental.com?subject=Appointments">Email Us</a>
            </div>
        '''
        extracted = WebsiteEnricher.extract_email(html, "Old email text info@fallback-biz.com")
        self.assertEqual(extracted, "primary@alphadental.com")

    def test_email_extraction_text_fallback(self):
        # Fallback to plain text when no mailto is present
        html = '<p>Drop us a line at office@alphadental.com anytime.</p>'
        extracted = WebsiteEnricher.extract_email(html, "Drop us a line at office@alphadental.com anytime.")
        self.assertEqual(extracted, "office@alphadental.com")

    def test_email_extraction_filters_false_positives(self):
        # Filter out image filenames and dummy placeholder domains
        html = '''
            <img src="banner@2x.png" alt="logo" />
            <p>Example: user@example.com or test@domain.com</p>
            <p>Real: info@alphadental.com</p>
        '''
        extracted = WebsiteEnricher.extract_email(html, "Example: user@example.com Real: info@alphadental.com")
        self.assertEqual(extracted, "info@alphadental.com")

    # 3. LinkedIn extraction
    def test_linkedin_extraction(self):
        html = '''
            <footer>
                <a href="https://www.linkedin.com/sharing/share-offsite/?url=xyz">Share</a>
                <a href="https://www.linkedin.com/company/alpha-dental-atx/?viewAsMember=true">Follow Us</a>
            </footer>
        '''
        socials = WebsiteEnricher.extract_social_links(html)
        self.assertEqual(socials["linkedin"], "https://www.linkedin.com/company/alpha-dental-atx")

    def test_linkedin_profile_in_extraction(self):
        html = '<a href="https://linkedin.com/in/dr-jane-smith">Dr. Smith</a>'
        socials = WebsiteEnricher.extract_social_links(html)
        self.assertEqual(socials["linkedin"], "https://linkedin.com/in/dr-jane-smith")

    # 4. Facebook extraction
    def test_facebook_extraction(self):
        html = '''
            <div>
                <a href="https://www.facebook.com/sharer/sharer.php?u=xyz">Share to FB</a>
                <a href="https://www.facebook.com/AlphaDentalAustin?ref=bookmarks">Facebook Page</a>
            </div>
        '''
        socials = WebsiteEnricher.extract_social_links(html)
        self.assertEqual(socials["facebook"], "https://www.facebook.com/AlphaDentalAustin")

    # 5. Instagram extraction
    def test_instagram_extraction(self):
        html = '''
            <div>
                <a href="https://www.instagram.com/p/CxY12345/">Recent Post</a>
                <a href="https://instagram.com/alphadentalatx/">Instagram</a>
            </div>
        '''
        socials = WebsiteEnricher.extract_social_links(html)
        self.assertEqual(socials["instagram"], "https://instagram.com/alphadentalatx")

    # 6. Missing website
    def test_missing_or_invalid_website(self):
        # Empty or "N/A" website should return original item without attempting browser work
        item_na = BusinessItem(
            name="No Web",
            rating=3.5,
            reviews_count=5,
            category="Shop",
            address="300 Oak St",
            phone="555-9999",
            website="N/A",
            maps_url="https://maps.google.com/noweb"
        )
        mock_context = MagicMock()
        result = self.enricher.enrich(item_na, context=mock_context)
        self.assertEqual(result.email, "N/A")
        self.assertEqual(result.linkedin, "N/A")
        mock_context.new_page.assert_not_called()

        item_empty = BusinessItem(
            name="Empty Web",
            rating=3.5,
            reviews_count=5,
            category="Shop",
            address="300 Oak St",
            phone="555-9999",
            website="",
            maps_url="https://maps.google.com/emptyweb"
        )
        result_empty = self.enricher.enrich(item_empty, context=mock_context)
        self.assertEqual(result_empty.email, "N/A")
        mock_context.new_page.assert_not_called()

    # 7. Website with no contact information
    def test_website_with_no_contact_information(self):
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        
        # HTML with no email or social links
        mock_page.content.return_value = "<html><body><h1>Welcome to Alpha Dental</h1><p>We care for teeth.</p></body></html>"
        mock_page.locator.return_value.is_visible.return_value = True
        mock_page.inner_text.return_value = "Welcome to Alpha Dental. We care for teeth."

        enriched = self.enricher.enrich(self.sample_item, context=mock_context)
        
        self.assertEqual(enriched.email, "N/A")
        self.assertEqual(enriched.linkedin, "N/A")
        self.assertEqual(enriched.facebook, "N/A")
        self.assertEqual(enriched.instagram, "N/A")
        # Ensure page was cleaned up
        mock_page.close.assert_called_once()

    # 8. Website timeout or error
    def test_website_timeout_handling(self):
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        
        # Simulate Playwright timeout on navigation
        mock_page.goto.side_effect = PlaywrightTimeoutError("Navigation timeout")

        enriched = self.enricher.enrich(self.sample_item, context=mock_context)
        
        # Should not raise exception, original data preserved, fields default to N/A
        self.assertEqual(enriched.name, self.sample_item.name)
        self.assertEqual(enriched.email, "N/A")
        self.assertEqual(enriched.linkedin, "N/A")
        mock_page.close.assert_called_once()

    def test_website_generic_exception_handling(self):
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        
        # Simulate unexpected network/browser error
        mock_page.goto.side_effect = RuntimeError("Connection reset by peer")

        enriched = self.enricher.enrich(self.sample_item, context=mock_context)
        
        self.assertEqual(enriched.name, self.sample_item.name)
        self.assertEqual(enriched.email, "N/A")
        mock_page.close.assert_called_once()

    # Multi-page Candidate Discovery and Early Exit
    def test_internal_candidate_link_discovery(self):
        html = '''
            <nav>
                <a href="/about-us">About Our Team</a>
                <a href="/contact">Get in Touch</a>
                <a href="https://external-news.com/article">External Link</a>
                <a href="mailto:test@alphadental.com">Email</a>
                <a href="#services">Services</a>
            </nav>
        '''
        candidates = WebsiteEnricher.find_internal_candidate_links(
            html=html,
            current_url="https://alphadental.com",
            base_domain="alphadental.com"
        )
        # Should find same-domain /contact and /about-us, with contact prioritized first
        self.assertEqual(candidates, [
            "https://alphadental.com/contact",
            "https://alphadental.com/about-us"
        ])

    def test_early_exit_when_all_fields_found_on_homepage(self):
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_page.content.return_value = '''
            <html>
                <body>
                    <a href="mailto:info@alphadental.com">Contact</a>
                    <a href="https://linkedin.com/company/alphadental">LinkedIn</a>
                    <a href="https://facebook.com/alphadental">Facebook</a>
                    <a href="https://instagram.com/alphadental">Instagram</a>
                    <a href="/contact">Contact Page</a>
                </body>
            </html>
        '''
        mock_page.locator.return_value.is_visible.return_value = True
        mock_page.inner_text.return_value = "Contact info..."

        enriched = self.enricher.enrich(self.sample_item, context=mock_context)

        self.assertEqual(enriched.email, "info@alphadental.com")
        self.assertEqual(enriched.linkedin, "https://linkedin.com/company/alphadental")
        self.assertEqual(enriched.facebook, "https://facebook.com/alphadental")
        self.assertEqual(enriched.instagram, "https://instagram.com/alphadental")

        # Because all 4 fields were discovered on the homepage, goto should only be called once!
        mock_page.goto.assert_called_once()


if __name__ == "__main__":
    unittest.main()
