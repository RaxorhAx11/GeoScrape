class ScraperError(Exception):
    """Base exception for all scraper-related errors."""
    pass

class BrowserLaunchError(ScraperError):
    """Raised when Playwright fails to launch the browser or create a context."""
    pass

class NavigationError(ScraperError):
    """Raised when navigation to Google Maps fails or times out."""
    pass

class SearchError(ScraperError):
    """Raised when entering search query or waiting for results fails."""
    pass

class ExtractionError(ScraperError):
    """Raised when extraction of business details fails."""
    pass
