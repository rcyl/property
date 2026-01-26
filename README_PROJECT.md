# Singapore HDB Resale Price Analysis

This project provides a comprehensive toolkit for fetching, normalizing, storing, and visualizing Singapore HDB resale transaction data. It includes a robust data pipeline and analysis tools to explore price trends and perform geospatial queries.

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.9+**
- **uv** (Recommended for dependency management) or `pip`

### 2. Installation
Clone the repository and install dependencies:

```bash
# Using uv (Recommended)
uv sync

# Using pip
pip install -r requirements.txt
```

*(Note: If `requirements.txt` is missing, dependencies include `pandas`, `matplotlib`, `seaborn`, `requests`, `numpy`, and `jupyter`)*

---

## 🛠️ Data Pipeline Usage

Follow these steps to build and maintain your database.

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

---

## 📊 Analysis & Visualization

### Interactive Notebooks
We provide Jupyter notebooks for interactive exploration.

1.  **`plot_analysis.ipynb`**: General price analysis. Filter by town, flat type, and model to visualize Price Per Square Foot (PSF) vs. Remaining Lease.
2.  **`plot_neighbour.ipynb`**: Neighborhood-specific analysis. Enter a target address (e.g., "406 Ang Mo Kio Ave 10") to visualize trends for flats within a specific radius.

**To run a notebook:**
```bash
uv run jupyter notebook plot_analysis.ipynb
# or
jupyter notebook plot_neighbour.ipynb
```

### Command Line Scripts
You can also generate static plots directly from the command line.

**Neighborhood Analysis:**
```bash
# Usage: python plot_neighbour.py <db_file> <address> <radius_m>
python plot_neighbour.py transactions.db "406 Ang Mo Kio Ave 10" 1000
```

---

## 🗄️ Database Schema

The `transactions.db` SQLite database is normalized for performance and storage efficiency.

### Tables

#### `transactions`
The core fact table containing resale records.
- **`id`**: Primary Key
- **`month`**: Transaction month (YYYY-MM)
- **`town_id`**: Foreign Key -> `towns.id`
- **`flat_type_id`**: Foreign Key -> `flat_types.id`
- **`block_id`**: Foreign Key -> `blocks.id`
- **`storey_range`**: Floor range (e.g., "10 TO 12")
- **`floor_area_sqm`**: Floor area in square meters
- **`flat_model_id`**: Foreign Key -> `flat_models.id`
- **`lease_commence_date`**: Year lease commenced
- **`remaining_lease`**: Remaining lease in years (stored as float)
- **`resale_price`**: Transaction price in SGD
- **`original_id`**: Unique ID from the source API (used for deduplication)

#### `blocks`
Caches geocoded coordinates to minimize OneMap API calls.
- **`id`**: Primary Key
- **`address`**: Full address (Block + Street Name)
- **`x`**: X coordinate (SVY21)
- **`y`**: Y coordinate (SVY21)

#### Lookup Tables
Normalized tables to reduce redundancy.
- **`towns`**: `id`, `name` (e.g., "ANG MO KIO")
- **`flat_types`**: `id`, `name` (e.g., "3 ROOM")
- **`flat_models`**: `id`, `name` (e.g., "New Generation")

### Views

#### `v_transactions_full`
A convenience view that joins all tables and adds calculated fields for easier analysis:
- All original fields with resolved names (e.g., `town`, `flat_type`)
- `full_address`, `x`, `y`
- `floor_area_sqft`: Converted from sqm ($sqm \times 10.7639$)
- `price_per_sqft`: Calculated unit price ($price / sqft$)

---

## 📂 Key Files
- `download_hdb_resale_prices.py`: API data fetcher and schema initializer.
- `parse_addr.py`: Geocoding service.
- `coord.py`: OneMap API utility.
- `plot.py`: Basic plotting script.