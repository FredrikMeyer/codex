"""
Example Playwright browser test (currently skipped).

This shows how to write browser-based E2E tests for the frontend.
To enable, install browsers with: uv run playwright install
Then remove the skip marker.
"""

import pytest

pytestmark = pytest.mark.skip(reason="Browser tests not yet implemented")


def test_frontend_loads_in_browser(page, server_url):
    """Example: Test that the frontend loads and displays correctly."""
    # This would test the actual frontend HTML/JS
    # page.goto(f"{server_url}/")
    # expect(page.locator("h1")).to_contain_text("Asthma Medicine Tracker")
    pass


def test_user_can_increment_counter(page, server_url):
    """Example: Test that user can increment the counter."""
    # page.goto(f"{server_url}/")
    # page.click("#increment")
    # expect(page.locator("#count")).to_have_text("1")
    pass
