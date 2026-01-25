"""
This script visualizes HDB resale prices (Price Per Square Foot vs Remaining Lease)
by querying the normalized SQLite database directly.

Usage:
    python plot.py <transactions.db>
"""

from datetime import datetime
import seaborn as sns
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import sys
import sqlite3

def plot(df, title, filename="psf_vs_lease.png"):
    plt.figure(figsize=(12, 8))
    # remaining_lease is stored as a float, so we cast to int for grouping in boxplot
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

def get_data_optimized(db_file, towns=None, flat_types=None, models_exclude=None, months_ago=60):
    conn = sqlite3.connect(db_file)
    
    query = """
        SELECT 
            t.remaining_lease,
            (t.resale_price / (t.floor_area_sqm * 10.7639)) AS price_per_sqft
        FROM transactions t
        JOIN towns tw ON t.town_id = tw.id
        JOIN flat_types ft ON t.flat_type_id = ft.id
        JOIN flat_models fm ON t.flat_model_id = fm.id
        WHERE 1=1
    """
    params = []

    if towns:
        placeholders = ', '.join(['?'] * len(towns))
        query += f" AND tw.name IN ({placeholders})"
        params.extend(towns)

    if flat_types:
        placeholders = ', '.join(['?'] * len(flat_types))
        query += f" AND ft.name IN ({placeholders})"
        params.extend(flat_types)

    if models_exclude:
        placeholders = ', '.join(['?'] * len(models_exclude))
        query += f" AND fm.name NOT IN ({placeholders})"
        params.extend(models_exclude)

    if months_ago:
        # Calculate date in SQL
        query += " AND t.month >= date('now', ?)"
        params.append(f'-{months_ago} months')

    print("Executing optimized SQL query...")
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_plot_title(towns, flat_types, flat_models_exclude, months_ago):
    town_title = ", ".join(towns) if towns else 'ALL TOWNS'
    flat_type_title = ", ".join(flat_types) if flat_types else 'ALL FLATS'
    exclude_title = f"excluding {', '.join(flat_models_exclude)}" if flat_models_exclude else ''
    
    now = datetime.now()
    year, week_num, _ = now.isocalendar()

    return f"PSF vs Remaining Lease for {flat_type_title} in {town_title}\n{exclude_title} (Last {months_ago} months, Week {week_num} {year})"

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python plot.py <transactions.db>")
        sys.exit(1)
    
    db_file = sys.argv[1]
    
    # Configuration
    towns = ['BUKIT MERAH']
    flat_types = []
    flat_models_exclude = ['Premium Apartment', 'Premium Apartment Loft', 'DBSS']
    months_ago = 60

    df = get_data_optimized(db_file, towns, flat_types, flat_models_exclude, months_ago)
    
    if df.empty:
        print("No data found for the selected filters.")
    else:
        print(f"Plotting {len(df)} records fetched directly via SQL...")
        title = get_plot_title(towns, flat_types, flat_models_exclude, months_ago)
        plot(df, title)