# property

## Database Schema

The `transactions.db` SQLite database is optimized using normalization to reduce redundancy. It contains the following tables and views:

### `transactions` Table
The main table containing resale records, referencing lookup tables via Foreign Keys.

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER | Primary Key |
| `month` | TEXT | Month of the transaction (YYYY-MM) |
| `town_id` | INTEGER | FK to `towns` table |
| `flat_type_id` | INTEGER | FK to `flat_types` table |
| `block_id` | INTEGER | FK to `blocks` table |
| `storey_range` | TEXT | Floor level range |
| `floor_area_sqm` | REAL | Floor area in square meters |
| `flat_model_id` | INTEGER | FK to `flat_models` table |
| `lease_commence_date` | INTEGER | Year the lease commenced |
| `remaining_lease` | REAL | Remaining lease in years (fractional) |
| `resale_price` | REAL | Transaction price in SGD |
| `original_id` | INTEGER | Original unique identifier from source |

### Lookup Tables
These tables store unique text values to save space.
- `towns`: `id`, `name`
- `flat_types`: `id`, `name`
- `flat_models`: `id`, `name`

### `blocks` Table
A cache of geocoded coordinates.

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER | Primary Key |
| `address` | TEXT | Full address (Block + Street Name) |
| `x` | REAL | X coordinate (SVY21) |
| `y` | REAL | Y coordinate (SVY21) |

### `v_transactions_full` View
A virtual view that joins all tables and recalculates derived columns for easy querying. Use this if you want the "original" format with full names and sqft calculations.

**Derived Columns in View:**
- `floor_area_sqft`: Calculated from `floor_area_sqm`
- `price_per_sqft`: Calculated from `resale_price` / `floor_area_sqft`
- `remaining_lease_int`: Integer part of `remaining_lease`

---

## Scripts

- `download_hdb_resale_prices.py`: Downloads raw data from Data.gov.sg API.
- `parse_transactions.py`: Processes raw CSV and populates/updates `transactions` table.
- `parse_addr.py`: Geocodes missing addresses and updates `blocks` table.
- `optimize_db.py`: Normalizes the database and creates views.
- `coord.py`: Utility for OneMap API geocoding.