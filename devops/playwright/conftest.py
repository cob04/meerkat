import pytest
from playwright.sync_api import Page

BASE_URL = "http://localhost:8000"
TEST_USERNAME = "e2e"
TEST_PASSWORD = "e2e-password"


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: Browser-driven end-to-end tests")


@pytest.fixture
def logged_in_page(page: Page) -> Page:
    page.goto(f"{BASE_URL}/admin/login/")
    page.fill('input[name="username"]', TEST_USERNAME)
    page.fill('input[name="password"]', TEST_PASSWORD)
    page.click('input[type="submit"], button[type="submit"]')
    page.wait_for_url(f"{BASE_URL}/admin/")
    return page
