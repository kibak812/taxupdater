import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Set

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from src.config.settings import SELENIUM_OPTIONS


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHROME_BINARY = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
VERSION_RE = re.compile(r"\b(\d+)\.\d+\.\d+\.\d+\b")


def _extract_major_version(version_output: str) -> Optional[int]:
    match = VERSION_RE.search(version_output)
    if not match:
        return None

    return int(match.group(1))


def _run_version_command(command: list[str]) -> Optional[str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    return f"{result.stdout}\n{result.stderr}".strip()


def _get_chrome_major_version(chrome_binary: Optional[str]) -> Optional[int]:
    if not chrome_binary:
        return None

    output = _run_version_command([chrome_binary, "--version"])
    if not output:
        return None

    return _extract_major_version(output)


def _get_chromedriver_major_version(driver_path: str) -> Optional[int]:
    output = _run_version_command([driver_path, "--version"])
    if not output:
        return None

    return _extract_major_version(output)


def _is_compatible_chromedriver(driver_path: str, chrome_major: Optional[int]) -> bool:
    if chrome_major is None:
        return True

    driver_major = _get_chromedriver_major_version(driver_path)
    if driver_major is None:
        return False

    return driver_major == chrome_major


def _find_chromedriver(chrome_major: Optional[int]) -> Optional[str]:
    """Prefer a compatible explicit/local driver; otherwise let Selenium Manager resolve it."""
    configured_path = os.environ.get("CHROMEDRIVER_PATH")
    if (
        configured_path
        and Path(configured_path).is_file()
        and _is_compatible_chromedriver(configured_path, chrome_major)
    ):
        return configured_path

    path_driver = shutil.which("chromedriver")
    if path_driver and _is_compatible_chromedriver(path_driver, chrome_major):
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

    sorted_candidates = sorted(
        executable_candidates,
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in sorted_candidates:
        if _is_compatible_chromedriver(str(candidate), chrome_major):
            return str(candidate)

    return None


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

    selected_chrome_binary = None
    chrome_binary = os.environ.get("CHROME_BINARY_PATH")
    if chrome_binary:
        options.binary_location = chrome_binary
        selected_chrome_binary = chrome_binary
    elif Path(DEFAULT_CHROME_BINARY).exists():
        options.binary_location = DEFAULT_CHROME_BINARY
        selected_chrome_binary = DEFAULT_CHROME_BINARY

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
    chrome_major = _get_chrome_major_version(selected_chrome_binary)
    driver_path = _find_chromedriver(chrome_major)

    try:
        if driver_path:
            service = Service(executable_path=driver_path)
            driver = webdriver.Chrome(options=options, service=service)
        else:
            driver = webdriver.Chrome(options=options)
    except Exception:
        if user_data_dir:
            shutil.rmtree(user_data_dir, ignore_errors=True)
        _cleanup_new_chrome_code_sign_clones(code_sign_clones)
        raise

    return _attach_chrome_cleanup(driver, user_data_dir, code_sign_clones)
