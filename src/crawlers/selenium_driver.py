import os
import shutil
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException

from src.config.settings import SELENIUM_OPTIONS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def _find_chromedriver() -> Optional[str]:
    """Prefer an explicit/local driver so Selenium Manager is not spawned on macOS."""
    configured_path = os.environ.get("CHROMEDRIVER_PATH")
    if configured_path and Path(configured_path).is_file():
        return configured_path

    path_driver = shutil.which("chromedriver")
    if path_driver:
        return path_driver

    candidates = []
    for cache_root in (
        PROJECT_ROOT / ".selenium-cache" / "chromedriver",
        Path.home() / ".cache" / "selenium" / "chromedriver",
    ):
        if cache_root.exists():
            candidates.extend(cache_root.glob("**/chromedriver"))

    executable_candidates = [path for path in candidates if path.is_file() and os.access(path, os.X_OK)]
    if not executable_candidates:
        return None

    return str(max(executable_candidates, key=lambda path: path.stat().st_mtime))


def create_chrome_driver() -> webdriver.Chrome:
    """Create a Chrome driver with stable macOS-friendly defaults."""
    options = Options()

    chrome_binary = os.environ.get("CHROME_BINARY_PATH")
    if chrome_binary:
        options.binary_location = chrome_binary
    elif Path(DEFAULT_CHROME_BINARY).exists():
        options.binary_location = DEFAULT_CHROME_BINARY

    configured = set()
    for option in SELENIUM_OPTIONS:
        if option == "--headless":
            options.add_argument("--headless=new")
            configured.add("--headless")
            configured.add("--headless=new")
        else:
            options.add_argument(option)
            configured.add(option.split("=")[0])

    for option in (
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--disable-background-networking",
        "--remote-debugging-pipe",
    ):
        if option.split("=")[0] not in configured:
            options.add_argument(option)

    driver_path = _find_chromedriver()
    if not driver_path:
        raise WebDriverException(
            "chromedriver를 찾을 수 없습니다. CHROMEDRIVER_PATH를 설정하거나 chromedriver를 PATH에 추가해주세요."
        )

    service = Service(executable_path=driver_path)
    return webdriver.Chrome(options=options, service=service)
