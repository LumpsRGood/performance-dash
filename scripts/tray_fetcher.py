import ctypes
import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values
from playwright.sync_api import Error as PlaywrightError, sync_playwright


ROOT = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = ROOT / ".env"
ORDERS_URL = "https://hq.dine.tray.com/tray/admin/reports?page=ordersListNew"
CHECKS_URL = "https://hq.dine.tray.com/tray/admin/reports?page=closeTabs"


def load_tray_credentials(env_file=DEFAULT_ENV_FILE):
    cfg = dotenv_values(env_file)
    username = os.getenv("TRAY_USERNAME") or cfg.get("TRAY_USERNAME")
    password = os.getenv("TRAY_PASSWORD") or cfg.get("TRAY_PASSWORD")
    if not username or not password:
        raise ValueError(f"Missing TRAY_USERNAME or TRAY_PASSWORD in {env_file}")
    return username, password


def ensure_playwright_chromium():
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Unable to install Playwright Chromium automatically. {detail}")


def ensure_linux_browser_libs():
    required_libs = [
        "libglib-2.0.so.0",
        "libgobject-2.0.so.0",
        "libnss3.so",
        "libnspr4.so",
    ]
    missing = []
    for lib_name in required_libs:
        try:
            ctypes.CDLL(lib_name)
        except OSError:
            missing.append(lib_name)
    if missing:
        raise RuntimeError(
            "Tray automation is not supported on this host because required browser libraries are missing: "
            + ", ".join(missing)
            + ". Rosnet refresh can run in-app, but Tray refresh needs a different host (or local run) with Chromium dependencies installed."
        )


def launch_browser_with_install(playwright, headless):
    ensure_linux_browser_libs()
    try:
        return playwright.chromium.launch(headless=headless)
    except PlaywrightError as exc:
        message = str(exc)
        if "Executable doesn't exist" not in message:
            raise
        ensure_playwright_chromium()
        return playwright.chromium.launch(headless=headless)


def _date_mmddyyyy(business_date):
    return business_date.strftime("%m/%d/%Y")


def _clear_and_fill(page, selector, value):
    locator = page.locator(selector).first
    locator.click()
    locator.fill("")
    locator.fill(value)


def _select_store(page, store_number):
    page.click("text=Sites :")
    page.click("div:has-text('Sites :') + div, button:has-text('Sites'), .sites-dropdown-selector")
    page.wait_for_timeout(1000)

    try:
        page.click(f"text=IHOP #{store_number}", timeout=2000)
    except Exception:
        search_boxes = page.locator(
            "input[type='text']:visible:not([id*='Date']):not([name*='date']):not([id*='ate']):not([id*='Check'])"
        )
        if search_boxes.count() > 0:
            search_boxes.first.fill(str(store_number))
        page.wait_for_timeout(1500)
        page.click(f"text=IHOP #{store_number}")

    page.keyboard.press("Escape")


def _select_visible_text(page, label_text, option_text):
    page.click(f"text={label_text}")
    page.click(f"div:has-text('{label_text}') + div, span:has-text('{label_text}') + div")
    page.wait_for_timeout(800)
    page.locator(f"text='{option_text}'").filter(visible=True).first.click()
    page.keyboard.press("Escape")


def _wait_for_csv_control(page, timeout=90000):
    candidates = [
        page.locator("text=CSV").filter(visible=True),
        page.locator("button:has-text('CSV')").filter(visible=True),
        page.locator("a:has-text('CSV')").filter(visible=True),
        page.locator("[title*='CSV']").filter(visible=True),
    ]
    last_error = None
    for locator in candidates:
        try:
            locator.first.wait_for(state="visible", timeout=timeout)
            return locator.first
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError("CSV export control did not appear")


def _run_report_and_download_csv(page, timeout=90000):
    page.click("text='Run Report'")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2500)
    csv_button = _wait_for_csv_control(page, timeout=timeout)
    with page.expect_download(timeout=timeout) as download_info:
        try:
            csv_button.click()
        except Exception:
            csv_button.evaluate("(node) => node.click()")
    return download_info.value


def _configure_checks_report(page, store_number, business_date):
    page.goto(CHECKS_URL, wait_until="networkidle")
    page.wait_for_selector("text='Run Report'", timeout=15000)
    date_text = _date_mmddyyyy(business_date)

    try:
        page.select_option("select[name*='period']", label="Today")
    except Exception:
        _select_visible_text(page, "Period :", "Today")

    _clear_and_fill(
        page,
        "input:visible[id*='Start'], input:visible[name*='start'], input:visible[placeholder*='Start']",
        date_text,
    )
    _clear_and_fill(
        page,
        "input:visible[id*='End'], input:visible[name*='end'], input:visible[placeholder*='End']",
        date_text,
    )

    _select_store(page, store_number)
    _select_visible_text(page, "Tender Type :", "Card")


def _configure_orders_report(page, store_number, business_date):
    page.goto(ORDERS_URL, wait_until="networkidle")
    page.wait_for_selector("text='Run Report'", timeout=15000)
    date_text = _date_mmddyyyy(business_date)
    _clear_and_fill(page, "#datepicker", date_text)
    _select_store(page, store_number)
    _select_visible_text(page, "Service :", "Eat In")


def fetch_tray_report(
    store_number,
    business_date,
    report_type,
    username=None,
    password=None,
    debug_visible=False,
    output_dir=None,
    env_file=DEFAULT_ENV_FILE,
):
    if username is None or password is None:
        username, password = load_tray_credentials(env_file)

    report_type = report_type.lower().strip()
    if report_type not in {"checks", "orders"}:
        raise ValueError("report_type must be 'checks' or 'orders'")

    output_dir = Path(output_dir or os.getcwd())
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = launch_browser_with_install(p, headless=not debug_visible)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            page.goto("https://hq.dine.tray.com", wait_until="networkidle")
            page.fill("input[type='email'], input[placeholder*='Email'], input#username", username)
            page.fill("input[type='password'], input[placeholder*='Password']", password)
            page.click(
                "button[type='submit'], input[type='submit'], button:has-text('Log In'), button:has-text('Sign In'), button:has-text('Login')"
            )
            page.wait_for_selector("text=Logout", timeout=20000)

            if report_type == "checks":
                _configure_checks_report(page, store_number, business_date)
            else:
                _configure_orders_report(page, store_number, business_date)

            try:
                download = _run_report_and_download_csv(page, timeout=90000)
            except Exception:
                page.wait_for_timeout(3000)
                page.reload(wait_until="networkidle")
                if report_type == "checks":
                    _configure_checks_report(page, store_number, business_date)
                else:
                    _configure_orders_report(page, store_number, business_date)
                download = _run_report_and_download_csv(page, timeout=90000)
            date_part = business_date.strftime("%Y%m%d")
            filename = f"tray_{report_type}_{store_number}_{date_part}.csv"
            save_path = output_dir / filename
            download.save_as(str(save_path))
            return save_path
        except Exception as exc:
            error_img = output_dir / f"debug_{report_type}_{store_number}.png"
            screenshot_note = ""
            try:
                page.screenshot(path=str(error_img), timeout=5000)
                screenshot_note = f" Debug screenshot saved to {error_img}."
            except Exception as screenshot_exc:
                screenshot_note = f" Debug screenshot failed: {screenshot_exc}"
            raise RuntimeError(
                f"Tray {report_type} fetch failed for store {store_number}: {exc}.{screenshot_note}"
            ) from exc
        finally:
            browser.close()
