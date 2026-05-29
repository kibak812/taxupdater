import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Set

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


def _create_chrome_user_data_dir() -> Path:
    profile_root = PROJECT_ROOT / ".selenium-cache" / "chrome-user-data"
    profile_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="profile-", dir=profile_root))


def _chrome_code_sign_clone_dir() -> Optional[Path]:
    tmpdir = Path(os.environ.get("TMPDIR", tempfile.gettempdir())).resolve()
    if tmpdir.name != "T":
        return None
    return tmpdir.parent / "X" / "com.google.Chrome.code_sign_clone"


def _snapshot_chrome_code_sign_clones() -> Set[str]:
    clone_dir = _chrome_code_sign_clone_dir()
    if not clone_dir or not clone_dir.is_dir():
        return set()
    return {path.name for path in clone_dir.iterdir() if path.is_dir()}


def _cleanup_new_chrome_code_sign_clones(existing_clones: Set[str]) -> None:
    clone_dir = _chrome_code_sign_clone_dir()
    if not clone_dir or not clone_dir.is_dir():
        return

    for path in clone_dir.iterdir():
        if path.is_dir() and path.name not in existing_clones:
            shutil.rmtree(path, ignore_errors=True)

    try:
        next(clone_dir.iterdir())
    except StopIteration:
        clone_dir.rmdir()
    except OSError:
        pass


def _attach_chrome_cleanup(
    driver: webdriver.Chrome,
    user_data_dir: Optional[Path],
    code_sign_clones: Set[str],
) -> webdriver.Chrome:
    original_quit = driver.quit

    def quit_with_cleanup(*args, **kwargs):
        try:
            return original_quit(*args, **kwargs)
        finally:
            if user_data_dir:
                shutil.rmtree(user_data_dir, ignore_errors=True)
            _cleanup_new_chrome_code_sign_clones(code_sign_clones)

    driver.quit = quit_with_cleanup
    return driver


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

    user_data_dir = None
    if "--user-data-dir" not in configured:
        user_data_dir = _create_chrome_user_data_dir()
        options.add_argument(f"--user-data-dir={user_data_dir}")

    code_sign_clones = _snapshot_chrome_code_sign_clones()
    driver_path = _find_chromedriver()
    if not driver_path:
        if user_data_dir:
            shutil.rmtree(user_data_dir, ignore_errors=True)
        _cleanup_new_chrome_code_sign_clones(code_sign_clones)
        raise WebDriverException(
            "chromedriver를 찾을 수 없습니다. CHROMEDRIVER_PATH를 설정하거나 chromedriver를 PATH에 추가해주세요."
        )

    service = Service(executable_path=driver_path)
    try:
        driver = webdriver.Chrome(options=options, service=service)
    except Exception:
        if user_data_dir:
            shutil.rmtree(user_data_dir, ignore_errors=True)
        _cleanup_new_chrome_code_sign_clones(code_sign_clones)
        raise

    return _attach_chrome_cleanup(driver, user_data_dir, code_sign_clones)
