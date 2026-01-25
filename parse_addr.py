"""
This script efficiently generates or updates the `blocks` table in the SQLite database,
which serves as a cache of address coordinates.

It identifies unique addresses from the `transactions` table that are missing from
the `blocks` table and fetches their coordinates using the OneMap API (via `coord.py`).

Usage:
    python parse_addr.py <database_file.db>
"""

import sqlite3
import sys
import coord
import os
import pandas as pd # Still useful for bulk operations if needed, but sqlite3 is sufficient here

def update_blocks_cache(db_file):
    if not os.path.exists(db_file):
        print(f"Error: Database file {db_file} not found.")
        sys.exit(1)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 1. Create blocks table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            address TEXT PRIMARY KEY,
            x REAL,
            y REAL
        )
    """)
    conn.commit()

    # 2. Get all unique addresses from transactions
    print("Fetching unique addresses from transactions table...")
    try:
        cursor.execute("SELECT DISTINCT block, street_name FROM transactions")
        transaction_rows = cursor.fetchall()
        unique_addresses = set([f"{row[0]} {row[1]}" for row in transaction_rows])
        print(f"Found {len(unique_addresses)} unique addresses in transactions.")
    except sqlite3.OperationalError as e:
        print(f"Error reading transactions table: {e}")
        conn.close()
        sys.exit(1)

    # 3. Get existing cached addresses
    print("Fetching existing addresses from blocks cache...")
    cursor.execute("SELECT address FROM blocks")
    cached_rows = cursor.fetchall()
    cached_addresses = set([row[0] for row in cached_rows])
    print(f"Found {len(cached_addresses)} addresses in blocks cache.")

    # 4. Identify Missing Addresses
    missing_addresses = list(unique_addresses - cached_addresses)
    print(f"Found {len(missing_addresses)} new addresses to geocode.")

    if not missing_addresses:
        print("No new addresses to process. Exiting.")
        conn.close()
        return

    # 5. Fetch Coordinates and Update DB
    print("Fetching coordinates...")
    new_data = []
    total = len(missing_addresses)
    
    for i, addr in enumerate(missing_addresses):
        x, y = coord.get_xy(addr)
        
        if x is not None and y is not None:
            # Insert immediately or batch? Batch is safer for speed, immediate is safer for crashes.
            # Let's batch commit every 10 or so.
            cursor.execute("INSERT OR REPLACE INTO blocks (address, x, y) VALUES (?, ?, ?)", (addr, x, y))
            status = "Found"
        else:
            status = "Not Found"
            # Optional: Record not founds to avoid re-querying?
            # For now, we skip inserting so they are retried next time.
            
        if (i + 1) % 10 == 0:
            conn.commit()
            print(f"Processed {i + 1}/{total}: {addr} -> {status}", end='\r')
        elif (i + 1) == total:
             print(f"Processed {i + 1}/{total}: {addr} -> {status}", end='\r')

    conn.commit()
    conn.close()
    print(f"\nFinished processing. Database updated.")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python parse_addr.py <database_file.db>")
        sys.exit(1)
    
    update_blocks_cache(sys.argv[1])
