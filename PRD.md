# Product Requirements Document (PRD)

## Project Name: GeoScrape

---

## 1. Project Overview

### 1.1 Executive Summary
**GeoScrape** is an RPA (Robotic Process Automation) desktop application designed to automate the collection of publicly available business information from Google Maps and export it directly into structured Excel spreadsheets. 

For many small businesses, sales teams, and marketers, manually gathering local leads (e.g., finding all dental clinics in a specific city) is a time-consuming process involving repetitive copy-pasting of names, addresses, and phone numbers. GeoScrape automates this robotic task by driving a browser programmatically to search, extract, and format the data, delivering it to the user in a ready-to-use Excel file.

### 1.2 Target Audience & Project Level
This project is designed as a **small-to-mid level software project**, tailor-made for an **IT Diploma or Undergraduate Degree** curriculum. It provides practical exposure to:
- **GUI Development**: Designing user-friendly desktop interfaces using frameworks like Tkinter, PyQt (Python), Electron (JavaScript), or WPF (.NET).
- **RPA and Browser Automation**: Interacting with dynamic web applications using tools like Playwright, Selenium, or Puppeteer.
- **Data Engineering Basics**: HTML parsing, handling missing data gracefully, and using library APIs to read/write spreadsheet files.
- **Asynchronous Programming**: Keeping the UI responsive while a background scraper process runs.

---

## 2. Objectives

### 2.1 Product Objectives
- **Automate Lead Generation**: Eliminate manual data entry tasks for regional marketing and sales campaigns.
- **Ensure Data Quality**: Structure extracted information into neat tables without losing data integrity (e.g., handling variable address formats or missing fields).
- **Accessibility**: Provide a zero-configuration, simple desktop interface that non-technical users can operate.

### 2.2 Academic & Learning Objectives
- Demonstrate understanding of the **Model-View-Controller (Model-View-ViewModel or typical layout)** architecture pattern in desktop software.
- Implement **asynchronous design patterns** (e.g., multi-threading or worker processes) to prevent application freezes during scraping.
- Apply robust **error handling and logging** for real-world web variability (such as network latency, DOM changes, or anti-scraping blocks).
- Learn responsible scraping behaviors (e.g., introducing delays to prevent server overload).

---

## 3. Scope

### 3.1 In-Scope
- **Search Criteria Configuration**: A user interface containing input fields for the target search query (e.g., "Dentist") and location (e.g., "Chicago, IL").
- **Dynamic Scroll & Pagination**: The automation engine must scroll the Google Maps results panel dynamically to load additional results.
- **Data Extraction**: Scraping the following fields for each business:
  - Business Name
  - Rating (out of 5 stars)
  - Number of Reviews
  - Category (e.g., "Dental Clinic")
  - Full Address
  - Phone Number
  - Website URL (if available)
  - Google Maps URL
- **Real-Time Log Console**: An in-app log display showing the scraping progress (e.g., *"Found 'Smile Dental' - Extracting phone number..."*).
- **Local Storage Export**: Exporting the collected dataset to a locally stored Excel file (`.xlsx`) with automatically adjusted column widths.

### 3.2 Out-of-Scope (Excluded from Current Version)
- **Database Integration**: The app will not store results in an SQL/NoSQL database; it operates strictly on a session-to-spreadsheet basis.
- **Proxy Rotation / IP Masking**: Automated proxy rotation and VPN switching are excluded to keep the setup simple.
- **CAPTCHA Bypass Solvers**: The app will not integrate third-party CAPTCHA solving services (e.g., 2Captcha).
- **Multi-threaded/Parallel Scraping**: Scraping will run sequentially on a single thread to minimize the risk of rapid IP bans from Google.
- **Cloud/Web SaaS Architecture**: The application will remain a standard desktop client.

---

## 4. Functional Requirements

| ID | Feature Name | Description | Priority |
| :--- | :--- | :--- | :--- |
| **FR-1** | User Input Form | User must be able to specify `Keyword` (e.g., "Cafe"), `Location` (e.g., "Austin"), and `Max Results` (e.g., 50). | High |
| **FR-2** | Browser Automation Launch | The application must initialize a browser instance (e.g., Chromium) via Selenium/Playwright in either headless or headed mode. | High |
| **FR-3** | Dynamic Scroll Automator | The RPA engine must locate the Google Maps results panel and programmatically scroll down to trigger lazy-loading of more businesses. | High |
| **FR-4** | DOM Parser & Extractor | The system must parse the details page for each business and extract data fields. Missing fields must default to "N/A" rather than crashing the scraper. | High |
| **FR-5** | Progress Tracking UI | The GUI must display a progress bar and a visual log detailing the current scraper activity. | Medium |
| **FR-6** | Interrupt / Stop Button | The user must be able to halt the scraping process safely mid-run, saving whatever data has been collected up to that point. | Medium |
| **FR-7** | Excel Exporter | The app must export the collected data table to an `.xlsx` file using a standard file-save dialog window. | High |

---

## 5. Non-Functional Requirements

### 5.1 Usability & Interface
- **Clean Layout**: A single-window dashboard layout containing the input configuration on the left/top, and the progress log and action buttons on the right/bottom.
- **Feedback Loops**: Immediate response to user action (e.g., disabling the "Start Scrape" button while scraping is in progress to prevent duplicate processes).

### 5.2 Reliability & Fault Tolerance
- **Graceful Failures**: If network connectivity drops, the app should pause, log the error, and prompt the user rather than crashing.
- **Polite Scraping**: Implement a random delay (e.g., 2 to 5 seconds) between navigating business details to simulate human interaction and minimize IP blocks.

### 5.3 Technical Constraints & Environment
- **Target OS**: Cross-platform compatibility (Windows and macOS) using Python (Tkinter/PyQt) or Electron.
- **Zero Heavy Installs**: The package should compile to an executable (e.g., using `PyInstaller`) or bundle dependencies so the student doesn't have to install complex system drivers.

---

## 6. Limitations

- **HTML Class Vulnerability**: Google Maps often updates its DOM elements and CSS class names. The extraction logic will break if Google changes its layout, requiring code updates.
- **IP Rate Limiting**: Scraping large volumes (e.g., >200 records in one go) without pauses may trigger Google Maps to display CAPTCHAs or temporarily block the scraper's IP address.
- **Performance Cap**: Because scraping relies on actual page rendering and dynamic scrolling, data retrieval speeds are limited by network latency and artificial human delays.

---

## 7. Future Improvements (Post-Diploma scope)

- **API Integration Toggle**: Allow users to switch from RPA-scraping to the official Google Places API (which requires billing/API key but offers extreme speed and reliability).
- **Contact Info Enrichment**: Automate navigating to the scraped business website to find email addresses and social media links (LinkedIn, Facebook, Instagram).
- **Schedule Scraping**: Allow automated batch operations to run at specific scheduled hours of the day.
- **Proxy Pool Management**: Integrate a settings panel where users can load a list of proxy servers to bypass rate limits.
