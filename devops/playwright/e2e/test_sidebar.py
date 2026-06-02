import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"


def _aside_width(page):
    return page.locator("aside").bounding_box()["width"]


@pytest.mark.e2e
def test_sidebar_collapses_to_icon_rail_and_persists(page: Page):
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(f"{BASE_URL}/inventory/")
    page.wait_for_load_state("networkidle")

    # Expanded by default: label visible, full width.
    label = page.locator("aside a[title='Inventory'] span")
    expect(label).to_be_visible()
    assert _aside_width(page) > 200
    page.screenshot(path="/screenshots/sidebar_expanded.png")

    # Collapse: labels hidden, rail width, icon still present.
    page.get_by_label("Collapse sidebar").click()
    page.wait_for_timeout(400)
    expect(label).to_be_hidden()
    expect(page.locator("aside a[title='Inventory'] svg")).to_be_visible()
    collapsed_width = _aside_width(page)
    assert collapsed_width < 100
    page.screenshot(path="/screenshots/sidebar_collapsed.png")

    # Persists across reload.
    page.reload()
    page.wait_for_load_state("networkidle")
    assert _aside_width(page) < 100
    expect(page.locator("aside a[title='Inventory'] span")).to_be_hidden()

    # Expand again restores labels.
    page.get_by_label("Expand sidebar").click()
    page.wait_for_timeout(400)
    expect(page.locator("aside a[title='Inventory'] span")).to_be_visible()
    assert _aside_width(page) > 200
