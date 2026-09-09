import base64
import os
import time
from pathlib import Path

import requests
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parent
DEFAULT_ENV_FILE = ROOT / ".env"
DEFAULT_COLLECTOR_URL = "https://app-attack-live-collector.onrender.com"


def load_tray_credentials(env_file=DEFAULT_ENV_FILE):
    cfg = dotenv_values(env_file) if env_file else {}
    username = os.getenv("TRAY_USERNAME") or cfg.get("TRAY_USERNAME")
    password = os.getenv("TRAY_PASSWORD") or cfg.get("TRAY_PASSWORD")
    if not username or not password:
        raise ValueError(f"Missing TRAY_USERNAME or TRAY_PASSWORD in {env_file}")
    return username, password


def _fetch_single_store(
    store,
    business_date,
    username,
    password,
    output_dir,
    collector_url,
    max_retries=2,
):
    """Fetch reports for a single store, retrying on transient 503/timeout errors."""
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"  -> Fetching store {store} (Attempt {attempt}/{max_retries})...")
            response = requests.post(
                f"{collector_url}/fetch-daily-reports",
                json={
                    "email": username,
                    "password": password,
                    "stores": [str(store)],
                    "businessDate": business_date.isoformat(),
                },
                timeout=120,
            )
        except requests.RequestException as exc:
            last_error = RuntimeError(f"Could not reach Tray collector for store {store}: {exc}")
            if attempt < max_retries:
                time.sleep(3)
                continue
            raise last_error from exc

        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            last_error = RuntimeError(
                f"Tray report service failed for store {store} ({response.status_code}): {detail}"
            )
            # If 503 or 504, wait briefly and retry
            if response.status_code in {502, 503, 504} and attempt < max_retries:
                print(f"     Transient {response.status_code} on store {store}, backing off 5s before retry...")
                time.sleep(5)
                continue
            raise last_error

        payload = response.json()
        saved = {"orders": [], "checks": []}
        for item in payload.get("files", []):
            report_type = item.get("reportType")
            if report_type not in saved:
                raise RuntimeError(f"Tray report service returned invalid report type: {report_type}")
            filename = Path(item["filename"]).name
            path = output_dir / filename
            try:
                path.write_bytes(base64.b64decode(item["contentBase64"], validate=True))
            except (KeyError, ValueError) as exc:
                raise RuntimeError(f"Tray report service returned invalid data for {filename}") from exc
            saved[report_type].append(path)

        if not saved["orders"] or not saved["checks"]:
            if attempt < max_retries:
                print(f"     Incomplete files for store {store}, retrying...")
                time.sleep(3)
                continue
            raise RuntimeError(f"Tray report service returned missing files for store {store}")

        return saved

    if last_error:
        raise last_error


def fetch_tray_reports(
    stores,
    business_date,
    username=None,
    password=None,
    output_dir=None,
    env_file=DEFAULT_ENV_FILE,
):
    """
    Fetches Tray reports for one or multiple stores.
    To avoid gateway proxy timeouts (e.g. Render's 100-second HTTP limit on high-volume days),
    multi-store requests are fetched store-by-store in sequential chunks with automatic retries.
    """
    if username is None or password is None:
        username, password = load_tray_credentials(env_file)

    output_dir = Path(output_dir or os.getcwd())
    output_dir.mkdir(parents=True, exist_ok=True)
    collector_url = os.getenv("TRAY_COLLECTOR_URL", DEFAULT_COLLECTOR_URL).rstrip("/")

    aggregated = {"orders": [], "checks": []}

    print(f"Starting sequential Tray fetch for {len(stores)} store(s) to guarantee zero gateway timeouts...")
    for idx, store in enumerate(stores, 1):
        print(f"[{idx}/{len(stores)}] Processing store {store} for {business_date}...")
        store_reports = _fetch_single_store(
            store=store,
            business_date=business_date,
            username=username,
            password=password,
            output_dir=output_dir,
            collector_url=collector_url,
        )
        aggregated["orders"].extend(store_reports["orders"])
        aggregated["checks"].extend(store_reports["checks"])

    expected = len(stores)
    if len(aggregated["orders"]) != expected or len(aggregated["checks"]) != expected:
        raise RuntimeError(
            "Tray report service returned an incomplete set of reports "
            f"({len(aggregated['orders'])} orders, {len(aggregated['checks'])} checks; expected {expected} each)."
        )
    return aggregated


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
