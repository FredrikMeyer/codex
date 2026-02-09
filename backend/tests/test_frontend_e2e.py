"""
E2E tests for the frontend using Playwright.
Tests the actual HTML/JS/CSS in a real browser.
"""

import http.server
import socketserver
import threading
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


import os


class FrontendServer(threading.Thread):
    """Serve frontend files on a local port."""

    def __init__(self, port: int):
        super().__init__(daemon=True)
        self.port = port
        self.frontend_dir = Path(__file__).parent.parent.parent / "frontend"
        self.httpd = None
        self._shutdown_requested = False

    def run(self):
        """Start HTTP server in the frontend directory."""
        handler = http.server.SimpleHTTPRequestHandler

        # Change to frontend directory
        original_dir = os.getcwd()
        try:
            os.chdir(self.frontend_dir)

            # Allow port reuse
            socketserver.TCPServer.allow_reuse_address = True
            self.httpd = socketserver.TCPServer(("", self.port), handler)
            self.httpd.serve_forever()
        finally:
            os.chdir(original_dir)

    def shutdown(self):
        """Stop the server."""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()


@pytest.fixture(scope="module")
def frontend_url():
    """Start a server for the frontend files."""
    import time
    port = 8080
    server = FrontendServer(port)
    server.start()

    # Wait for server to start
    time.sleep(1)

    url = f"http://localhost:{port}"
    yield url

    server.shutdown()


def test_frontend_loads(page: Page, frontend_url: str):
    """Test that the frontend loads and displays the main UI."""
    page.goto(frontend_url)

    # Check that the main heading is present
    expect(page.locator(".header-title")).to_contain_text("Asthma Medicine Tracker")

    # Check that the subtitle is present (first one in header)
    expect(page.locator("header .subtitle")).to_contain_text("Log your daily usage anywhere")


def test_medicine_type_selector(page: Page, frontend_url: str):
    """Test that medicine type buttons work."""
    page.goto(frontend_url)

    # Initially, Ventoline should be active (default)
    ventoline_btn = page.locator('button[data-type="ventoline"]')
    spray_btn = page.locator('button[data-type="spray"]')

    expect(ventoline_btn).to_have_class("medicine-type active")

    # Click spray button
    spray_btn.click()

    # Now spray should be active
    expect(spray_btn).to_have_class("medicine-type active")
    expect(ventoline_btn).to_have_class("medicine-type")


def test_counter_increment_decrement(page: Page, frontend_url: str):
    """Test that the counter increments and decrements."""
    page.goto(frontend_url)

    counter = page.locator("#count")
    increment_btn = page.locator("#increment")
    decrement_btn = page.locator("#decrement")

    # Initial count should be 0
    expect(counter).to_have_text("0")

    # Click increment 3 times
    increment_btn.click()
    expect(counter).to_have_text("1")

    increment_btn.click()
    expect(counter).to_have_text("2")

    increment_btn.click()
    expect(counter).to_have_text("3")

    # Click decrement
    decrement_btn.click()
    expect(counter).to_have_text("2")

    # Decrement should not go below 0
    decrement_btn.click()
    decrement_btn.click()
    decrement_btn.click()
    expect(counter).to_have_text("0")


def test_save_and_display_entry(page: Page, frontend_url: str):
    """Test saving an entry and seeing it in history."""
    page.goto(frontend_url)

    # Set counter to 2
    increment_btn = page.locator("#increment")
    increment_btn.click()
    increment_btn.click()

    # Save
    save_btn = page.locator("#save")
    save_btn.click()

    # Toast should appear
    toast = page.locator("#toast")
    expect(toast).to_have_class("show")
    expect(toast).to_contain_text("Saved")

    # Entry should appear in history
    # Wait for toast to disappear
    page.wait_for_timeout(2000)

    # Check that an entry exists
    entries = page.locator(".entry")
    expect(entries).to_have_count(1)

    # Entry should show "2 doses (Ventoline: 2)"
    entry_text = entries.first.locator(".count").text_content()
    assert entry_text is not None
    assert "2 doses" in entry_text
    assert "Ventoline: 2" in entry_text


def test_switching_medicine_type_changes_counter(page: Page, frontend_url: str):
    """Test that switching medicine type shows the correct count for each type."""
    page.goto(frontend_url)

    counter = page.locator("#count")
    increment_btn = page.locator("#increment")
    save_btn = page.locator("#save")
    spray_btn = page.locator('button[data-type="spray"]')
    ventoline_btn = page.locator('button[data-type="ventoline"]')

    # Ventoline is selected by default
    # Increment to 2
    increment_btn.click()
    increment_btn.click()
    expect(counter).to_have_text("2")

    # Save
    save_btn.click()
    page.wait_for_timeout(500)

    # Switch to Spray
    spray_btn.click()

    # Counter should reset to 0 (no spray entries for today)
    expect(counter).to_have_text("0")

    # Increment spray
    increment_btn.click()
    expect(counter).to_have_text("1")

    # Save spray
    save_btn.click()
    page.wait_for_timeout(500)

    # Switch back to Ventoline
    ventoline_btn.click()

    # Should show 2 (the ventoline count we saved)
    expect(counter).to_have_text("2")

    # Check history shows both
    entry_text = page.locator(".entry").first.locator(".count").text_content()
    assert entry_text is not None
    assert "3 doses" in entry_text  # 2 ventoline + 1 spray = 3 total
    assert "Spray: 1" in entry_text
    assert "Ventoline: 2" in entry_text


def test_delete_entry(page: Page, frontend_url: str):
    """Test deleting an entry from history."""
    page.goto(frontend_url)

    # Create an entry
    increment_btn = page.locator("#increment")
    increment_btn.click()

    save_btn = page.locator("#save")
    save_btn.click()
    page.wait_for_timeout(500)

    # Entry should exist
    entries = page.locator(".entry")
    expect(entries).to_have_count(1)

    # Click delete button
    delete_btn = entries.first.locator("button.ghost")
    delete_btn.click()

    # Entry should be removed
    expect(page.locator(".entries")).to_contain_text("No history yet")


def test_reset_day(page: Page, frontend_url: str):
    """Test resetting the counter for the current day."""
    page.goto(frontend_url)

    counter = page.locator("#count")
    increment_btn = page.locator("#increment")
    save_btn = page.locator("#save")
    reset_btn = page.locator("#reset-day")

    # Set counter to 5
    for _ in range(5):
        increment_btn.click()

    expect(counter).to_have_text("5")

    # Save
    save_btn.click()
    page.wait_for_timeout(500)

    # Reset day
    reset_btn.click()

    # Counter should be 0
    expect(counter).to_have_text("0")

    # Toast should show "Reset for day"
    toast = page.locator("#toast")
    expect(toast).to_contain_text("Reset for day")


def test_ui_elements_present(page: Page, frontend_url: str):
    """Test that all main UI elements are present."""
    page.goto(frontend_url)

    # Date picker
    expect(page.locator("#usage-date")).to_be_visible()

    # Medicine type buttons
    expect(page.locator('button[data-type="spray"]')).to_be_visible()
    expect(page.locator('button[data-type="ventoline"]')).to_be_visible()

    # Counter controls
    expect(page.locator("#decrement")).to_be_visible()
    expect(page.locator("#count")).to_be_visible()
    expect(page.locator("#increment")).to_be_visible()

    # Action buttons
    expect(page.locator("#save")).to_be_visible()
    expect(page.locator("#reset-day")).to_be_visible()
    expect(page.locator("#export")).to_be_visible()

    # History section
    expect(page.locator("#entries")).to_be_visible()
