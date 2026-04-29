import os
import tempfile
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from src.config.settings import SELENIUM_OPTIONS


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def create_chrome_driver() -> webdriver.Chrome:
    """Create a Chrome driver with writable cache/profile paths.

    Selenium Manager defaults to ~/.cache/selenium and Chrome defaults to a
    shared user profile. Both can fail in constrained runners, so keep runtime
    files inside the project unless the caller overrides them with env vars.
    """
    selenium_cache = Path(os.environ.get("SE_CACHE_PATH", PROJECT_ROOT / ".selenium-cache"))
    chrome_profiles = Path(os.environ.get("CHROME_PROFILE_ROOT", PROJECT_ROOT / ".chrome-profile"))
    selenium_cache.mkdir(parents=True, exist_ok=True)
    chrome_profiles.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("SE_CACHE_PATH", str(selenium_cache))
    os.environ.setdefault("XDG_CACHE_HOME", str(PROJECT_ROOT / ".cache"))

    options = Options()
    chrome_binary = os.environ.get("CHROME_BINARY_PATH")
    if chrome_binary:
        options.binary_location = chrome_binary

    configured = set()
    for option in SELENIUM_OPTIONS:
        options.add_argument(option)
        configured.add(option.split("=")[0])

    # Modern Chrome is happier with the new headless backend.
    if "--headless" in configured and "--headless=new" not in SELENIUM_OPTIONS:
        # Remove is not supported by Selenium Options, but Chrome accepts both
        # and the later flag wins.
        options.add_argument("--headless=new")

    for option in [
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--disable-background-networking",
        "--remote-debugging-port=0",
    ]:
        if option.split("=")[0] not in configured:
            options.add_argument(option)

    profile_dir = tempfile.mkdtemp(prefix="chrome-profile-", dir=str(chrome_profiles))
    options.add_argument(f"--user-data-dir={profile_dir}")

    driver_path = os.environ.get("CHROMEDRIVER_PATH")
    service = Service(executable_path=driver_path) if driver_path else Service()
    return webdriver.Chrome(options=options, service=service)
