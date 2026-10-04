import os
import sys

# Add project root to sys.path to resolve imports when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.ui.controller import MainWindowController
from src.scraper.playwright_scraper import PlaywrightScraper
from src.enrichment.website_enricher import WebsiteEnricher
from src.exporter.excel_exporter import ExcelExporter

def main():
    """Main application launcher and dependency injection bootstrapper."""
    # Initialize the PySide6 application context
    app = QApplication(sys.argv)
    
    print("GeoScrape UI initialization...")
    
    # Create concrete engine instances (dependencies)
    enricher = WebsiteEnricher()
    scraper = PlaywrightScraper(headless=True, enricher=enricher)
    exporter = ExcelExporter()
    
    # Instantiate the View
    window = MainWindow()
    
    # Instantiate the Controller (wires view events to scraper actions)
    controller = MainWindowController(window, scraper, exporter)
    
    # Display the window (triggers the modern fade-in transition)
    window.show()
    
    # Run the application event execution loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
