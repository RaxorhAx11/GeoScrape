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

## 🤖 Automated RPA Workflows (Faculty Requirements)

GeoScrape demonstrates **5 fully automated RPA workflows**:

1. **Dynamic Google Maps Results Scrolling & Lazy Loading**: Programmatically locates the virtualized feed panel, detects lazy-loaded DOM boundaries, and autoscrolls until reaching the specified lead threshold or exhausting feed results.
2. **Automated Cookie Consent & Dialog Handling**: Intelligently inspects and bypasses regional Google consent modals and cookies dialogues without interrupting headless execution.
3. **Automated Business Data Extraction, Cleaning & Throttling**: Parses multi-line addresses, phone numbers, ratings, review counts, and categories with graceful fallbacks and human-like randomized throttling (2-5s) to prevent rate limiting.
4. **Automated Website Contact & Social Profile Enrichment**: Navigates to discovered business websites, scans footer, header, and contact pages, and extracts direct email addresses and social profiles (LinkedIn, Facebook, Instagram).
5. **Autonomous Multi-Query Batch Queue Processor**: Loads JSON-configured batch search queues, executes queries sequentially without human intervention, automatically saves dedicated Excel spreadsheets with sanitized filenames, handles failures fault-tolerantly, and generates an aggregate summary.

---

## 👤 Human-in-the-Loop (HITL) Workflows

GeoScrape incorporates **5 interactive Human-in-the-Loop decisions**:

1. **Interactive Job Configuration & Destination Selection**: Operator configures keywords, geographic boundary, lead caps, and browser visibility parameters with input validation and custom destination path negotiation.
2. **User-Controlled Cancellation & Partial Recovery**: Operator can halt long-running background scraping mid-cycle; the system traps the interruption signal, prevents thread corruption, and preserves all collected records.
3. **Application Termination Guard**: Prevents accidental exit during background operations by intercepting window close events, presenting confirmation modals, and safely terminating sub-processes.
4. **Interactive Data Review & Lead Approval (Workflow #4)**: Transitions automated scraping into a dedicated review table before Excel generation. Human reviewers inspect scraped/enriched records, correct inaccurate fields, delete unwanted leads, select/deselect entries, and give explicit authorization to export.
5. **Batch Exception Review & Recovery**: Unattended batch execution catches individual task failures gracefully, preserving successful outputs and presenting summary reports for operator audit.

---

## 🚀 Features

* **Dual-Mode Desktop Interface**: Single Scrape mode for quick queries and Batch Queue mode for unattended multi-query processing.
* **Autonomous Batch Processor**: Executes consecutive scraping and enrichment jobs sequentially without user intervention.
* **Responsive Background Threading**: Uses dedicated `QThread` workers (`ScrapeOrchestrator` and `BatchScrapeOrchestrator`) keeping the GUI responsive.
* **Polite Scraping (Rate Limit Safe)**: Implements randomized human-like delays (2 to 5 seconds) between business profile navigations.
* **Automated Website Contact Enrichment**: Scans business sites for contact emails and social media channels.
* **Safe Output Filenames**: Generates collision-proof, sanitized Excel files (`<keyword>_<location>_<timestamp>.xlsx`).
* **Early Terminate / Stop Safety**: Halts operations safely mid-run upon cancellation request while preserving collected data.
* **Real-time UI Logs Redirection**: Thread-safe `QtLogHandler` routes logging records directly to the in-app console.
* **Rich Styled Excel Export**: Automatically generates column widths, styles headers, applies borders, and exports to `.xlsx`.

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

### Single Scrape Mode:
1. **Configure Your Query**:
   * **Business Keyword**: Enter what you want to find (e.g. *Dentist*, *Real Estate*, *Cafe*).
   * **Location**: Define the city or area (e.g. *Boston, MA*, *Austin, TX*).
   * **Maximum Results**: Use the spinner to set a result ceiling.
   * **Headed Toggle**: Enable "Show browser window" if you want to visually watch Playwright navigate Google Maps.
2. **Begin Extraction**:
   * Click **Start Scrape**.
   * Pick your export destination path in the file save dialog.
   * Watch extraction and website enrichment progress update in real-time on the status bar and Live Execution Log.
3. **Interactive Human Review & Lead Approval (HITL Workflow #4)**:
   * When scraping completes, GeoScrape automatically opens the **Data Review** table view.
   * **Select / Deselect**: Toggle individual checkboxes or use **Select All** / **Deselect All** to choose which leads to keep.
   * **Edit Records**: Highlight a record and click **Edit Selected** (or double-click) to correct inaccurate data with field validation.
   * **Delete Unwanted Leads**: Select rows and click **Delete Selected** to remove spam or irrelevant businesses.
   * **Approve & Export**: Click **✓ Approve & Export** to generate the final Excel spreadsheet containing ONLY approved records.
   * **Cancel Review**: Click **Cancel Review** to discard the scraped dataset safely without writing to disk.
4. **Halt Scrape Mid-Run (Optional)**:
   * Press **Stop** to halt scraping mid-run. The app preserves partially collected records and offers them for review.

### Batch Queue Mode (Autonomous Multi-Query RPA Workflow):
1. **Switch to "Batch Queue" Tab** in the left sidebar.
2. **Choose an Input Method**:
   * **Method 1: Simple Input (Fast & Direct)**:
     Type or paste your queries directly into the text box (one per line, format: `Keyword, Location, Limit`):
     ```text
     Dentist, Ahmedabad, 20
     Restaurant, Ahmedabad, 20
     Hotel, Surat, 20
     ```
   * **Method 2: Upload JSON**:
     Switch to the **Upload JSON** sub-tab and click **Load Batch File (.json)** to select a pre-configured JSON file (e.g., `batch_jobs.json`).
3. **Execute Autonomous Batch**:
   * Click **Run Batch**.
   * Select a destination folder where individual Excel files will be placed.
   * The application processes Job 1 → Scrapes Google Maps → Enriches website contacts → Exports Excel → Automatically transitions to Job 2 → Continues until queue completes.
4. **Cancel Batch**: Click **Cancel Batch** at any time to gracefully halt processing subsequent queries while preserving completed spreadsheets.

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
