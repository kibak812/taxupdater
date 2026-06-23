import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.crawlers import selenium_driver


class SeleniumDriverSelectionTests(unittest.TestCase):
    def test_extract_major_version_from_browser_and_driver_output(self):
        self.assertEqual(
            selenium_driver._extract_major_version("Google Chrome 149.0.7827.104"),
            149,
        )
        self.assertEqual(
            selenium_driver._extract_major_version("ChromeDriver 147.0.7727.117"),
            147,
        )
        self.assertIsNone(selenium_driver._extract_major_version("not a version"))

    def test_find_chromedriver_skips_incompatible_cache_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_root = root / ".selenium-cache" / "chromedriver" / "mac-arm64"
            stale_driver = cache_root / "147.0.7727.117" / "chromedriver"
            current_driver = cache_root / "149.0.7827.104" / "chromedriver"

            for driver in (stale_driver, current_driver):
                driver.parent.mkdir(parents=True, exist_ok=True)
                driver.write_text("", encoding="utf-8")
                driver.chmod(driver.stat().st_mode | stat.S_IXUSR)

            def fake_driver_major(driver_path):
                return 149 if "149.0.7827.104" in driver_path else 147

            with patch.dict(os.environ, {}, clear=True), patch(
                "src.crawlers.selenium_driver.PROJECT_ROOT",
                root,
            ), patch(
                "src.crawlers.selenium_driver.Path.home",
                return_value=root / "home",
            ), patch(
                "src.crawlers.selenium_driver.shutil.which",
                return_value=None,
            ), patch(
                "src.crawlers.selenium_driver._get_chromedriver_major_version",
                side_effect=fake_driver_major,
            ):
                self.assertEqual(
                    selenium_driver._find_chromedriver(149),
                    str(current_driver),
                )
                self.assertIsNone(selenium_driver._find_chromedriver(150))


if __name__ == "__main__":
    unittest.main()
