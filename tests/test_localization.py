import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PersianDashboardTests(unittest.TestCase):
    def test_document_declares_persian_rtl(self):
        html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<html lang="fa" dir="rtl">', html)
        self.assertIn('/static/fa.js', html)

    def test_translation_layer_covers_dynamic_dashboard_states(self):
        translations = (ROOT / "static" / "fa.js").read_text(encoding="utf-8")
        for expected in (
            "در انتظار تأیید",
            "فرصت ذخیره شد",
            "پاداش ثبت شد",
            "نیازمند بررسی انسانی",
            "نتیجه‌ای پیدا نشد",
        ):
            self.assertIn(expected, translations)
        self.assertIn("MutationObserver", translations)
        self.assertLess(translations.index('["pending_approval"'), translations.index('["pending"'))
        self.assertLess(translations.index('["Opportunity saved"'), translations.index('["Opportunity"'))

    def test_rtl_styles_include_mobile_layout(self):
        css = (ROOT / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertIn('html[dir="rtl"] .sidebar', css)
        self.assertIn('html[dir="rtl"] main', css)
        self.assertIn("@media(max-width:850px)", css)

    def test_currency_uses_persian_locale(self):
        app = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('Intl.NumberFormat("fa-IR"', app)


if __name__ == "__main__":
    unittest.main()
