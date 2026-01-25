import requests
import sqlite3
import sys
import time

DB_FILE = "transactions.db"
# Resource ID for HDB Resale Prices (check data.gov.sg for updates)
RESOURCE_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc" 

def init_db(conn):
    """Initializes the normalized database schema."""
    cursor = conn.cursor()
    
    # 1. Lookup Tables
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS towns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS flat_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS flat_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        );
        CREATE TABLE IF NOT EXISTS blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT UNIQUE,
            x REAL,
            y REAL
        );
    """)

    # 2. Main Transactions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT,
            town_id INTEGER,
            flat_type_id INTEGER,
            block_id INTEGER,
            storey_range TEXT, 
            floor_area_sqm REAL,
            flat_model_id INTEGER,
            lease_commence_date INTEGER,
            remaining_lease REAL,
            resale_price REAL,
            original_id INTEGER UNIQUE,
            FOREIGN KEY(town_id) REFERENCES towns(id),
            FOREIGN KEY(flat_type_id) REFERENCES flat_types(id),
            FOREIGN KEY(block_id) REFERENCES blocks(id),
            FOREIGN KEY(flat_model_id) REFERENCES flat_models(id)
        )
    """)
    
    # 3. View (Optional, but good for analysis)
    cursor.execute("DROP VIEW IF EXISTS v_transactions_full")
    cursor.execute("""
        CREATE VIEW v_transactions_full AS
        SELECT 
            t.month,
            tw.name AS town,
            ft.name AS flat_type,
            b.address AS full_address,
            b.x, b.y,
            t.storey_range,
            t.floor_area_sqm,
            fm.name AS flat_model,
            t.lease_commence_date,
            t.remaining_lease,
            t.resale_price,
            (t.floor_area_sqm * 10.7639) AS floor_area_sqft,
            (t.resale_price / (t.floor_area_sqm * 10.7639)) AS price_per_sqft,
            CAST(t.remaining_lease AS INTEGER) AS remaining_lease_int
        FROM transactions t
        JOIN towns tw ON t.town_id = tw.id
        JOIN flat_types ft ON t.flat_type_id = ft.id
        JOIN flat_models fm ON t.flat_model_id = fm.id
        JOIN blocks b ON t.block_id = b.id
    """)
    conn.commit()

def str_to_years(date_str):
    """Parses '61 years 04 months' to 61.333..."""
    try:
        parts = date_str.split()
        years = int(parts[0])
        months = 0
        if len(parts) > 2:
            months = int(parts[2])
        return years + (months / 12.0)
    except (ValueError, IndexError, AttributeError):
        return 0.0

def get_or_create_id(conn, table, column, value, cache):
    if value in cache:
        return cache[value]
    
    cursor = conn.cursor()
    try:
        cursor.execute(f"INSERT INTO {table} ({column}) VALUES (?)", (value,))
        new_id = cursor.lastrowid
        cache[value] = new_id
        return new_id
    except sqlite3.IntegrityError:
        cursor.execute(f"SELECT id FROM {table} WHERE {column} = ?", (value,))
        result = cursor.fetchone()
        if result:
            id_val = result[0]
            cache[value] = id_val
            return id_val
        raise

def download_hdb_data(resource_id):
    base_url = "https://data.gov.sg/api/action/datastore_search"
    limit = 2000
    offset = 0
    
    conn = sqlite3.connect(DB_FILE)
    
    # Ensure schema exists
    init_db(conn)
    
    cursor = conn.cursor()

    # 1. Initialize caches
    print("Initializing caches...")
    towns_cache = {name: i for name, i in cursor.execute("SELECT name, id FROM towns").fetchall()}
    flat_types_cache = {name: i for name, i in cursor.execute("SELECT name, id FROM flat_types").fetchall()}
    flat_models_cache = {name: i for name, i in cursor.execute("SELECT name, id FROM flat_models").fetchall()}
    blocks_cache = {addr: i for addr, i in cursor.execute("SELECT address, id FROM blocks").fetchall()}
    
    existing_ids = set(row[0] for row in cursor.execute("SELECT original_id FROM transactions").fetchall())
    print(f"Found {len(existing_ids)} existing records in DB.")

    # 2. Download Loop
    total_records_api = 0
    records_processed = 0
    new_records_count = 0
    
    params = {"resource_id": resource_id, "limit": limit, "offset": offset}
    print(f"Starting download for resource: {resource_id}")
    session = requests.Session()
    
    while True:
        try:
            response = session.get(base_url, params=params)
            if response.status_code == 429:
                print("Rate limit hit. Sleeping...")
                time.sleep(2)
                continue
            response.raise_for_status()
            data = response.json()
            
            if not data.get("success"):
                break

            result = data["result"]
            total_records_api = result["total"]
            records = result["records"]
            
            if not records:
                break
            
            for record in records:
                original_id = record['_id']
                if original_id in existing_ids:
                    records_processed += 1
                    continue
                
                town_id = get_or_create_id(conn, 'towns', 'name', record['town'], towns_cache)
                flat_type_id = get_or_create_id(conn, 'flat_types', 'name', record['flat_type'], flat_types_cache)
                flat_model_id = get_or_create_id(conn, 'flat_models', 'name', record['flat_model'], flat_models_cache)
                
                full_address = f"{record['block']} {record['street_name']}"
                if full_address in blocks_cache:
                    block_id = blocks_cache[full_address]
                else:
                    cursor.execute("INSERT INTO blocks (address, x, y) VALUES (?, ?, ?)", (full_address, None, None))
                    block_id = cursor.lastrowid
                    blocks_cache[full_address] = block_id

                remaining_lease_val = str_to_years(record['remaining_lease'])
                
                cursor.execute("""
                    INSERT INTO transactions (
                        month, town_id, flat_type_id, block_id, 
                        storey_range, floor_area_sqm, flat_model_id, 
                        lease_commence_date, remaining_lease, resale_price, original_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record['month'], town_id, flat_type_id, block_id, 
                    record['storey_range'], float(record['floor_area_sqm']), flat_model_id, 
                    int(record['lease_commence_date']), remaining_lease_val, float(record['resale_price']), original_id
                ))
                new_records_count += 1
                records_processed += 1

            conn.commit()
            sys.stderr.write(f"\rProcessed {records_processed} / {total_records_api} records. (New: {new_records_count})")
            sys.stderr.flush()
            
            if records_processed >= total_records_api:
                break
            
            offset += limit
            params["offset"] = offset
            
        except Exception as e:
            print(f"\nError: {e}")
            break

    conn.close()
    print(f"\nOperation complete. Added {new_records_count} new records.")

if __name__ == "__main__":
    download_hdb_data(RESOURCE_ID)