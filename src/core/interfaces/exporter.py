from abc import ABC, abstractmethod
from typing import List
from src.core.models import BusinessItem

class ExporterInterface(ABC):
    """Abstract interface defining the contract for exporting business items."""

    @abstractmethod
    def export(self, items: List[BusinessItem], file_path: str = None) -> str:
        """
        Exports a list of BusinessItems to a specific file format.

        Args:
            items: The list of BusinessItem domain models to export.
            file_path: The local file path where the export should be saved.

        Returns:
            str: The actual file path where the file was saved.
        """
        pass
