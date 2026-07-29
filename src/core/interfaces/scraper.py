from abc import ABC, abstractmethod
from typing import List, Callable
from src.core.models import BusinessItem

class ScraperInterface(ABC):
    """Abstract interface defining the contract for web scraping engines."""

    @abstractmethod
    def scrape(
        self,
        query: str,
        location: str,
        limit: int,
        progress_callback: Callable[[BusinessItem], None]
    ) -> List[BusinessItem]:
        """
        Executes a search on Google Maps and extracts business details.

        Args:
            query: The business type or keyword (e.g., "Dentist").
            location: The geographic location (e.g., "Boston, MA").
            limit: The maximum number of results to extract.
            progress_callback: A function invoked when a new business item is scraped.

        Returns:
            A list of scraped BusinessItem objects.
        """
        pass
