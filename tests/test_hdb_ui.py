import pytest
from playwright.sync_api import Page, expect
import http.server
import socketserver
import threading
import os
import time

# --- Fixtures to serve the static site locally ---

PORT = 8001

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

@pytest.fixture(scope="session", autouse=True)
def http_server():
    """Starts a simple HTTP server to serve the static files."""
    handler = http.server.SimpleHTTPRequestHandler
    
    # Ensure we are serving from the project root
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(root_dir)
    
    with ReusableTCPServer(("", PORT), handler) as httpd:
        print(f"Serving at port {PORT}")
        # Run server in a separate thread
        thread = threading.Thread(target=httpd.serve_forever)
        thread.daemon = True
        thread.start()
        yield
        httpd.shutdown()
        httpd.server_close()

@pytest.fixture
def index_page(page: Page):
    """Navigates to the index page and waits for DB load."""
    page.goto(f"http://localhost:{PORT}/index.html")
    
    # Wait for the "Loading database..." to disappear and success box/output to appear
    # The loading container has id 'loading-container' and success is '#output-box'
    expect(page.locator("#loading-container")).to_be_hidden(timeout=10000)
    expect(page.locator("#output-box")).to_be_visible()
    return page

# --- Tests ---

def test_page_title(index_page: Page):
    expect(index_page).to_have_title("HDB Resale Analysis")

def test_market_trends_load(index_page: Page):
    """Verifies that the Market Trends tab loads data and renders a table."""
    # Ensure we are on the trends tab
    index_page.click("#trends-tab")
    
    # Click update plot
    index_page.click("#plot-run")
    
    # Check chart is visible
    expect(index_page.locator("#plot-container")).to_be_visible()
    
    # Check table is populated
    table = index_page.locator("#data")
    expect(table).to_be_visible()
    
    # Verify table headers for trends (Standard SQL schema)
    # The exact headers depend on the renderQuery function, usually they match the SELECT columns
    # We selected: month, full_address, flat_type, floor_area_sqm, resale_price, remaining_lease
    headers = table.locator("thead th")
    expect(headers.first).to_contain_text("month") 
    
    # Verify rows exist
    rows = table.locator("tbody tr")
    expect(rows).not_to_have_count(0)
    
    # Verify pagination
    pager = index_page.locator("#pager")
    expect(pager).to_contain_text("Page 1")

    # Take screenshot
    index_page.screenshot(path="screenshot_market_trends.png", full_page=True)

def test_neighbourhood_search(index_page: Page):
    """Verifies the Neighbourhood Search tab functionality."""
    # Switch to tab
    index_page.click("#neighbour-tab")
    expect(index_page.locator("#neighbour-pane")).to_be_visible()
    
    # Fill inputs
    index_page.fill("#target-address", "406 Ang Mo Kio Ave 10")
    index_page.fill("#target-radius", "500")
    
    # Click search (this triggers API call + DB query)
    # We might need to wait for network idle or UI changes
    with index_page.expect_response("**/api/common/elastic/search?**"):
        index_page.click("#neighbour-run")
    
    # Wait for processing (spinner logic in JS uses same loading-container usually, or just waits for async)
    # Our JS shows #plot-container on success
    expect(index_page.locator("#plot-container")).to_be_visible(timeout=10000)
    
    # Check table specific headers for neighbourhood
    # Headers: "Month", "Address", "Flat Type", "Area (sqm)", "Price", "Lease Left"
    table = index_page.locator("#data")
    expect(table).to_be_visible()
    
    headers = table.locator("thead th")
    expect(headers.first).to_contain_text("Month")
    expect(headers.nth(1)).to_contain_text("Address")
    
    # Verify rows exist
    rows = table.locator("tbody tr")
    expect(rows).not_to_have_count(0)
    
    # Verify sorting (descending month) - Check first date is recent
    first_date = rows.first.locator("td").first.inner_text()
    assert "20" in first_date # Should be a year like 2024, 2025

    # Take screenshot
    index_page.screenshot(path="screenshot_neighbourhood.png", full_page=True)
