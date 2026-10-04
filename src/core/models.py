from dataclasses import dataclass

@dataclass(frozen=True)
class BusinessItem:
    """Domain model representing a business extracted from Google Maps."""
    name: str
    rating: float
    reviews_count: int
    category: str
    address: str
    phone: str
    website: str
    maps_url: str
    email: str = "N/A"
    linkedin: str = "N/A"
    facebook: str = "N/A"
    instagram: str = "N/A"

