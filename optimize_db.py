import sqlite3
import os

def optimize_database(db_file):
    print(f"Optimizing {db_file}...")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 1. Create Lookup Tables
    print("Creating lookup tables...")
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
    """)

    # 2. Extract and Insert Unique Values
    print("Populating lookup tables...")
    cursor.execute("INSERT OR IGNORE INTO towns (name) SELECT DISTINCT town FROM transactions")
    cursor.execute("INSERT OR IGNORE INTO flat_types (name) SELECT DISTINCT flat_type FROM transactions")
    cursor.execute("INSERT OR IGNORE INTO flat_models (name) SELECT DISTINCT flat_model FROM transactions")

    # 3. Optimize Blocks Table (Ensure Integer PK)
    print(" restructuring blocks table...")
    # We need to make sure blocks has an INTEGER id to be referenced efficiently
    # Rename old blocks table
    cursor.execute("ALTER TABLE blocks RENAME TO blocks_old")
    
    cursor.execute("""
        CREATE TABLE blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT UNIQUE,
            x REAL,
            y REAL
        )
    """)
    
    # Migrate blocks data
    cursor.execute("INSERT INTO blocks (address, x, y) SELECT address, x, y FROM blocks_old")
    
    # 4. Create Normalized Transactions Table
    print("Creating normalized transactions table...")
    cursor.execute("""
        CREATE TABLE transactions_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT,
            town_id INTEGER,
            flat_type_id INTEGER,
            block_id INTEGER,
            street_name TEXT, 
            storey_range TEXT,
            floor_area_sqm REAL,
            flat_model_id INTEGER,
            lease_commence_date INTEGER,
            remaining_lease REAL,
            resale_price REAL,
            original_id INTEGER,
            FOREIGN KEY(town_id) REFERENCES towns(id),
            FOREIGN KEY(flat_type_id) REFERENCES flat_types(id),
            FOREIGN KEY(block_id) REFERENCES blocks(id),
            FOREIGN KEY(flat_model_id) REFERENCES flat_models(id)
        )
    """)
    # Note: We keep street_name temp here to help matching, or we assume block_id covers it?
    # The original 'blocks' table in previous step was keyed by 'address' (Block + Street).
    # So we can link solely by block_id if we match 'Block + Street'.

    # 5. Migrate Transaction Data
    print("Migrating transaction data (this might take a moment)...")
    # We construct the address on the fly to match the blocks table
    cursor.execute("""
        INSERT INTO transactions_new (
            month, town_id, flat_type_id, block_id, 
            storey_range, floor_area_sqm, flat_model_id, 
            lease_commence_date, remaining_lease, resale_price, original_id
        )
        SELECT 
            t.month, 
            tw.id, 
            ft.id, 
            b.id,
            t.storey_range, 
            t.floor_area_sqm, 
            fm.id, 
            t.lease_commence_date, 
            t.remaining_lease, 
            t.resale_price, 
            t._id
        FROM transactions t
        JOIN towns tw ON t.town = tw.name
        JOIN flat_types ft ON t.flat_type = ft.name
        JOIN flat_models fm ON t.flat_model = fm.name
        LEFT JOIN blocks b ON (t.block || ' ' || t.street_name) = b.address
    """)

    # 6. Create View for Backward Compatibility
    print("Creating virtual view...")
    cursor.execute("""
        CREATE VIEW v_transactions_full AS
        SELECT 
            t.month,
            tw.name AS town,
            ft.name AS flat_type,
            b.address AS full_address,
            t.storey_range,
            t.floor_area_sqm,
            fm.name AS flat_model,
            t.lease_commence_date,
            t.remaining_lease,
            t.resale_price,
            (t.floor_area_sqm * 10.7639) AS floor_area_sqft,
            (t.resale_price / (t.floor_area_sqm * 10.7639)) AS price_per_sqft,
            CAST(t.remaining_lease AS INTEGER) AS remaining_lease_int
        FROM transactions_new t
        JOIN towns tw ON t.town_id = tw.id
        JOIN flat_types ft ON t.flat_type_id = ft.id
        JOIN flat_models fm ON t.flat_model_id = fm.id
        LEFT JOIN blocks b ON t.block_id = b.id
    """)

    # 7. Cleanup
    print("Cleaning up old tables...")
    cursor.execute("DROP TABLE transactions")
    cursor.execute("DROP TABLE blocks_old")
    cursor.execute("ALTER TABLE transactions_new RENAME TO transactions")

    # 8. Vacuum to reclaim disk space
    print("Vacuuming database...")
    conn.commit()
    cursor.execute("VACUUM")
    
    conn.close()
    print("Optimization complete.")

if __name__ == "__main__":
    optimize_database("transactions.db")
