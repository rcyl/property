from datetime import datetime
import seaborn as sns
import matplotlib
matplotlib.use('TkAgg')  # Or any other X11 back-end
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import time
import csv
import sys

def plot(df, title):
    plt.figure(figsize=(12, 8))
    sb = sns.boxplot(x='remaining_lease_int', y='price_per_sqft', data=df)
    sb.invert_xaxis()
    plt.title(title)
    plt.xlabel('Remaining Lease (Years)')
    plt.ylabel('Price Per Square Foot (SGD)')
    plt.xticks(rotation=45)  # Rotate x-axis labels for better readability
    plt.tight_layout()  # Adjust layout to make room for the rotated x-axis labels
    plt.show()

def get_plot_title(towns, flat_types, flat_models_exclude, months_ago):
    
    town_title = 'ALL TOWNS'
    flat_type_title = 'ALL FLATS'
    exclude_title = ''
    if towns: 
        town_title = ", ".join(towns)
    if flat_types:
        flat_type_title = ", ".join(flat_types)
    if flat_models_exclude:
        exclude_title = "excluding {} flat models".format(", ".join(flat_models_exclude))

    now = datetime.now()
    # Extract the ISO week number
    year, week_num, day_of_week = now.isocalendar()

    title = """Price Per Square Foot vs Remaining Lease for {} 
    Flats in {}, {} with transactions within {} 
    months from Week {} {}""".format(
        flat_type_title, town_title, exclude_title, months_ago, week_num, year
    )

    return title

def query(df, towns, flat_types, flat_models_exclude, months_ago):

    df['month'] = pd.to_datetime(df['month'])
    query = df

    if towns:
        query = query[query['town'].isin(towns)]
    
    if flat_types:
        query = query[query['flat_type'].isin(flat_types)]

    if flat_models_exclude:
        query = query[~query['flat_model'].isin(flat_models_exclude)]

    if months_ago:
        period_ago = pd.Timestamp.today() - pd.DateOffset(months=months_ago)
        query = query[query['month'] >= period_ago]

    flat_counts = query['remaining_lease_int'].value_counts().sort_index(ascending=False)

    return query, flat_counts

if __name__ == '__main__':
    
    if len(sys.argv) != 2:
        print("Usage is plot.py <resale_file.csv>")
        sys.exit(1)
    
    df = pd.read_csv(sys.argv[1])

    towns = ['QUEENSTOWN', 'CLEMENTI']
    flat_types = ['4 ROOM']
    flat_models_exclude = [
        'Premium Apartment', 'Premium Apartment Loft', 'DBSS'
    ]
    months_ago = 12

    df, flat_counts = query(df, towns, flat_types, flat_models_exclude, months_ago)
    print(df)
    print(flat_counts)
    title = get_plot_title(towns, flat_types, flat_models_exclude, months_ago)
    plot(df, title)
   


  