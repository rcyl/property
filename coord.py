import requests
import urllib.parse
import time

def get_xy(addr):
    """
    Queries OneMap API for X, Y coordinates of an address.
    Returns (x, y) as floats, or (None, None) if not found/error.
    """
    try:
        address_encoded = urllib.parse.quote(addr)
        url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={address_encoded}&returnGeom=Y&getAddrDetails=Y"
        
        # Add a small delay to respect API rate limits
        time.sleep(0.1) 
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['found'] > 0:
                result = data['results'][0]
                return float(result['X']), float(result['Y'])
    except Exception as e:
        print(f"Error fetching {addr}: {e}")
        
    return None, None
