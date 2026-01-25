import requests
import sqlite3
import sys
import re
import time

DB_FILE = "transactions.db"

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
    """
    Returns the ID for a value in a lookup table. 
    If not found, inserts it and updates the cache.
    """
    if value in cache:
        return cache[value]
    
    cursor = conn.cursor()
    try:
        cursor.execute(f"INSERT INTO {table} ({column}) VALUES (?)", (value,))
        new_id = cursor.lastrowid
        cache[value] = new_id
        return new_id
    except sqlite3.IntegrityError:
        # Handling race condition if multiple things inserted (unlikely here)
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
    cursor = conn.cursor()

    # 1. Initialize caches to minimize DB reads
    print("Initializing caches...")
    
    # Towns
    towns_cache = {}
    cursor.execute("SELECT name, id FROM towns")
    for name, id in cursor.fetchall():
        towns_cache[name] = id
        
    # Flat Types
    flat_types_cache = {}
    cursor.execute("SELECT name, id FROM flat_types")
    for name, id in cursor.fetchall():
        flat_types_cache[name] = id
        
    # Flat Models
    flat_models_cache = {}
    cursor.execute("SELECT name, id FROM flat_models")
    for name, id in cursor.fetchall():
        flat_models_cache[name] = id
        
    # Blocks (Address -> ID)
    blocks_cache = {}
    cursor.execute("SELECT address, id FROM blocks")
    for address, id in cursor.fetchall():
        blocks_cache[address] = id

    # Existing Transactions (to skip duplicates)
    existing_ids = set()
    cursor.execute("SELECT original_id FROM transactions")
    for row in cursor.fetchall():
        existing_ids.add(row[0])
    
    print(f"Found {len(existing_ids)} existing records in DB.")

    # 2. Start Download Loop
    total_records_api = 0
    records_processed = 0
    new_records_count = 0
    
    params = {
        "resource_id": resource_id,
        "limit": limit,
        "offset": offset
    }
    
    print(f"Starting download for resource: {resource_id}")
    session = requests.Session()
    
    while True:
        try:
            response = session.get(base_url, params=params)
            
            if response.status_code == 429:
                print("\nRate limit hit. Sleeping for 2 seconds...")
                time.sleep(2)
                continue
                
            response.raise_for_status()
            data = response.json()
            
            if not data.get("success"):
                print("Error: API request failed.")
                break

            result = data["result"]
            total_records_api = result["total"]
            records = result["records"]
            
            if not records:
                break
            
            # Process batch
            for record in records:
                original_id = record['_id']
                
                # Skip if exists
                if original_id in existing_ids:
                    records_processed += 1
                    continue
                
                # Normalize Data
                town_id = get_or_create_id(conn, 'towns', 'name', record['town'], towns_cache)
                flat_type_id = get_or_create_id(conn, 'flat_types', 'name', record['flat_type'], flat_types_cache)
                flat_model_id = get_or_create_id(conn, 'flat_models', 'name', record['flat_model'], flat_models_cache)
                
                full_address = f"{record['block']} {record['street_name']}"
                # For blocks, we insert with NULL x, y if strictly new
                if full_address in blocks_cache:
                    block_id = blocks_cache[full_address]
                else:
                    cursor.execute("INSERT INTO blocks (address, x, y) VALUES (?, ?, ?)", (full_address, None, None))
                    block_id = cursor.lastrowid
                    blocks_cache[full_address] = block_id

                # Transform columns
                remaining_lease_val = str_to_years(record['remaining_lease'])
                
                # Insert into transactions
                cursor.execute("""
                    INSERT INTO transactions (
                        month, town_id, flat_type_id, block_id, 
                        storey_range, floor_area_sqm, flat_model_id, 
                        lease_commence_date, remaining_lease, resale_price, original_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record['month'],
                    town_id,
                    flat_type_id,
                    block_id,
                    record['storey_range'],
                    float(record['floor_area_sqm']),
                    flat_model_id,
                    int(record['lease_commence_date']),
                    remaining_lease_val,
                    float(record['resale_price']),
                    original_id
                ))
                
                new_records_count += 1
                records_processed += 1

            conn.commit()
            
            # Progress update
            sys.stderr.write(f"\rProcessed {records_processed} / {total_records_api} records. (New: {new_records_count})")
            sys.stderr.flush()
            
            if records_processed >= total_records_api:
                break
            
            offset += limit
            params["offset"] = offset
            
        except requests.exceptions.RequestException as e:
            print(f"\nRequest Error: {e}")
            time.sleep(5) 
        except Exception as e:
            print(f"\nUnexpected Error: {e}")
            break

    conn.close()
    print(f"\nOperation complete. Added {new_records_count} new records.")

if __name__ == "__main__":
    RESOURCE_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"
    download_hdb_data(RESOURCE_ID)

if __name__ == "__main__":
    RESOURCE_ID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"
    download_hdb_data(RESOURCE_ID)
