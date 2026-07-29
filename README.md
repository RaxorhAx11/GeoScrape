# GeoScrape - RPA Lead Generator

[![Python Version](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![GUI Framework](https://img.shields.io/badge/GUI-PySide6%20(Qt)-green.svg)](https://doc.qt.io/qtforpython/)
[![Automation](https://img.shields.io/badge/Automation-Playwright-orange.svg)](https://playwright.dev/python/)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](LICENSE)

GeoScrape is a clean, modern Robotic Process Automation (RPA) desktop application written in Python. It automates the collection of publicly available business information from Google Maps and exports the structured data directly into styled Excel spreadsheets. 

Manually gathering local leads (e.g., finding all dental clinics or cafes in a specific city) is a time-consuming process involving repetitive copy-pasting of names, addresses, and contact numbers. GeoScrape automates this repetitive chore by programmatically driving a browser instance to search, extract, and clean maps listings—delivering a ready-to-use spreadsheet file within minutes.

Designed with academic presentation in mind, this project adheres strictly to **SOLID design principles**, demonstrates **clean MVC architecture**, and handles multi-threaded background workers safely without freezing the desktop user interface.

---

## 📸 Screenshots

| Dashboard Configuration | Live Log Console |
| :--- | :--- |
| ![Dashboard Setup Placeholder](https://via.placeholder.com/450x300.png?text=GeoScrape+Dashboard+Config+Form) | ![Execution Logs Placeholder](https://via.placeholder.com/450x300.png?text=Live+Execution+Console+Activity) |

---

## 🚀 Features

* **Visual Config Form**: Configure searches using parameters like `Keyword`, `Location`, and `Max Results` limits.
* **Responsive Background Scraper**: Scrapes lead details inside a background `QThread` to ensure the PySide6 user interface stays smooth and completely interactive.
* **Polite Scraping (Rate Limit Safe)**: Implements randomized human-like delays (2 to 5 seconds) between business profile navigations to mimic realistic activity and prevent IP rate-limiting.
* **Resilient DOM Extractor**: Gracefully handles missing properties (e.g. absent phone numbers or website URLs) by reverting to `"N/A"` instead of failing the workflow.
* **Dynamic Results Loader**: Locates results panels and programmatically triggers page scrolling to lazy-load entries up to the requested result count.
* **Early Terminate / Stop Safety**: Halts operations safely mid-run upon cancellation request, ensuring all data collected up to that point is preserved and exported.
* **Real-time UI Logs Redirection**: Features a thread-safe `QtLogHandler` that intercepts system logs and prints progress directly to the in-app scrolling console text panel.
* **Rich Styled Excel Export**: Automatically generates column widths, styles headers, applies borders, and exports to `.xlsx` files with date-injected file names.

---

## 🛠 Technology Stack

* **Programming Language**: [Python](https://www.python.org/) (Compatible with 3.8+)
* **GUI Presentation Layer**: [PySide6](https://pypi.org/project/PySide6/) (Official Qt for Python bindings)
* **Robotic Automation Engine**: [Playwright Python](https://playwright.dev/python/) (Sync API wrapper driving Chromium)
* **Spreadsheet Data Engineer**: [openpyxl](https://openpyxl.readthedocs.io/en/stable/) (Writing structured styled Excel worksheets)

---

## 📐 Architecture Design

GeoScrape is structured around the **Model-View-Controller (MVC)** pattern with complete decoupling via interfaces to align with **SOLID principles**:

* **Domain Models (`src/core/models.py`)**: Defines the immutable `BusinessItem` dataclass representing a business entity.
* **Abstractions (`src/core/interfaces/`)**: Declares `ScraperInterface` and `ExporterInterface` base classes. High-level orchestrators depend only on these contracts, making it easy to swap Playwright scraping with an API backend or Excel output with CSV/JSON.
* **Orchestrator (`src/core/orchestrator.py`)**: Governs background execution flow via a `QThread` class and coordinates communication using Qt Signals (`item_scraped`, `progress_changed`, `scraping_finished`, `failed`).
* **UI Views (`src/ui/`)**: Renders layout, cards, and styling components. Contains the Apple-inspired stylesheets.
* **Controller (`src/ui/controller.py`)**: Intercepts actions from the GUI, triggers file dialogs, validates fields, and manages thread lifecycle and event subscriptions.

For a detailed blueprint including sequence diagrams, consult the [Architecture Design Document](architecture_design.md).

---

## 📦 Installation & Setup

### Prerequisites

* Python 3.8 or higher installed on your computer.

### Step-by-Step Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/GeoScrape.git
   cd GeoScrape
   ```

2. **Establish a Virtual Environment**:
   ```bash
   # Create virtual environment
   python -m venv venv

   # Activate on Windows:
   .\venv\Scripts\activate

   # Activate on macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Core Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Browser Binaries**:
   Playwright requires specific browser binaries to run. Download and configure Chromium by running:
   ```bash
   playwright install chromium
   ```

---

## 💻 Usage Instructions

1. **Launch the Desktop Application**:
   Ensure your virtual environment is active, then run:
   ```bash
   python src/main.py
   ```

2. **Configure Your Query**:
   * **Business Keyword**: Enter what you want to find (e.g. *Dentist*, *Real Estate*, *Cafe*).
   * **Location**: Define the city or area (e.g. *Boston, MA*, *Austin, TX*).
   * **Maximum Results**: Use the spinner to set a result ceiling.
   * **Headed Toggle**: Enable "Show browser window" if you want to visually watch Playwright navigate Google Maps.

3. **Begin Extraction**:
   * Click **Start Scrape**.
   * Pick your export directory and filename in the save dialog.
   * Watch progress update in real-time on the status bar and the Live Execution Log.

4. **Halt Scrape (Optional)**:
   * Press **Stop** to halt scraping mid-run. The app will immediately complete saving all items collected up to the cancellation.

---

## ⚠️ Known Limitations

* **DOM Layout Changes**: Google Maps frequently changes its HTML selectors and class designations. If Google updates its details layouts, DOM queries in `src/scraper/selectors.py` must be updated.
* **No Bypass for CAPTCHAs**: High-frequency, massive scrapes without delays might trigger Google's CAPTCHA security screens. GeoScrape operates sequentially on a single thread to lower rate-limiting risks, but proxy configuration is out-of-scope.
* **Single Thread Sequencing**: To remain polite and prevent rapid IP bans, the application scrapes pages sequentially rather than in parallel, which limits parsing speed to network thresholds and human delay settings.

---

## 🔮 Future Enhancements (Post-Diploma Scope)

* **Places API Integration**: Add a toggle enabling users to input a Google Cloud API Key to pull data via Google Places API for instant and reliable rates.
* **Website Contact Extractor**: Add enrichment steps to navigate to scraped websites and extract contact emails or social handles (LinkedIn, Facebook, Instagram).
* **Proxy and VPN Rotation**: Integrate proxy configuration pools to rotate scraper IPs and allow high-volume extraction.
* **Scheduled Scrapes**: Support cron schedules for recurrent, unattended lead extraction runs.
