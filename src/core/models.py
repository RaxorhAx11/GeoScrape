from dataclasses import dataclass
from typing import Optional

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


@dataclass(frozen=True)
class BatchJob:
    """Domain model representing a single task in a multi-query batch queue."""
    keyword: str
    location: str
    max_results: int

    def __post_init__(self) -> None:
        if not isinstance(self.keyword, str) or not self.keyword.strip():
            raise ValueError("BatchJob keyword must be a non-empty string.")
        if not isinstance(self.location, str) or not self.location.strip():
            raise ValueError("BatchJob location must be a non-empty string.")
        if not isinstance(self.max_results, int) or isinstance(self.max_results, bool) or self.max_results <= 0:
            raise ValueError("BatchJob max_results must be a positive integer greater than 0.")


@dataclass
class BatchJobResult:
    """Data transfer object containing execution outcome metrics for a batch job."""
    job: BatchJob
    success: bool
    count: int = 0
    export_path: Optional[str] = None
    error_message: Optional[str] = None

