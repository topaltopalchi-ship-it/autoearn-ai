import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


class PersianDashboardBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        env = os.environ.copy()
        env["AUTOEARN_DB"] = str(Path(cls.temp_dir.name) / "browser-test.db")
        cls.server = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "app.main:app",
                "--host", "127.0.0.1", "--port", str(cls.port),
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        deadline = time.time() + 20
        while time.time() < deadline:
            if cls.server.poll() is not None:
                raise RuntimeError("Dashboard test server exited before startup")
            try:
                with urlopen(cls.base_url + "/api/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("Dashboard test server did not become ready")

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
        if hasattr(cls, "playwright"):
            cls.playwright.stop()
        if hasattr(cls, "server"):
            cls.server.terminate()
            try:
                cls.server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.server.kill()
        cls.temp_dir.cleanup()

    def test_rtl_dashboard_on_desktop_and_mobile(self):
        page = self.browser.new_page(viewport={"width": 1365, "height": 900})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        response = page.goto(self.base_url, wait_until="networkidle")
        self.assertEqual(response.status, 200)
        self.assertEqual(page.locator("html").get_attribute("lang"), "fa")
        self.assertEqual(page.locator("html").get_attribute("dir"), "rtl")

        sidebar = page.locator(".sidebar")
        self.assertEqual(sidebar.evaluate("(el) => getComputedStyle(el).position"), "fixed")
        self.assertEqual(sidebar.evaluate("(el) => getComputedStyle(el).right"), "0px")
        self.assertEqual(
            page.locator("main").evaluate("(el) => getComputedStyle(el).marginRight"),
            "238px",
        )

        page.get_by_role("button", name="افزودن فرصت").click()
        self.assertTrue(page.locator("#opportunity-dialog").evaluate("(el) => el.open"))
        page.get_by_role("button", name="×").first.click()
        self.assertFalse(page.locator("#opportunity-dialog").evaluate("(el) => el.open"))

        page.set_viewport_size({"width": 390, "height": 844})
        self.assertEqual(sidebar.evaluate("(el) => getComputedStyle(el).position"), "static")
        self.assertEqual(
            page.locator("main").evaluate("(el) => getComputedStyle(el).marginRight"),
            "0px",
        )
        self.assertEqual(page.locator("html").evaluate("(el) => getComputedStyle(el).direction"), "rtl")
        self.assertEqual(page_errors, [])
        page.close()


if __name__ == "__main__":
    unittest.main()
