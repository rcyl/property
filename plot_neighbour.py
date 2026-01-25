"""
This script visualizes HDB resale prices (Price Per Square Foot vs Remaining Lease)
for flats located within a specified radius of a target address by querying
 the normalized SQLite database.

Usage:
    python plot_neighbour.py <transactions.db> <target_address> <radius_in_m>
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import sys
from datetime import datetime
import addr_query

def get_neighbourhood_data(db_file, x_ref, y_ref, radius_m, months_ago=12, flat_types=None):
    conn = sqlite3.connect(db_file)
    
    # 1. Bounding Box Filter (SQL level for speed)
    # This roughly filters blocks before calculating exact distance in Python
    query = """
        SELECT 
            t.remaining_lease,
            (t.resale_price / (t.floor_area_sqm * 10.7639)) AS price_per_sqft,
            b.x,
            b.y,
            ft.name AS flat_type,
            t.month
        FROM transactions t
        JOIN blocks b ON t.block_id = b.id
        JOIN flat_types ft ON t.flat_type_id = ft.id
        WHERE b.x BETWEEN ? AND ?
          AND b.y BETWEEN ? AND ?
          AND t.month >= date('now', ?)
    """
    
    params = [
        x_ref - radius_m, x_ref + radius_m,
        y_ref - radius_m, y_ref + radius_m,
        f'-{months_ago} months'
    ]
    
    print(f"Fetching candidates from bounding box...")
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if df.empty:
        return df

    # 2. Precise Distance Filter (Python level)
    df['distance'] = np.sqrt((df['x'] - x_ref)**2 + (df['y'] - y_ref)**2)
    df = df[df['distance'] <= radius_m]
    
    # 3. Flat Type Filter
    if flat_types:
        df = df[df['flat_type'].isin(flat_types)]
        
    return df

def plot_neighbourhood(df, target_addr, radius_m, title, filename="neighbourhood_psf.png"):
    plt.figure(figsize=(12, 8))
    
    # Cast to int for grouping
    df['remaining_lease_int'] = df['remaining_lease'].astype(int)
    
    # Determine the full range of years to show gaps in the axis
    if not df.empty:
        min_year = int(df['remaining_lease_int'].min())
        max_year = int(df['remaining_lease_int'].max())
        full_range = range(min_year, max_year + 1)
    else:
        full_range = None
    
    sb = sns.boxplot(x='remaining_lease_int', y='price_per_sqft', data=df, order=full_range)
    sb.invert_xaxis()
    
    plt.title(title)
    plt.xlabel('Remaining Lease (Years)')
    plt.ylabel('Price Per Square Foot (SGD)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(filename)
    print(f"Plot saved to {filename}")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python plot_neighbour.py <transactions.db> <target_address> <radius_in_m>")
        sys.exit(1)
    
    db_file = sys.argv[1]
    target_addr = sys.argv[2]
    radius_m = float(sys.argv[3])
    
    print(f"Querying coordinates for {target_addr}...")
    x_ref, y_ref = addr_query.query_addr(target_addr)
    x_ref, y_ref = float(x_ref), float(y_ref)
    print(f"Reference Coordinates: {x_ref}, {y_ref}")

    # Configuration
    months_ago = 24 # Increased default for better sample size in small radii
    flat_types = ['3 ROOM', '4 ROOM', '5 ROOM']
    
    df = get_neighbourhood_data(db_file, x_ref, y_ref, radius_m, months_ago, flat_types)
    
    if df.empty:
        print(f"No transactions found within {radius_m}m of {target_addr} in the last {months_ago} months.")
    else:
        print(f"Found {len(df)} transactions. Plotting...")
        
        now = datetime.now()
        year, week_num, _ = now.isocalendar()
        title = (f"PSF vs Remaining Lease within {radius_m}m of {target_addr}\n"
                 f"({', '.join(flat_types)}) - Last {months_ago} months (Week {week_num} {year})")
        
        plot_neighbourhood(df, target_addr, radius_m, title)