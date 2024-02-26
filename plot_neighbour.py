from datetime import datetime
import seaborn as sns
import matplotlib
matplotlib.use('TkAgg')  # Or any other X11 back-end
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import csv
import sys
import addr_query

if __name__ == '__main__':

    if len(sys.argv) != 5:
        print("Usage is neighbour.py <resale_file.csv> <addr.csv> <addr> <radius in m>")
        sys.exit(1)
    
    resale_csv = sys.argv[1]
    blocks_csv = sys.argv[2]
    addr = sys.argv[3]
    x_ref, y_ref = addr_query.query_addr(addr)
    radius_in_m = float(sys.argv[4])
   
    x_ref = float(x_ref)
    y_ref = float(y_ref)

    print(x_ref, y_ref)

    df = pd.read_csv(resale_csv)
    blocks = pd.read_csv(blocks_csv)

    # Change the month to dataframes month
    df['month'] = pd.to_datetime(df['month'])

    df['address'] = df['block'] + ' ' + df['street_name']
    
    # Merge the two dataframes into 1
    df = pd.merge(df, blocks, on='address')
    
    # Calculate the eucludian distance
    df['distance'] = np.sqrt((df['x'] - x_ref)**2 + (df['y'] - y_ref)**2)

    months_ago = 60
    flat_type = ''
    period_ago = pd.Timestamp.today() - pd.DateOffset(months=months_ago)
    query = df
    query = query[query['month'] >= period_ago]
    if flat_type:
        query = query[query['flat_type'] == flat_type]
    query = query[query['distance'] <= radius_in_m]
 
    # pd.set_option('display.max_rows', None)  # Replace None with a number if you only want to increase the limit
    # Set option to display all columns (or a specific number)
    # pd.set_option('display.max_columns', None) 
    print(query)

    flat_counts = query['remaining_lease_int'].value_counts().sort_index(ascending=False)
    print(flat_counts)

    group = query.groupby('remaining_lease_int')['price_per_sqft']

    median = group.median().sort_index(ascending=False)
    mean = group.mean().sort_index(ascending=False)
    # print(median)
    # print(mean)

    # median_prices = query.groupby('flat_age_int')['price_per_sqft'].median().reset_index()
    plt.figure(figsize=(12, 8))
    sb = sns.boxplot(x='remaining_lease_int', y='price_per_sqft', data=query)
    sb.invert_xaxis()

    now = datetime.now()
    year, week_num, day_of_week = now.isocalendar()

    flat_title = 'ALL FLATS'
    if flat_type: 
        flat_title = flat_type

    title = """Price Per Square Foot vs Remaining Lease for {} Flats within {} 
    meters from {} with transactions within {} months from 
    week {} {}""".format(flat_title, radius_in_m, addr, months_ago, week_num, year)
    plt.title(title)
    plt.xlabel('Flat Age (Years)')
    plt.ylabel('Price Per Square Foot (SGD)')
    plt.xticks(rotation=45)  # Rotate x-axis labels for better readability
    plt.tight_layout()  # Adjust layout to make room for the rotated x-axis labels
    plt.show()




  