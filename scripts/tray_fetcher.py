import base64
import os
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


def fetch_tray_reports(
    stores,
    business_date,
    username=None,
    password=None,
    output_dir=None,
    env_file=DEFAULT_ENV_FILE,
):
    if username is None or password is None:
        username, password = load_tray_credentials(env_file)

    output_dir = Path(output_dir or os.getcwd())
    output_dir.mkdir(parents=True, exist_ok=True)
    collector_url = os.getenv("TRAY_COLLECTOR_URL", DEFAULT_COLLECTOR_URL).rstrip("/")

    try:
        response = requests.post(
            f"{collector_url}/fetch-daily-reports",
            json={
                "email": username,
                "password": password,
                "stores": [str(store) for store in stores],
                "businessDate": business_date.isoformat(),
            },
            timeout=600,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach the Tray report service: {exc}") from exc

    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(
            f"Tray report service failed ({response.status_code}): {detail}"
        )

    payload = response.json()
    saved = {"orders": [], "checks": []}
    for item in payload.get("files", []):
        report_type = item.get("reportType")
        if report_type not in saved:
            raise RuntimeError(f"Tray report service returned an invalid report type: {report_type}")
        filename = Path(item["filename"]).name
        path = output_dir / filename
        try:
            path.write_bytes(base64.b64decode(item["contentBase64"], validate=True))
        except (KeyError, ValueError) as exc:
            raise RuntimeError(f"Tray report service returned invalid data for {filename}") from exc
        saved[report_type].append(path)

    expected = len(stores)
    if len(saved["orders"]) != expected or len(saved["checks"]) != expected:
        raise RuntimeError(
            "Tray report service returned an incomplete set of reports "
            f"({len(saved['orders'])} orders, {len(saved['checks'])} checks; expected {expected} each)."
        )
    return saved


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
