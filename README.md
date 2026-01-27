# Singapore HDB Resale Price Analysis

A comprehensive toolkit for fetching, analyzing, and visualizing Singapore HDB resale transaction data. This project features a robust Python data pipeline and a serverless, browser-based web application for interactive exploration.

**[🌐 View Live Dashboard](https://rcyl.github.io/property/)**

## ✨ Key Features

*   **Interactive Web Dashboard:** A static, serverless web app hosted on GitHub Pages.
    *   **Market Trends:** Analyze Price Per Square Foot (PSF) vs. Remaining Lease across different towns and flat types.
    *   **Neighbourhood Search:** Enter any address or postal code to see transaction data for properties within a specific radius (e.g., 500m).
    *   **Client-Side SQL:** Powered by `sql.js` (WebAssembly), running SQL queries directly in your browser against the local `transactions.db`.
*   **Data Pipeline:**
    *   **Automated Ingestion:** Fetches the latest data from Data.gov.sg.
    *   **Geocoding:** Automatically resolves addresses to coordinates using the OneMap API.
    *   **Normalization:** Stores data in an optimized SQLite schema.

## 🚀 Getting Started (Development)

To run the pipeline or modify the web app locally:

### 1. Prerequisites
- **Python 3.9+**
- **uv** (Recommended) or `pip`

### 2. Installation
Clone the repository and install dependencies:

```bash
# Using uv (Recommended)
uv sync

# Using pip
pip install -r requirements.txt
```

### 3. Running the Web App Locally
Since the app uses WebAssembly, it must be served via a local web server (opening `index.html` directly won't work due to CORS).

```bash
python -m http.server 8000
# Open http://localhost:8000 in your browser
```

---

## 🛠️ Data Pipeline Usage

Follow these steps to update the dataset.

### Step 1: Ingest Data
Fetch the latest resale transactions directly from the Data.gov.sg API. This script automatically initializes the database schema and normalizes the data.
```bash
python download_hdb_resale_prices.py
```

### Step 2: Geocode Addresses
Enrich the data with geospatial coordinates (SVY21) using the OneMap API. This is required for neighborhood analysis.
```bash
python parse_addr.py
```

*Note: The web app automatically loads `transactions.db` from the root directory. After updating the data, simply commit and push the new `.db` file to deploy it.*

---

## 📊 Analysis & Visualization (Python)

Apart from the web app, you can use Jupyter notebooks or CLI scripts for analysis.

### Interactive Notebooks
1.  **`plot_analysis.ipynb`**: General price analysis.
2.  **`plot_neighbour.ipynb`**: Neighborhood-specific analysis.

**To run a notebook:**
```bash
uv run jupyter notebook plot_analysis.ipynb
```

### Command Line Scripts
Generate static plots directly from the terminal:

```bash
# Usage: python plot_neighbour.py <db_file> <address> <radius_m>
python plot_neighbour.py transactions.db "406 Ang Mo Kio Ave 10" 1000
```

---

## 🗄️ Database Schema

The `transactions.db` SQLite database is normalized for performance and storage efficiency.

### Tables

*   **`transactions`**: Core fact table (Price, Lease, Floor Area, etc.)
*   **`blocks`**: Caches geocoded coordinates (X, Y) to minimize API calls.
*   **`towns`, `flat_types`, `flat_models`**: Normalized lookup tables.

### Views

*   **`v_transactions_full`**: A convenience view joining all tables with calculated fields (e.g., `price_per_sqft`).

---

## 📂 Key Files
*   `index.html`, `js/`, `css/`: The static web application.
*   `download_hdb_resale_prices.py`: API data fetcher.
*   `parse_addr.py`: Geocoding service.
*   `plot.py`: Basic plotting script.
