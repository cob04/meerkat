import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"


@pytest.mark.e2e
def test_products_autocomplete(page: Page):
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_viewport_size({"width": 1280, "height": 900})

    page.goto(f"{BASE_URL}/products/")
    page.wait_for_load_state("networkidle")

    box = page.locator("input[name='q']")
    box.click()
    box.press_sequentially("pan", delay=60)
    page.wait_for_timeout(700)

    suggestion = page.locator("#q-suggest button", has_text="Panadol").first
    expect(suggestion).to_be_visible()
    page.screenshot(path="/screenshots/autocomplete_open.png")

    suggestion.click()
    page.wait_for_timeout(700)
    expect(box).to_have_value("Panadol")
    # Results filtered to the chosen product.
    assert "Panadol" in page.locator("#products-results").inner_text()

    # Re-open then Escape closes the dropdown.
    box.click()
    box.press_sequentially("a", delay=60)
    page.wait_for_timeout(500)
    box.press("Escape")
    page.wait_for_timeout(200)
    expect(page.locator("#q-suggest")).to_be_hidden()

    assert not errors
