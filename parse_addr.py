"""
This script efficiently updates the `blocks` table in the SQLite database by fetching
missing coordinates for addresses using the OneMap API.

It directly queries the `blocks` table for entries with NULL coordinates (x, y),
eliminating the need to scan the entire transactions table.

Usage:
    python parse_addr.py [database_file.db]
"""

import sqlite3
import sys
import coord
import os

DB_FILE = "transactions.db"

def update_blocks_cache(db_file):
    if not os.path.exists(db_file):
        print(f"Error: Database file {db_file} not found.")
        sys.exit(1)

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 1. Identify Blocks with Missing Coordinates
    print("Fetching addresses with missing coordinates from blocks table...")
    try:
        # Check if table exists first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='blocks'")
        if not cursor.fetchone():
            print("Error: 'blocks' table does not exist. Run download_hdb_resale_prices.py first.")
            conn.close()
            return

        cursor.execute("SELECT id, address FROM blocks WHERE x IS NULL OR y IS NULL")
        missing_rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Error reading blocks table: {e}")
        conn.close()
        sys.exit(1)

    total = len(missing_rows)
    print(f"Found {total} addresses waiting for geocoding.")

    if total == 0:
        print("All blocks are already geocoded. Exiting.")
        conn.close()
        return

    # 2. Fetch Coordinates and Update DB
    print("Fetching coordinates...")
    updated_count = 0
    
    for i, (block_id, addr) in enumerate(missing_rows):
        x, y = coord.get_xy(addr)
        
        status = "Not Found"
        if x is not None and y is not None:
            cursor.execute("UPDATE blocks SET x = ?, y = ? WHERE id = ?", (x, y, block_id))
            status = "Updated"
            updated_count += 1
            
        # Commit every 10 records
        if (i + 1) % 10 == 0:
            conn.commit()
            print(f"Processed {i + 1}/{total}: {addr} -> {status} (Success Rate: {updated_count}/{i+1})", end='\r')
        elif (i + 1) == total:
             print(f"Processed {i + 1}/{total}: {addr} -> {status} (Success Rate: {updated_count}/{i+1})", end='\r')

    conn.commit()
    conn.close()
    print(f"\nFinished processing. Updated {updated_count} blocks.")

if __name__ == '__main__':
    target_db = sys.argv[1] if len(sys.argv) > 1 else DB_FILE
    update_blocks_cache(target_db)