"""Exercise the built Daymark app in Chromium with an isolated workspace."""

import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return server.getsockname()[1]


def wait_for_server(url, server):
    for _ in range(90):
        if server.poll() is not None:
            raise RuntimeError(f"Daymark server exited ({server.returncode})")
        try:
            if httpx.get(url, timeout=0.5, trust_env=False).is_success:
                return
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError("Daymark server did not start")


def exercise(browser, url):
    context = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True, color_scheme="light")
    page = context.new_page()
    page.set_default_timeout(9000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(url)
    expect(page.get_by_role("heading", name="Your day, at a glance.")).to_be_visible()
    page.get_by_role("button", name="Load sample data").click()
    expect(page.get_by_role("heading", name="Coming up")).to_be_visible()
    if screenshot := os.getenv("DAYMARK_SMOKE_SCREENSHOT"):
        page.screenshot(path=screenshot)

    page.get_by_role("link", name="Tasks", exact=True).click()
    page.get_by_role("button", name="New task", exact=True).click()
    page.get_by_label("Title", exact=True).fill("Browser smoke task")
    page.get_by_label("Repeat", exact=True).select_option("daily")
    page.get_by_role("button", name="Save", exact=True).click()
    page.get_by_role("button", name="Complete Browser smoke task").first.click()
    page.get_by_role("button", name="Completed", exact=True).click()
    expect(page.get_by_role("button", name="Reopen Browser smoke task")).to_be_visible()
    page.get_by_role("button", name="Search anything").click()
    page.get_by_placeholder("Search events, tasks, and subjects").fill("smoke task")
    page.locator("dialog").get_by_role("button", name="Browser smoke task").click()
    expect(page.get_by_role("heading", name="Task details")).to_be_visible()
    page.keyboard.press("Escape")

    page.get_by_role("button", name="Create", exact=True).click()
    page.get_by_role("button", name="Quick Add", exact=True).click()
    page.get_by_label("What do you need to do?").fill("Review transactions tomorrow for 30m p1")
    page.get_by_role("button", name="Review draft").click()
    expect(page.get_by_label("Title", exact=True)).to_have_value("Review transactions")
    expect(page.get_by_label("Estimate in minutes")).to_have_value("30")
    page.get_by_role("button", name="Save", exact=True).click()

    page.get_by_role("link", name="Calendar", exact=True).click()
    page.get_by_role("button", name="week", exact=True).click()
    expect(page.locator(".time-grid.week")).to_be_visible()
    page.get_by_role("button", name="day", exact=True).click()
    expect(page.get_by_role("heading", name="Day agenda")).to_be_visible()
    page.get_by_role("button", name="month", exact=True).click()
    page.locator(".date-cell").first.click()
    expect(page.locator(".time-grid.day")).to_be_visible()
    page.get_by_role("button", name="Filters").click()
    expect(page.get_by_text("Sources", exact=True)).to_be_visible()

    page.get_by_role("link", name="Study", exact=True).click()
    tomorrow = (datetime.now(ZoneInfo("Asia/Kolkata")).date() + timedelta(days=1)).isoformat()
    page.get_by_label("Planning date").fill(tomorrow)
    page.get_by_label("Review transactions").check()
    page.get_by_role("button", name="Preview study plan").click()
    expect(page.get_by_role("heading", name="Review your study plan")).to_be_visible()
    page.get_by_role("button", name="Confirm and add").click()
    expect(page.get_by_text("1 study blocks added.")).to_be_visible()

    page.get_by_role("button", name="Exam prep", exact=True).click()
    page.get_by_label("Topic 1", exact=True).fill("Indexing and joins")
    page.get_by_role("button", name="Preview revision plan").click()
    expect(page.get_by_role("heading", name="Review your study plan")).to_be_visible()
    page.get_by_role("button", name="Confirm and add").click()
    expect(page.get_by_text("2 study blocks added.")).to_be_visible()

    page.get_by_role("button", name="Attendance", exact=True).click()
    page.get_by_label("Subject", exact=True).select_option("CSE201")
    expect(page.get_by_text("87.5%", exact=True)).to_be_visible()
    page.get_by_role("button", name="Log attendance").click()
    page.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_text("88.9%", exact=True)).to_be_visible()

    page.get_by_role("link", name="Settings", exact=True).click()
    page.get_by_label("Color mode").select_option("dark")
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    expect(page.locator("html")).to_have_css("background-color", "rgb(21, 33, 31)")
    expect(page.get_by_role("heading", name="Settings")).to_have_css("font-family", 'Calibri, Carlito, "Segoe UI", system-ui, sans-serif')
    page.reload()
    expect(page.get_by_label("Color mode")).to_have_value("dark")
    if screenshot := os.getenv("DAYMARK_SMOKE_SCREENSHOT"):
        page.screenshot(path=str(Path(screenshot).with_name("daymark-dark.png")))
    page.get_by_label("Import as").select_option("camu")
    page.get_by_label("CSV or ICS file").set_input_files({"name": "timetable.csv", "mimeType": "text/csv",
        "buffer": b"kind,title,course\ntask,Review MyCamu export,CSE201\n"})
    page.get_by_role("button", name="Import file").click()
    expect(page.get_by_text("Processed 1 records from timetable.csv.")).to_be_visible()
    with page.expect_download() as work:
        page.get_by_role("link", name="Export CSV").click()
    assert work.value.suggested_filename == "daymark.csv"

    page.evaluate("navigator.serviceWorker.ready")
    page.wait_for_function("Boolean(navigator.serviceWorker.controller)")
    page.wait_for_function("""async () => {
      const cache = await caches.keys();
      const entries = await (await caches.open(cache.find(key => key.startsWith('daymark-shell-')))).keys();
      return entries.some(item => item.url.endsWith('.woff2')) &&
        !entries.some(item => item.url.includes('/api/'));
    }""")
    context.set_offline(True)
    page.reload()
    expect(page.get_by_text("Offline view", exact=False)).to_be_visible()
    expect(page.get_by_role("button", name="Save preferences")).to_be_disabled()
    context.set_offline(False)
    expect(page.get_by_text("Offline view", exact=False)).to_have_count(0)
    assert not errors, errors
    context.close()


def mobile(browser, url):
    phone = browser.new_context(viewport={"width": 360, "height": 800}, is_mobile=True,
                                device_scale_factor=2, has_touch=True, color_scheme="dark")
    page = phone.new_page()
    page.goto(url)
    expect(page.locator("html")).to_have_css("color-scheme", "dark")
    expect(page.get_by_role("heading", name="Your day, at a glance.")).to_be_visible()
    page.get_by_role("button", name="Open navigation").click()
    page.get_by_role("link", name="Calendar", exact=True).click()
    page.get_by_role("button", name="week", exact=True).click()
    expect(page.locator(".time-grid.week")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth") == 360
    page.get_by_role("button", name="Open navigation").click()
    page.get_by_role("link", name="Settings", exact=True).click()
    page.get_by_label("Color mode").select_option("light")
    expect(page.locator("html")).to_have_css("background-color", "rgb(246, 248, 245)")
    assert page.evaluate("document.documentElement.scrollWidth") == 360
    phone.close()


def main():
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        raise SystemExit("Build the frontend before running the browser smoke test.")
    port = free_port()
    url = f"http://localhost:{port}"
    with tempfile.TemporaryDirectory() as temp:
        env = {**os.environ, "DAYMARK_ORIGIN": url, "DAYMARK_DB": str(Path(temp) / "smoke.sqlite3"),
               "DAYMARK_PASSWORD": "", "DAYMARK_SYNC_SECONDS": "0", "DAYMARK_CAMU_FILE": "", "DAYMARK_BENNETT_ICS": ""}
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1",
                                   "--port", str(port), "--no-access-log"], cwd=ROOT, env=env)
        try:
            wait_for_server(url, server)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=os.getenv("DAYMARK_CHROMIUM"),
                                                     args=["--no-sandbox"])
                exercise(browser, url)
                mobile(browser, url)
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=8)
    print("Chromium desktop, mobile, and offline workflows passed.")


if __name__ == "__main__":
    main()
