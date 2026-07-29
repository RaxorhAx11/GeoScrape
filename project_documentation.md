# GeoScrape: RPA Lead Generator & Google Maps Scraper
### Academic Project Documentation & Technical Report

---

## 1. Introduction

### 1.1 Project Overview
In modern marketing, sales, and lead generation, local businesses frequently require regional lead databases to execute campaigns. For instance, a dental supplier might seek contact details for all dental clinics in a metropolitan area, or a restaurant equipment wholesaler might require a list of cafes and bistros. 

Manually compiling these directories from public sources such as Google Maps is a highly repetitive, low-cognitive task ("robotic work"). It consists of typing a query, clicking on individual cards, selecting text, copy-pasting addresses, websites, and phone numbers, and formatting them in a spreadsheet. 

**GeoScrape** is a Robotic Process Automation (RPA) desktop application written in Python. It automates this exact pipeline. By driving a browser programmatically, GeoScrape navigates Google Maps, executes search queries, scrolls results sidebar panels to trigger lazy loading, inspects individual listings, extracts data points, cleans them, and exports them directly into a styled, auto-fitted Excel spreadsheet.

### 1.2 Target Audience & Academic Scope
This application is designed specifically as a small-to-mid-tier software project suitable for an **IT Diploma or Undergraduate Computer Science/Software Engineering degree**. It serves as a practical, real-world case study for:
* **Object-Oriented Design**: Aligning software components with SOLID design principles.
* **Graphical User Interface (GUI) Design**: Implementing responsive desktop interfaces with PySide6 (Qt for Python).
* **Asynchronous Execution Patterns**: Preventing user interface blocking or freezing using background thread orchestration.
* **Data Engineering & Automation**: Interacting with dynamic browser environments (Playwright) and writing structured spreadsheet output (openpyxl).

---

## 2. Objectives

### 2.1 Product Objectives
* **Eliminate Manual Data Entry**: Automate the lead compilation process, reducing hours of robotic copy-pasting to a few seconds or minutes of hands-free execution.
* **Graceful Data Parsing**: Format messy and incomplete web data structure into structured fields, defaulting to standard placeholder values (`"N/A"`) instead of interrupting runtime.
* **Polite Scraping Behavior**: Maintain respectful scraping frequencies using random delay intervals to avoid server overload and prevent rapid IP blocks.
* **Zero-Configuration Operation**: Package dependencies and runtimes so that non-technical business users can operate the tool on common operating systems (Windows, macOS).

### 2.2 Academic & Learning Objectives
* **Adherence to SOLID Principles**:
  * *Single Responsibility Principle (SRP)*: Structuring separate, distinct modules for GUI presentation, browser automation, and Excel generation.
  * *Open/Closed Principle (OCP) / Liskov Substitution Principle (LSP)*: Defining abstract base interfaces (`ScraperInterface` and `ExporterInterface`) so that scraper or exporter implementations can be extended or replaced without modifying core orchestrator systems.
  * *Dependency Inversion Principle (DIP)*: Ensuring the core logic depends on abstract base classes instead of concrete low-level implementations.
* **Multi-Threaded UI Design**: Applying Qt's event loop and `QThread` components to safely separate background network processing from main thread user interaction.
* **Real-time Event Logging**: Implementing thread-safe logging pipelines (`QtLogHandler`) to funnel background activity directly to graphical console widgets.

---

## 3. Methodology

The development methodology follows a modular software lifecycle process structured around the Model-View-Controller (MVC) architectural pattern.

```mermaid
graph TD
    subgraph UI Layer (View)
        MainWindow[MainWindow]
        ConfigForm[ConfigForm]
        LogConsole[LogConsole]
    end

    subgraph Control Layer (Controller)
        MainWindowController[MainWindowController]
        QtLogHandler[QtLogHandler]
    end

    subgraph Core Layer (Model & Orchestration)
        ScrapeOrchestrator[ScrapeOrchestrator QThread]
        BusinessItem[BusinessItem Model]
    end

    subgraph Low-Level Engines (Services)
        PlaywrightScraper[PlaywrightScraper]
        ExcelExporter[ExcelExporter]
    end

    MainWindowController --> MainWindow
    MainWindowController --> ScrapeOrchestrator
    ScrapeOrchestrator --> PlaywrightScraper
    ScrapeOrchestrator --> ExcelExporter
    PlaywrightScraper -.->|Yields| BusinessItem
    QtLogHandler --> LogConsole
```

### 3.1 Architecture Overview
1. **The View (UI Layer)**: Built with `PySide6`. Composes widgets (`ConfigForm`, `ControlPanel`, `LogConsole`) into a unified dashboard styling layout inspired by Apple design cues. It is responsible strictly for inputs gathering, status representation, and user action hooks.
2. **The Controller (Coordination Layer)**: The mediator `MainWindowController` binds user actions to logic systems. It validates inputs, instantiates background threads, handles saving file paths, and coordinates clean application exit events.
3. **The Worker (Orchestration Layer)**: The background worker `ScrapeOrchestrator` inherits from `QThread`. It boots and runs the low-level scrapers and exporters in the background. It utilizes Qt Signals to send progress metrics safely back to the View.
4. **The Services (Engine Layer)**: Concrete classes implementing base contracts:
   * `PlaywrightScraper` (implements `ScraperInterface`): Automates Chromium, accepts cookies, inputs queries, scrolls results, and parses cards.
   * `ExcelExporter` (implements `ExporterInterface`): Receives domain items and exports styled spreadsheets using `openpyxl`.

---

## 4. Modules

### 4.1 Entry Point (`src/main.py`)
Responsible for bootstrapping the application. It instantiates the `QApplication` context, injects concrete engines (`PlaywrightScraper`, `ExcelExporter`) into the `MainWindowController`, loads the graphical `MainWindow`, and starts the main application event loop.

### 4.2 Core Domain Modules (`src/core/`)
* **`models.py`**: Holds the `BusinessItem` dataclass representing a business record:
  ```python
  @dataclass(frozen=True)
  class BusinessItem:
      name: str
      rating: float
      reviews_count: int
      category: str
      address: str
      phone: str
      website: str
      maps_url: str
  ```
* **`interfaces/`**: Houses abstract class contracts:
  * `scraper.py`: `ScraperInterface` defines the `scrape()` contract.
  * `exporter.py`: `ExporterInterface` defines the `export()` contract.
* **`orchestrator.py`**: Declares `ScrapeOrchestrator(QThread)`. Manages the background task lifecycle. It executes the scraper, collects results, triggers the exporter, handles user interruptions (`InterruptedError`), and communicates via Qt Signals (`item_scraped`, `progress_changed`, `scraping_finished`, `failed`).

### 4.3 Scraping Engine Module (`src/scraper/`)
* **`playwright_scraper.py`**: Houses the automation core:
  * `BrowserSession`: A custom context manager utilizing `sync_playwright()` to cleanly manage the lifecycle of browser launching, new context generation, and context destruction.
  * `MapsParser`: A utility class containing static methods to extract fields (name, ratings, reviews, category, address, phone, website) from a loaded detail panel locator.
  * `PlaywrightScraper`: Orchestrates browser navigation, executes queries, manages dynamic page scrolling, extracts listings, and runs polite delay delays.
* **`selectors.py`**: Central repository for CSS & XPath string patterns (e.g. `BUSINESS_NAME = "h1.DUwDvf"`). By isolating selectors, layout adjustments by Google Maps can be fixed without changing business logic code.
* **`exceptions.py`**: Defines custom exception classes like `BrowserLaunchError`, `NavigationError`, and `SearchError`.

### 4.4 Exporter Module (`src/exporter/`)
* **`excel_exporter.py`**: Implements `ExporterInterface` using `openpyxl`. Converts the array of `BusinessItem` objects into formatted columns. Applies styling parameters:
  * Injects current date string in export filenames if not present.
  * Creates target directory paths if they do not exist.
  * Formats headers with solid fills (dark slate blue) and white bold fonts.
  * Auto-fits column widths based on maximum string lengths + safety margin.
  * Formats borders and right-aligns numeric indicators (Rating, Reviews).

### 4.5 GUI Module (`src/ui/`)
* **`main_window.py`**: Builds the frame cards layout (Sidebar panel and Console card) using `QSplitter` and initiates window fade-in animations on load.
* **`controller.py`**: Mediates inputs, launches QThread processes, and sets up logging hooks.
* **`components/`**: Reusable custom widgets (`ConfigForm`, `ControlPanel`, `LogConsole`, `StatusIndicatorDot`).
* **`styles.py`**: Stores global Apple-styled CSS stylesheet (QSS) for aesthetic layouts.

---

## 5. Algorithms

### 5.1 Dynamic scrolling and lazy-loading (`_scroll_results_feed`)
```text
Algorithm 1: Dynamic scrolling of Maps Results list
Input: page (Browser Page), limit (target business count)
Output: Scroll feed until result count meets limit or end of list is reached

1: Find side panel feed container locator via RESULTS_LIST_PANEL selector
2: If feed locator is not visible, return
3: Set prev_count = 0, no_change_attempts = 0
4: Loop from attempt = 1 to max_scrolls (default 40):
5:     If is_cancelled flag is True:
6:         Raise InterruptedError
7:     Extract unique listing links from current DOM state
8:     If count of unique links >= limit:
9:         Log "Reached target results limit."
10:        Break loop
11:    Check if page displays footer messages ("You've reached the end of the list.")
12:    If footer message is visible:
13:        Log "End of results reached."
14:        Break loop
15:    Execute Javascript scrolling logic on feed container:
           "container.scrollTop = container.scrollHeight"
16:    Wait for scroll_delay_ms (default 1500ms) to allow network loading
17:    If count == prev_count:
18:        Increment no_change_attempts by 1
19:        If no_change_attempts >= 5:
20:            Log "Scrolling reached bottom."
21:            Break loop
22:    Else:
23:        Set no_change_attempts = 0
24:    Set prev_count = count
```

### 5.2 Listings extraction and polite delays (`_extract_listings`)
```text
Algorithm 2: Extractor Loop with Polite Rate-Limiting
Input: page, links (listing URLs), limit, progress_callback
Output: List of parsed BusinessItems

1: Set results = []
2: Set seen_urls = Empty Set
3: Set target_count = Minimum of (length of links, limit)
4: For each index, href in enumerate(links up to limit):
5:     If is_cancelled flag is True:
6:         Raise InterruptedError
7:     If index > 0:
8:         Generate random_delay between 2.0 and 5.0 seconds
9:         Wait for random_delay (Polite Scraping delay)
10:    Try:
11:        Scroll card link into view and click
12:        Wait for detail container element (BUSINESS_NAME selector) to be visible (timeout 5s)
13:        Wait 500ms for child elements rendering stability
14:        Parse details using MapsParser:
15:            name = Inner text of BUSINESS_NAME or "N/A"
16:            rating, reviews = Extract rating values and numeric review count text
17:            category = Inner text of BUSINESS_CATEGORY button or "N/A"
18:            address = Clean and format BUSINESS_ADDRESS text
19:            phone = Clean and format BUSINESS_PHONE text
20:            website = Extract href attribute from BUSINESS_WEBSITE anchor
21:        If parse succeeds and maps_url is not in seen_urls:
22:            Add normalized maps_url to seen_urls
23:            Trigger progress_callback(BusinessItem)
24:            Add BusinessItem to results list
25:    Catch PlaywrightTimeoutError:
26:        Log warning and continue to next item
27:    Catch Exception:
28:        Log error details and continue to next item
29: Return results
```

---

## 6. Testing

### 6.1 Unit Testing Strategy
Automated testing is built using the standard Python `unittest` module. Because external network requests and browser instances are dynamic and slow, mock-based testing strategies are heavily utilized:
1. **Configuration Checks**: Validating default configs, range overrides, and custom values inside `ScraperConfig`.
2. **Data Parsing (Pure Functions)**: Testing `MapsParser._clean_element_text` against clean strings, multi-line address blocks, and unicode icon headers.
3. **Browser Lifecycle Mocking**: Patching `sync_playwright` to simulate launch failures (`BrowserLaunchError`) and testing normal context creation and automatic cleanup hooks.
4. **DOM Extraction Mocks**: Creating mock `Page` objects with side-effect selectors that simulate name, category, website, and phone element visibilities, verifying that the extractor correctly parses them into structured dataclasses.
5. **Excel File Writing Tests**: Running tests that execute `ExcelExporter.export` locally to verify date-string file parsing, worksheet header matching, row calculations, and formatting rules.

### 6.2 Test Suite Execution Results
The test suite is executed using Python's unittest module discovery:
```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests
```
Output:
```text
..Playwright sync framework failed to start: Fatal launch
.......
----------------------------------------------------------------------
Ran 9 tests in 0.034s

OK
```
All unit and integration mock tests run and complete successfully with zero errors or failures.

---

## 7. Conclusion

### 7.1 Key Achievements
The GeoScrape application successfully meets all core functional and non-functional goals laid out in the requirements specifications:
1. **Responsiveness**: Integrating Qt background worker threads keeps the visual interface responsive during network wait cycles.
2. **Robust Extractor**: Modular selectors and robust default fallback structures prevent web layout omissions from crashing execution threads.
3. **Professional Presentation**: Features beautiful visual presentation layouts alongside clean code systems adhering directly to SOLID programming principles.
4. **Thread-safe Real-time Feedback**: Redirecting standard logging pipelines thread-safely allows users to view live extraction milestones.

### 7.2 Future Horizons
While highly effective, GeoScrape could be extended further post-curriculum:
* **API Ingestion Modules**: Integrating the official Google Places API backend to allow users to trade automation scraping for official rate-limited Google cloud interfaces.
* **IP Rotation Settings**: Exposing proxy lists inside config layouts to support high-volume scrapes.
* **Deep Leads Enrichment**: Automating separate browser scrapes on discovered business websites to extract contact emails and social media accounts.
