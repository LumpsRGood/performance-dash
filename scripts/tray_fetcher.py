import base64
import csv
import glob
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

import requests
from dotenv import dotenv_values

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = ROOT / ".env"
TRAY_HOME = "https://hq.dine.tray.com"
MENU_MIX_URL = f"{TRAY_HOME}/tray/admin/reports?page=menuMix"
LABOR_SUMMARY_URL = f"{TRAY_HOME}/tray/admin/reports?page=laborSummary"
ORDERS_URL = f"{TRAY_HOME}/tray/admin/reports?page=ordersListNew"
CHECKS_URL = f"{TRAY_HOME}/tray/admin/reports?page=closeTabs"


def load_tray_credentials(env_file=DEFAULT_ENV_FILE):
    cfg = dotenv_values(env_file) if env_file and Path(env_file).exists() else {}
    username = os.getenv("TRAY_USERNAME") or cfg.get("TRAY_USERNAME")
    password = os.getenv("TRAY_PASSWORD") or cfg.get("TRAY_PASSWORD")
    if not username or not password:
        raise ValueError(f"Missing TRAY_USERNAME or TRAY_PASSWORD in environment or {env_file}")
    return username, password


def chromium_executable() -> str | None:
    candidates = [
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("google-chrome"),
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        *glob.glob("/opt/render/.cache/ms-playwright/chromium-*/chrome-linux*/chrome"),
        *glob.glob("/opt/render/.cache/ms-playwright/chromium_headless_shell-*/chrome-linux*/headless_shell"),
        *glob.glob("/root/.cache/ms-playwright/chromium-*/chrome-linux*/chrome"),
        *glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")),
    ]
    return next((path for path in candidates if path and os.path.isfile(path)), None)


def ensure_chromium() -> None:
    if chromium_executable():
        return
    try:
        print("Installing Playwright Chromium browser binary...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    except Exception as exc:
        print(f"Notice: Playwright browser check/install: {exc}")


def visible(page, selector: str) -> bool:
    try:
        return page.locator(selector).first.is_visible(timeout=500)
    except Exception:
        return False


def login(page, email: str, password: str) -> None:
    print(f"Navigating to {TRAY_HOME}...")
    page.goto(TRAY_HOME, wait_until="networkidle")
    page.locator("input[type='email'], input[placeholder*='Email'], input#username").first.fill(email)
    page.locator("input[type='password'], input[placeholder*='Password']").first.fill(password)
    page.locator(
        "button[type='submit'], input[type='submit'], button:has-text('LOGIN'), button:has-text('Sign In')"
    ).first.click()
    page.wait_for_timeout(1200)
    page.wait_for_function(
        """() => !document.querySelector("input[type='password']") || location.pathname.includes('/tray/admin/')""",
        timeout=45000,
    )
    if visible(page, "text=Invalid") or visible(page, "text=incorrect"):
        raise ValueError("TRAY rejected the email or password.")
    print("Successfully logged into Tray.")


def select_store(page, store: str) -> str:
    sites_label = page.get_by_text("Sites :", exact=True).filter(visible=True).first
    sites_label.wait_for(state="visible", timeout=15000)
    sites_control = sites_label.locator("xpath=following-sibling::*[1]")
    sites_control.wait_for(state="visible", timeout=15000)
    sites_control.click()
    page.wait_for_timeout(1000)

    # TRAY keeps prior site selections when the report page is reused.
    # Clear every selected site so each report is strictly location-specific.
    checked_sites = page.locator("input[type='checkbox']:checked:visible")
    for index in range(checked_sites.count() - 1, -1, -1):
        checked_sites.nth(index).uncheck(force=True)
    page.wait_for_timeout(400)

    candidates = [str(store)]
    if len(str(store)) == 3:
        candidates.append(str(store).zfill(4))

    def find_exact_match():
        for candidate in candidates:
            matches = page.get_by_text(f"IHOP #{candidate}", exact=True).filter(visible=True)
            if matches.count() > 0:
                return candidate, matches
        return None, None

    resolved_store, matches = find_exact_match()
    if matches is None:
        search_boxes = page.locator(
            "input[type='text']:visible:not([id*='Date']):not([name*='date']):not([id*='ate']):not([id*='Check'])"
        )
        if search_boxes.count() > 0:
            for candidate in candidates:
                search_boxes.first.fill(candidate)
                page.wait_for_timeout(1000)
                resolved_store, matches = find_exact_match()
                if matches is not None:
                    break
        if matches is None:
            raise ValueError(f"IHOP #{store} is not available to this TRAY account.")

    matches.first.click()
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    return str(resolved_store)


def select_option_by_label(page, label_text: str, option_text: str) -> None:
    label = page.get_by_text(label_text, exact=True).filter(visible=True)
    if label.count() > 0:
        container = label.first.locator("xpath=following-sibling::*[1]")
        native = container.locator("select")
        if native.count() > 0 and native.first.is_visible():
            native.first.select_option(label=option_text)
            return
        container.click()
    else:
        page.get_by_text(label_text).filter(visible=True).first.click()
    page.get_by_text(option_text, exact=True).filter(visible=True).first.click()
    page.keyboard.press("Escape")


def clear_and_fill(page, selector: str, value: str) -> None:
    locator = page.locator(selector).first
    locator.click()
    locator.fill("")
    locator.fill(value)


def goto_report(page, url: str) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    page.locator("text='Run Report'").filter(visible=True).first.wait_for(
        state="visible", timeout=20000
    )


def wait_for_tray(page, timeout: int = 180000) -> None:
    busy_locators = [
        page.locator("text=/please wait/i"),
        page.locator("text=/loading/i"),
        page.locator(".blockUI:visible"),
        page.locator(".loading:visible"),
        page.locator(".spinner:visible"),
    ]
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        if not any(
            locator.count() > 0 and locator.first.is_visible()
            for locator in busy_locators
        ):
            return
        page.wait_for_timeout(1000)


def configure_daily_report(page, report_type: str, store: str, business_date) -> str:
    if hasattr(business_date, "strftime"):
        date_text = business_date.strftime("%m/%d/%Y")
    else:
        date_text = datetime.strptime(str(business_date)[:10], "%Y-%m-%d").strftime("%m/%d/%Y")

    if report_type == "checks":
        goto_report(page, CHECKS_URL)
        select_option_by_label(page, "Period :", "Today")
        clear_and_fill(
            page,
            "input:visible[id*='Start'], input:visible[name*='start'], input:visible[placeholder*='Start']",
            date_text,
        )
        clear_and_fill(
            page,
            "input:visible[id*='End'], input:visible[name*='end'], input:visible[placeholder*='End']",
            date_text,
        )
        resolved_store = select_store(page, store)
        select_option_by_label(page, "Tender Type :", "Card")
        return resolved_store

    goto_report(page, ORDERS_URL)
    clear_and_fill(page, "#datepicker", date_text)
    resolved_store = select_store(page, store)
    select_option_by_label(page, "Service :", "Eat In")
    return resolved_store


def orders_csv(page, timeout: int = 300000) -> bytes:
    page.locator("text='Run Report'").filter(visible=True).first.click()
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except Exception:
        pass
    page.wait_for_timeout(2500)
    wait_for_tray(page, timeout)
    page.wait_for_selector("#ordersReportTable tbody tr", timeout=timeout)
    rows = page.locator("#ordersReportTable tbody tr").evaluate_all(
        """(trs) => trs
            .map((tr) => Array.from(tr.querySelectorAll('td')).map((td) => td.innerText.replace(/\\s+/g, ' ').trim()))
            .filter((row) => row.length)"""
    )
    if not rows:
        raise ValueError("Orders report returned no rows.")
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "Time", "ID Site", "Service Destination", "Routing",
        "Device Orders Report", "Items", "Staff Customer",
        "Check ID Check Number", "Base (Including Disc.)", "Tax",
        "Fees", "Total (Excluding Tip)", "Print Status", "Action",
    ])
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def checks_csv(page, download_dir: str, store: str, timeout: int = 180000) -> bytes:
    page.locator("text='Run Report'").filter(visible=True).first.click()
    wait_for_tray(page, timeout)
    page.wait_for_function(
        """() => Array.from(document.querySelectorAll('span, a, button, [role="button"]')).some((node) => {
            const style = window.getComputedStyle(node);
            const rect = node.getBoundingClientRect();
            return node.textContent.trim() === 'CSV'
                && style.display !== 'none'
                && style.visibility !== 'hidden'
                && rect.width > 0
                && rect.height > 0;
        })""",
        timeout=timeout,
    )
    with page.expect_download(timeout=timeout) as info:
        page.evaluate(
            """() => {
                const nodes = Array.from(document.querySelectorAll('span, a, button, [role="button"]'));
                const node = nodes.find((candidate) => {
                    const style = window.getComputedStyle(candidate);
                    const rect = candidate.getBoundingClientRect();
                    return candidate.textContent.trim() === 'CSV'
                        && style.display !== 'none'
                        && style.visibility !== 'hidden'
                        && rect.width > 0
                        && rect.height > 0;
                });
                if (!node) throw new Error('CSV export control disappeared before it could be clicked.');
                (node.closest('a, button, [role="button"], [onclick]') || node).click();
            }"""
        )
    path = os.path.join(download_dir, f"checks-{store}.csv")
    info.value.save_as(path)
    with open(path, "rb") as handle:
        return handle.read()


def fetch_local_daily_reports(stores, business_date, username, password, output_dir):
    """
    Fetches daily Orders and Checks CSVs directly in-process via Playwright
    headless Chromium without requiring an external Render server.
    """
    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed. Add 'playwright' to requirements.txt.")

    ensure_chromium()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    clean_stores = list(dict.fromkeys("".join(ch for ch in str(store) if ch.isdigit()) for store in stores))
    clean_stores = [store for store in clean_stores if store]
    if not clean_stores:
        raise ValueError("No valid store numbers were supplied.")

    date_part = (
        business_date.strftime("%Y%m%d")
        if hasattr(business_date, "strftime")
        else str(business_date)[:10].replace("-", "")
    )

    saved = {"orders": [], "checks": []}
    with tempfile.TemporaryDirectory() as temp_dir:
        with sync_playwright() as playwright:
            executable = chromium_executable()
            launch_options = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-zygote",
                    "--js-flags=--max-old-space-size=192",
                ],
            }
            if executable:
                launch_options["executable_path"] = executable
            print(f"Launching Chromium browser (executable: {executable or 'playwright default'})...")
            browser = playwright.chromium.launch(**launch_options)
            context = browser.new_context(accept_downloads=True)
            # Memory and speed optimization: block images, media, and fonts
            context.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in ("image", "media", "font")
                else route.continue_(),
            )
            page = context.new_page()
            try:
                login(page, username, password)
                for idx, store in enumerate(clean_stores, 1):
                    print(f"[{idx}/{len(clean_stores)}] Fetching Tray reports for store #{store}...")
                    for report_type in ("orders", "checks"):
                        print(f"  -> Generating {report_type} for store #{store} ({business_date})...")
                        resolved_store = configure_daily_report(page, report_type, store, business_date)
                        if report_type == "orders":
                            content = orders_csv(page)
                        else:
                            content = checks_csv(page, temp_dir, resolved_store)

                        filename = f"tray_{report_type}_{resolved_store}_{date_part}.csv"
                        path = output_dir / filename
                        path.write_bytes(content)
                        saved[report_type].append(path)
                        print(f"  -> Saved {filename} ({len(content)} bytes)")
            finally:
                browser.close()
    return saved


def _wake_collector(collector_url):
    try:
        requests.get(f"{collector_url}/health", timeout=8)
    except Exception:
        pass


def _fetch_via_remote_collector(stores, business_date, username, password, output_dir, collector_url):
    """Fallback to remote collector if explicitly specified by TRAY_COLLECTOR_URL."""
    _wake_collector(collector_url)
    saved = {"orders": [], "checks": []}
    date_str = business_date.isoformat() if hasattr(business_date, "isoformat") else str(business_date)[:10]

    for store in stores:
        clean_store = "".join(ch for ch in str(store) if ch.isdigit())
        response = requests.post(
            f"{collector_url}/fetch-daily-reports",
            json={
                "email": username,
                "password": password,
                "stores": [clean_store],
                "businessDate": date_str,
            },
            timeout=180,
        )
        if not response.ok:
            raise RuntimeError(f"Remote collector error for store {store}: {response.text}")
        payload = response.json()
        for item in payload.get("files", []):
            report_type = item.get("reportType")
            if report_type in saved:
                path = output_dir / Path(item["filename"]).name
                path.write_bytes(base64.b64decode(item["contentBase64"], validate=True))
                saved[report_type].append(path)
    return saved


def fetch_tray_reports(
    stores,
    business_date,
    username=None,
    password=None,
    output_dir=None,
    env_file=DEFAULT_ENV_FILE,
):
    """
    Primary entry point: Fetches Tray reports for stores on business_date.
    Defaults to fast local headless browser (zero external hosting needed).
    """
    if username is None or password is None:
        username, password = load_tray_credentials(env_file)

    output_dir = Path(output_dir or os.getcwd())
    output_dir.mkdir(parents=True, exist_ok=True)

    collector_url = os.getenv("TRAY_COLLECTOR_URL")
    if collector_url and collector_url.strip().lower() not in {"local", "none", "false", ""}:
        try:
            print(f"Using configured remote collector URL: {collector_url}")
            return _fetch_via_remote_collector(
                stores=stores,
                business_date=business_date,
                username=username,
                password=password,
                output_dir=output_dir,
                collector_url=collector_url.rstrip("/"),
            )
        except Exception as exc:
            print(f"Remote collector failed ({exc}), running local headless browser...")

    print("Running in-process headless browser to fetch Tray reports directly...")
    return fetch_local_daily_reports(
        stores=stores,
        business_date=business_date,
        username=username,
        password=password,
        output_dir=output_dir,
    )


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
    del debug_visible
    report_type = report_type.lower().strip()
    if report_type not in {"checks", "orders"}:
        raise ValueError("report_type must be 'checks' or 'orders'")
    reports = fetch_tray_reports(
        stores=[store_number],
        business_date=business_date,
        username=username,
        password=password,
        output_dir=output_dir,
        env_file=env_file,
    )
    return reports[report_type][0]
