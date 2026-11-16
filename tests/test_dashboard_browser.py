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
        env["AUTOEARN_MASTER_PASSWORD"] = "browser-test-password"
        env["AUTOEARN_AUTH_SECRET"] = "browser-test-auth-secret"
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

    def authenticated_page(self, **kwargs):
        page = self.browser.new_page(**kwargs)
        login = page.request.post(self.base_url + "/api/auth/login", data={"password": "browser-test-password"})
        if login.status != 200:
            raise AssertionError(f"Owner login failed: {login.status}")
        return page

    def test_rtl_dashboard_on_desktop_and_mobile(self):
        page = self.authenticated_page(viewport={"width": 1365, "height": 900})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        response = page.goto(self.base_url + "/", wait_until="networkidle")
        self.assertEqual(response.status, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertEqual(page.title(), "AutoEarn AI")
        self.assertEqual(page.locator("html").get_attribute("lang"), "fa")
        self.assertEqual(page.locator("html").get_attribute("dir"), "rtl")

        # Dynamic UI copy should be translated, while external/user text is preserved.
        page.evaluate("""() => {
          const root = document.createElement("div");
          root.id = "translation-smoke";
          const dynamic = document.createElement("p");
          dynamic.textContent = "Opportunity saved";
          const userText = document.createElement("span");
          userText.dataset.noTranslate = "";
          userText.textContent = "My Custom Platform";
          root.append(dynamic, userText);
          document.body.append(root);
        }""")
        page.wait_for_function(
            "() => document.querySelector('#translation-smoke p')?.textContent === 'فرصت ذخیره شد'"
        )
        self.assertEqual(page.locator("#translation-smoke span").text_content(), "My Custom Platform")

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

        # Exercise the human approval gate end to end: saving an opportunity
        # creates no task until the user explicitly starts one, and the task
        # remains pending until the separate approval confirmation.
        page.get_by_role("button", name="افزودن فرصت").click()
        page.locator('#opportunity-form input[name="title"]').fill("Browser Test Opportunity")
        page.locator('#opportunity-form input[name="platform"]').fill("Example Platform")
        page.locator('#opportunity-form input[name="url"]').fill("https://example.com")
        page.locator('#opportunity-form button[type="submit"]').click()
        page.wait_for_function(
            "() => document.querySelector('#opportunity-list')?.textContent.includes('Browser Test Opportunity')"
        )
        self.assertIn("هنوز کاری ثبت نشده است", page.locator("#task-list").text_content())

        page.once("dialog", lambda dialog: dialog.accept("Review the official platform terms"))
        page.locator("#opportunity-list [data-task]").first.click()
        page.wait_for_function(
            "() => document.querySelector('#task-list')?.textContent.includes('Review the official platform terms')"
        )
        self.assertIn("در انتظار تأیید", page.locator("#task-list").text_content())
        self.assertTrue(page.get_by_role("button", name="تأیید کار").is_visible())

        page.once("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="تأیید کار").click()
        page.wait_for_function(
            "() => document.querySelector('#task-list')?.textContent.includes('تأییدشده')"
        )
        self.assertNotIn("تأیید کار", page.locator("#task-list").text_content())
        self.assertEqual(page_errors, [])
        page.close()


    def test_discovery_results_render_as_unverified_leads(self):
        page = self.authenticated_page(viewport={"width": 390, "height": 844})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.route(
            "**/api/discover",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body='[{"id":7,"title":"Demo Survey Reward","url":"https://example.org/survey","snippet":"Official rules mention eligibility and payout terms","provider":"test-provider","domain":"example.org","category":"surveys","discovered_at":"2026-11-16T12:00:00+00:00","confidence":60,"signals":["https_transport","terms_or_rules_mentioned","reward_language_found"],"review_required":true,"verified":false}]',
            ),
        )
        page.goto(self.base_url + "/", wait_until="networkidle")
        page.locator("#discovery-query").fill("paid surveys in Europe")
        page.locator("#discovery-category").select_option("surveys")
        page.locator("#discovery-form button[type='submit']").click()
        page.wait_for_function(
            "() => document.querySelector('#discovery-results')?.textContent.includes('Demo Survey Reward')"
        )
        results = page.locator("#discovery-results")
        self.assertIn("example.org", results.text_content())
        self.assertIn("نیازمند بررسی انسانی", results.text_content())
        self.assertIn("تأییدنشده", results.text_content())
        self.assertEqual(
            results.locator("a").first.get_attribute("href"),
            "https://example.org/survey",
        )

        page.route("**/api/discoveries/7/review", lambda route: route.fulfill(
            status=200, content_type="application/json",
            body='{"id":7,"review_status":"accepted","promoted_opportunity_id":null,"verified":false}'
        ))
        page.route("**/api/discoveries/7/promote", lambda route: route.fulfill(
            status=200, content_type="application/json",
            body='{"opportunity":{"id":42,"title":"Demo Survey Reward"},"already_promoted":false,"already_exists":false}'
        ))
        results.get_by_role("button", name="تأیید برای بررسی").click()
        self.assertTrue(results.get_by_role("button", name="افزودن به فرصت‌های من").is_visible())
        page.once("dialog", lambda dialog: dialog.accept())
        results.get_by_role("button", name="افزودن به فرصت‌های من").click()
        page.wait_for_function(
            "() => document.querySelector('#discovery-results')?.textContent.includes('به فرصت‌های من افزوده شد')"
        )
        self.assertEqual(page_errors, [])
        page.close()

    def test_reward_ledger_can_record_and_display_paid_reward(self):
        page = self.authenticated_page(viewport={"width": 390, "height": 844})
        page.goto(self.base_url + "/", wait_until="networkidle")
        created = page.request.post(
            self.base_url + "/api/opportunities",
            data={
                "title": "Ledger Browser Opportunity",
                "platform": "Example Platform",
                "url": "https://ledger.example/reward",
                "reward_description": "Example payout",
            },
        )
        self.assertEqual(created.status, 201)
        page.reload(wait_until="networkidle")

        page.locator("#add-reward").click()
        page.locator("#reward-opportunity").select_option(str(created.json()["id"]))
        page.locator("#reward-form input[name='amount']").fill("4.5")
        page.locator("#reward-form input[name='currency']").fill("EUR")
        page.locator("#reward-form select[name='status']").select_option("paid")
        page.locator("#reward-form input[name='reference']").fill("browser-ledger-proof")
        page.locator("#reward-form button[type='submit']").click()

        page.wait_for_function(
            "() => document.querySelector('#reward-list')?.textContent.includes('browser-ledger-proof')"
        )
        self.assertIn("Ledger Browser Opportunity", page.locator("#reward-list").text_content())
        dashboard = page.request.get(self.base_url + "/api/dashboard").json()
        self.assertEqual(dashboard["paid_total"], 4.5)
        rewards = page.request.get(self.base_url + "/api/rewards").json()
        self.assertEqual(len(rewards), 1)
        self.assertEqual(rewards[0]["currency"], "EUR")
        self.assertEqual(rewards[0]["status"], "paid")
        self.assertEqual(rewards[0]["reference"], "browser-ledger-proof")
        page.close()


    def test_discovery_text_extraction_is_manual_and_shows_unverified_evidence(self):
        page = self.authenticated_page(viewport={"width": 390, "height": 844})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.route(
            "**/api/discover",
            lambda route: route.fulfill(
                status=200, content_type="application/json",
                body='[{"id":19,"title":"Manual terms review","url":"https://example.org/terms","snippet":"Review official terms","provider":"fixture","domain":"example.org","category":"surveys","confidence":70,"review_status":"pending","review_priority":{"review_priority_score":30},"verified":false}]',
            ),
        )
        page.route(
            "**/api/discoveries/19/extract",
            lambda route: route.fulfill(
                status=200, content_type="application/json",
                body='{"candidate_id":19,"extraction":{"reward_amounts":[{"currency":"EUR","amount_text":"15"}],"minimum_age_hints":[18],"eligibility_evidence":["Eligible residents of Germany."],"terms_mentioned":true,"verified":false,"disclaimer":"Extracted from supplied text only; unverified."},"review_priority":{"review_priority_score":65},"verified":false}',
            ),
        )
        page.goto(self.base_url + "/", wait_until="networkidle")
        page.locator("#discovery-query").fill("paid surveys")
        page.locator("#discovery-form button[type='submit']").click()
        page.wait_for_function(
            "() => document.querySelector('#discovery-results')?.textContent.includes('Manual terms review')"
        )
        page.once("dialog", lambda dialog: dialog.accept(
            "Terms and conditions. Eligible residents of Germany receive EUR 15. Minimum age 18."
        ))
        page.get_by_role("button", name="تحلیل متن شرایط").click()
        page.wait_for_function(
            "() => document.querySelector('#discovery-results')?.textContent.includes('EUR 15')"
        )
        result = page.locator("#discovery-results").text_content()
        self.assertIn("Eligible residents of Germany", result)
        self.assertIn("18", result)
        self.assertIn("تأییدنشده", result)
        self.assertEqual(page_errors, [])
        page.close()

    def test_risk_assessment_form_shows_explainable_high_and_low_results(self):
        page = self.authenticated_page(viewport={"width": 390, "height": 844})
        page_errors = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(self.base_url + "/", wait_until="networkidle")

        for name in (
            "upfront_payment",
            "deposit_or_top_up",
            "guaranteed_high_returns",
            "requests_sensitive_data_early",
        ):
            page.locator(f'#risk-form input[name="{name}"]').check()
        page.locator('#risk-form button[type="submit"]').click()
        page.wait_for_function(
            "() => document.querySelector('#risk-result')?.textContent.includes('80/100')"
        )
        high_result = page.locator("#risk-result").text_content()
        self.assertIn("ریسک بالا", high_result)
        self.assertIn("درخواست پرداخت هزینه اولیه", high_result)
        self.assertIn("الزام به واریز وجه یا شارژ حساب", high_result)
        self.assertIn("اعتبار پلتفرم را تأیید نمی‌کند", high_result)

        for checkbox in page.locator("#risk-form").locator('input[type="checkbox"]').all():
            checkbox.uncheck()
        page.locator('#risk-form button[type="submit"]').click()
        page.wait_for_function(
            "() => document.querySelector('#risk-result')?.textContent.includes('0/100')"
        )
        low_result = page.locator("#risk-result").text_content()
        self.assertIn("ریسک پایین", low_result)
        self.assertIn("امتیاز پایین، معتبر بودن یا بی‌خطر بودن پلتفرم را ثابت نمی‌کند", low_result)
        self.assertEqual(page_errors, [])
        page.close()


if __name__ == "__main__":
    unittest.main()
