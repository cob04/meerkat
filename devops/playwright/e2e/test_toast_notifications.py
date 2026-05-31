import re

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"


def _pick_dispensable_item_id(page: Page) -> int:
    page.goto(f"{BASE_URL}/inventory/?status=available")
    rows = page.locator("tbody tr")
    for i in range(rows.count()):
        row = rows.nth(i)
        qty_text = row.locator("td.tabular-nums").first.inner_text().strip()
        try:
            qty = int(qty_text)
        except ValueError:
            continue
        if qty < 1:
            continue
        href = row.locator('a[href^="/inventory/"]').first.get_attribute("href") or ""
        match = re.match(r"^/inventory/(\d+)/$", href)
        if match:
            return int(match.group(1))
    raise AssertionError("No available inventory item with quantity > 0 found")


@pytest.mark.e2e
def test_dispense_emits_toast_without_full_reload(logged_in_page: Page):
    page = logged_in_page
    item_id = _pick_dispensable_item_id(page)

    page.goto(f"{BASE_URL}/inventory/{item_id}/")
    page.evaluate("window.__pageLoadMarker = 'initial'")

    before_qty = int(
        page.locator("dt", has_text="Quantity").locator("xpath=following-sibling::dd").inner_text()
    )

    page.click(f'a[href="/inventory/{item_id}/dispense/"]')
    page.wait_for_url(f"{BASE_URL}/inventory/{item_id}/dispense/")
    page.fill('input[name="quantity"]', "1")
    page.click('button[type="submit"]')

    page.wait_for_url(f"{BASE_URL}/inventory/{item_id}/")

    toast = page.locator('div[role="status"]').first
    expect(toast).to_be_visible()
    expect(toast).to_contain_text("Dispensed 1x")

    assert (
        page.evaluate("window.__pageLoadMarker") == "initial"
    ), "hx-boost broke: full page reload wiped window state"

    after_qty = int(
        page.locator("dt", has_text="Quantity").locator("xpath=following-sibling::dd").inner_text()
    )
    assert after_qty == before_qty - 1, f"Expected quantity {before_qty - 1}, got {after_qty}"

    page.screenshot(path="/screenshots/dispense_toast.png", full_page=False)


@pytest.mark.e2e
def test_toast_auto_dismisses_success(logged_in_page: Page):
    page = logged_in_page
    item_id = _pick_dispensable_item_id(page)

    page.goto(f"{BASE_URL}/inventory/{item_id}/dispense/")
    page.fill('input[name="quantity"]', "1")
    page.click('button[type="submit"]')

    toast = page.locator('div[role="status"]').first
    expect(toast).to_be_visible()
    expect(toast).to_be_hidden(timeout=6000)


@pytest.mark.e2e
def test_dispense_over_available_shows_inline_error_not_toast(logged_in_page: Page):
    page = logged_in_page
    item_id = _pick_dispensable_item_id(page)
    page.goto(f"{BASE_URL}/inventory/{item_id}/")
    available = int(
        page.locator("dt", has_text="Quantity").locator("xpath=following-sibling::dd").inner_text()
    )

    page.goto(f"{BASE_URL}/inventory/{item_id}/dispense/")
    page.fill('input[name="quantity"]', str(available + 50))
    page.click('button[type="submit"]')

    expect(page).to_have_url(re.compile(r"/dispense/$"))
    expect(page.locator('div[role="status"]')).to_have_count(0)
