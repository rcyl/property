"""
This script queries the OneMap API to retrieve the X and Y coordinates (SVY21)
for a given address string. It is intended to be used as a command-line tool.

Usage:
    python addr_query.py "<address>"
"""

import coord
import sys
import requests
import urllib.parse

def query_addr(addr):
    address_encoded = urllib.parse.quote(addr)

    url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={address_encoded}&returnGeom=Y&getAddrDetails=Y"
    # Send a GET request to the OneMap API
    response = requests.get(url)

    if response.status_code != 200:
        print("Error in performing GET request")
        sys.exit(1)

    data = response.json()

    if len(data['results']) == 0:
        print("No data found")
        sys.exit(1)

    print(data)

    # Get the latitude and longitude
    x = data['results'][0]['X']
    y = data['results'][0]['Y']

    return x, y

if __name__ == '__main__':

    if len(sys.argv) != 2:
        print("Usage is addr_query.py <addr>")
        sys.exit(1)
    
    addr = sys.argv[1]

    x, y = query_addr(addr)
    print(x, y)