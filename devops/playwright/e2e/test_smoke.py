from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"


def test_inventory_page_loads(page: Page):
    page.goto(f"{BASE_URL}/inventory/")
    expect(page).to_have_title("Inventory - Meerkat")
    expect(page.locator("table")).to_be_visible()
