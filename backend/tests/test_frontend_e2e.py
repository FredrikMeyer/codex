"""
E2E tests for the frontend using Playwright.
Tests the actual HTML/JS/CSS in a real browser.
"""

import http.server
import os
import socketserver
import threading
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from app.main import create_app


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


class BackendServer(threading.Thread):
    """Run the Flask backend on localhost:5000."""

    def __init__(self, port: int, data_file: Path):
        super().__init__(daemon=True)
        self.port = port
        self.data_file = data_file
        self.server = None
        self._shutdown_requested = False
        self._started = threading.Event()

    def run(self):
        """Start Flask server."""
        try:
            from werkzeug.serving import make_server

            app = create_app(self.data_file)
            app.config["TESTING"] = True

            # Allow port reuse
            socketserver.TCPServer.allow_reuse_address = True
            self.server = make_server("127.0.0.1", self.port, app, threaded=True)
            self._started.set()  # Signal that server is ready
            self.server.serve_forever()
        except Exception as e:
            print(f"Backend server failed to start: {e}")
            self._started.set()  # Signal even on failure so we don't hang

    def wait_until_started(self, timeout=5):
        """Wait for server to start."""
        return self._started.wait(timeout)

    def shutdown(self):
        """Stop the server."""
        if self.server:
            self.server.shutdown()


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


@pytest.fixture(scope="module")
def backend_url(tmp_path_factory):
    """Start a backend server for E2E tests."""
    import requests
    import time

    # Use port 5555 to avoid conflict with macOS ControlCenter on port 5000
    port = 5555

    # Ensure CORS is configured for frontend origin before server starts
    os.environ["ALLOWED_ORIGINS"] = "http://localhost:8080"

    # Also ensure no .env file interferes
    if "PRODUCTION" in os.environ:
        del os.environ["PRODUCTION"]

    tmp_path = tmp_path_factory.mktemp("backend_data")
    data_file = tmp_path / "data.json"

    server = BackendServer(port, data_file)
    server.start()

    # Wait for server to start
    if not server.wait_until_started(timeout=5):
        raise RuntimeError("Backend server failed to start")

    # Give it a moment to fully initialize
    time.sleep(1)

    url = f"http://localhost:{port}"

    # Verify server is responding by trying generate-code endpoint
    max_retries = 15
    for i in range(max_retries):
        try:
            response = requests.post(f"{url}/generate-code", timeout=2)
            if response.status_code in [200, 429]:  # 200 OK or 429 Rate Limited - both mean server is up
                break
        except requests.exceptions.ConnectionError:
            if i < max_retries - 1:
                time.sleep(0.3)
                continue
            raise RuntimeError(f"Backend server not responding on {url}")

    yield url, data_file

    server.shutdown()


@pytest.fixture()
def client(tmp_path: Path):
    """Create a test client for the backend API."""
    data_file = tmp_path / "data.json"
    app = create_app(data_file)
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


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


def test_sync_setup_ui_elements_present(page: Page, frontend_url: str):
    """Test that sync setup UI elements are present."""
    page.goto(frontend_url)

    # Sync status section
    expect(page.locator("#sync-status")).to_be_visible()
    expect(page.locator("#sync-status-text")).to_be_visible()
    expect(page.locator(".status-dot")).to_be_visible()

    # Initially should show "Not configured"
    expect(page.locator("#sync-status-text")).to_contain_text("Not configured")

    # Sync setup section should be visible
    expect(page.locator("#sync-setup")).to_be_visible()

    # Setup buttons and inputs
    expect(page.locator("#generate-code")).to_be_visible()
    expect(page.locator("#code-input")).to_be_visible()
    expect(page.locator("#complete-setup")).to_be_visible()

    # Configured section should be hidden initially
    expect(page.locator("#sync-configured")).not_to_be_visible()


def test_sync_token_storage_in_localstorage(page: Page, frontend_url: str):
    """Test that token storage and retrieval works via localStorage."""
    page.goto(frontend_url)

    # Clear any existing token
    page.evaluate("localStorage.removeItem('asthma-auth-token')")
    page.reload()

    # Verify no token initially
    has_token = page.evaluate("() => localStorage.getItem('asthma-auth-token') !== null")
    assert has_token is False

    # Verify UI shows "Not configured"
    expect(page.locator("#sync-status-text")).to_contain_text("Not configured")

    # Simulate storing a token (as the backend integration would do)
    test_token = "test-token-123456789abcdef"
    page.evaluate(f"localStorage.setItem('asthma-auth-token', '{test_token}')")
    page.reload()

    # Verify token is stored
    stored_token = page.evaluate("localStorage.getItem('asthma-auth-token')")
    assert stored_token == test_token

    # Verify UI updates to show "Connected"
    expect(page.locator("#sync-status-text")).to_contain_text("Connected")

    # Verify setup section is hidden
    expect(page.locator("#sync-setup")).not_to_be_visible()

    # Verify configured section is visible
    expect(page.locator("#sync-configured")).to_be_visible()

    # Test disconnect functionality
    disconnect_btn = page.locator("#disconnect-sync")
    expect(disconnect_btn).to_be_visible()

    # Handle confirmation dialog
    page.once("dialog", lambda dialog: dialog.accept())
    disconnect_btn.click()

    # Wait for UI to update
    page.wait_for_timeout(500)

    # Verify token is cleared
    has_token_after = page.evaluate("() => localStorage.getItem('asthma-auth-token') !== null")
    assert has_token_after is False

    # Verify UI shows "Not configured" again
    expect(page.locator("#sync-status-text")).to_contain_text("Not configured")


def test_sync_token_flow_with_backend(page: Page, frontend_url: str, backend_url):
    """Test the complete sync setup flow: generate code, exchange for token."""
    # backend_url fixture ensures backend server is running
    backend_base_url, _ = backend_url

    # Override backendUrl in the frontend to point to test backend
    page.add_init_script(f"window.backendUrl = '{backend_base_url}';")

    page.goto(frontend_url)

    # Clear any existing token from localStorage
    page.evaluate("localStorage.removeItem('asthma-auth-token')")
    page.reload()

    # Initially not configured
    expect(page.locator("#sync-status-text")).to_contain_text("Not configured")

    # Step 1: Click "Generate Code" button in the UI
    generate_btn = page.locator("#generate-code")
    generate_btn.click()

    # Wait for code to be generated and displayed
    page.wait_for_timeout(2000)

    # Verify code is displayed
    code_display = page.locator("#generated-code")
    expect(code_display).to_be_visible()

    # Get the code from the display
    code = code_display.text_content()
    assert code is not None
    assert len(code.strip()) == 6

    # Step 2: Enter the code in the input field
    code_input = page.locator("#code-input")
    code_input.fill(code)

    # Step 3: Click "Complete Setup"
    complete_btn = page.locator("#complete-setup")
    complete_btn.click()

    # Wait for the API call to complete and UI to update
    page.wait_for_timeout(1000)

    # Step 4: Verify token is stored in localStorage
    token = page.evaluate("localStorage.getItem('asthma-auth-token')")
    assert token is not None
    assert len(token) > 0

    # Step 5: Verify UI shows "Connected"
    expect(page.locator("#sync-status-text")).to_contain_text("Connected")

    # Step 6: Verify status dot has connected class
    expect(page.locator(".status-dot")).to_have_class("status-dot connected")

    # Step 7: Verify sync setup section is hidden
    expect(page.locator("#sync-setup")).not_to_be_visible()

    # Step 8: Verify configured section is visible
    expect(page.locator("#sync-configured")).to_be_visible()

    # Step 9: Test disconnect functionality
    disconnect_btn = page.locator("#disconnect-sync")
    expect(disconnect_btn).to_be_visible()

    # Handle the confirmation dialog
    page.once("dialog", lambda dialog: dialog.accept())
    disconnect_btn.click()

    # Wait for UI to update
    page.wait_for_timeout(500)

    # Verify token is cleared
    token_after_disconnect = page.evaluate("localStorage.getItem('asthma-auth-token')")
    assert token_after_disconnect is None

    # Verify UI shows "Not configured" again
    expect(page.locator("#sync-status-text")).to_contain_text("Not configured")

    # Verify setup section is visible again
    expect(page.locator("#sync-setup")).to_be_visible()


def test_sync_token_persists_across_reload(page: Page, frontend_url: str, backend_url):
    """Test that stored token persists across page reload."""
    backend_base_url, _ = backend_url
    page.add_init_script(f"window.backendUrl = '{backend_base_url}';")
    page.goto(frontend_url)

    # Clear any existing token
    page.evaluate("localStorage.removeItem('asthma-auth-token')")
    page.reload()

    # Generate code via UI
    generate_btn = page.locator("#generate-code")
    generate_btn.click()

    # Wait for code to appear
    page.wait_for_timeout(1500)

    # Get the code
    code_display = page.locator("#generated-code")
    code = code_display.text_content()
    assert code is not None

    # Enter code
    code_input = page.locator("#code-input")
    code_input.fill(code)

    complete_btn = page.locator("#complete-setup")
    complete_btn.click()

    # Wait for setup to complete
    page.wait_for_timeout(1000)

    # Verify connected
    expect(page.locator("#sync-status-text")).to_contain_text("Connected")

    # Reload the page
    page.reload()

    # After reload, should still show connected
    expect(page.locator("#sync-status-text")).to_contain_text("Connected")
    expect(page.locator("#sync-configured")).to_be_visible()
    expect(page.locator("#sync-setup")).not_to_be_visible()


def test_sync_invalid_code_shows_error(page: Page, frontend_url: str, backend_url):
    """Test that entering an invalid code shows an error message."""
    backend_base_url, _ = backend_url
    page.add_init_script(f"window.backendUrl = '{backend_base_url}';")
    page.goto(frontend_url)

    # Clear any existing token
    page.evaluate("localStorage.removeItem('asthma-auth-token')")
    page.reload()

    # Enter invalid code (6 characters)
    code_input = page.locator("#code-input")
    code_input.fill("XXXXXX")

    # Click complete setup
    complete_btn = page.locator("#complete-setup")
    complete_btn.click()

    # Wait for API call to complete
    page.wait_for_timeout(1000)

    # Toast should show error
    toast = page.locator("#toast")
    expect(toast).to_have_class("show")
    expect(toast).to_contain_text("Invalid code")

    # Should still be not configured
    expect(page.locator("#sync-status-text")).to_contain_text("Not configured")


def test_sync_to_cloud_functionality(page: Page, frontend_url: str, backend_url):
    """Test syncing entries to the cloud."""
    backend_base_url, data_file = backend_url
    page.add_init_script(f"window.backendUrl = '{backend_base_url}';")
    page.goto(frontend_url)

    # Clear local storage
    page.evaluate("localStorage.clear()")
    page.reload()

    # Sync button should be hidden when not configured
    sync_btn = page.locator("#sync-to-cloud")
    expect(sync_btn).not_to_be_visible()

    # Set up sync
    generate_btn = page.locator("#generate-code")
    generate_btn.click()
    page.wait_for_timeout(2000)

    code_display = page.locator("#generated-code")
    expect(code_display).to_be_visible()
    code = code_display.text_content()
    assert code is not None

    code_input = page.locator("#code-input")
    code_input.fill(code)

    complete_btn = page.locator("#complete-setup")
    complete_btn.click()
    page.wait_for_timeout(2000)

    # Sync button should now be visible
    expect(sync_btn).to_be_visible()

    # Create some entries
    increment_btn = page.locator("#increment")
    save_btn = page.locator("#save")

    # Save entry 1
    increment_btn.click()
    increment_btn.click()
    save_btn.click()
    page.wait_for_timeout(500)

    # Change date and save entry 2
    page.evaluate("document.getElementById('usage-date').valueAsDate = new Date('2026-02-09')")
    page.locator("#increment").click()
    save_btn.click()
    page.wait_for_timeout(500)

    # Verify entries exist locally
    entries = page.locator(".entry")
    expect(entries).to_have_count(2)

    # Click sync button
    sync_btn.click()

    # Wait for toast to appear and verify it
    toast = page.locator("#toast")
    expect(toast).to_contain_text("Synced", timeout=5000)

    # Wait for sync to complete
    page.wait_for_timeout(2000)

    # Verify data was saved to backend
    from app.storage import load_data
    data = load_data(data_file)
    logs = data.get("logs", [])
    # Should have 2 entries synced
    assert len(logs) >= 2
