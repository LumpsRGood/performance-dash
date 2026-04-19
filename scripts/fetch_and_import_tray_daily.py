import argparse
import importlib.util
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import dotenv_values

from import_tray_daily_files import main as import_tray_main


def load_tray_api(tray_repo: Path):
    local_tray_api_path = Path(__file__).resolve().with_name("tray_fetcher.py")
    tray_api_path = tray_repo / "tray_api.py" if tray_repo else local_tray_api_path
    if not tray_api_path.exists():
        tray_api_path = local_tray_api_path
    spec = importlib.util.spec_from_file_location("tray_api", tray_api_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load tray_api from {tray_api_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_db_config(env_file=None):
    file_cfg = dotenv_values(env_file) if env_file else {}
    return {
        "DB_HOST": os.getenv("DB_HOST") or file_cfg.get("DB_HOST"),
        "DB_PORT": os.getenv("DB_PORT") or file_cfg.get("DB_PORT"),
        "DB_NAME": os.getenv("DB_NAME") or file_cfg.get("DB_NAME"),
        "DB_USER": os.getenv("DB_USER") or file_cfg.get("DB_USER"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD") or file_cfg.get("DB_PASSWORD"),
    }


def load_completed_tray_stores(business_date, stores, env_file=None):
    cfg = load_db_config(env_file)
    conn = psycopg2.connect(
        host=cfg["DB_HOST"],
        port=cfg["DB_PORT"],
        dbname=cfg["DB_NAME"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        sslmode="require",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    store_number::text,
                    count(*) filter (
                        where tablet_pct is not null and tablet_weight is not null and tablet_weight > 0
                    ) as tablet_rows,
                    count(*) filter (
                        where turn_time is not null and turn_check_count is not null and turn_check_count > 0
                    ) as turn_rows
                from public.foh_daily_metrics
                where business_date = %s
                  and store_number = any(%s::int[])
                group by store_number
                """,
                (business_date, [int(store) for store in stores]),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    completed = set()
    for store_number, tablet_rows, turn_rows in rows:
        if (tablet_rows or 0) > 0 and (turn_rows or 0) > 0:
            completed.add(str(store_number))
    return completed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--stores", default="3231,4445,4456,4463")
    parser.add_argument("--tray-repo", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--debug-visible", action="store_true")
    parser.add_argument("--tray-username", default=None)
    parser.add_argument("--tray-password", default=None)
    parser.add_argument("--tray-env-file", default=None)
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    tray_repo = Path(args.tray_repo) if args.tray_repo else None
    tray_api = load_tray_api(tray_repo)

    business_date = args.business_date
    stores = [s.strip() for s in args.stores.split(",") if s.strip()]
    if not args.force_refresh:
        completed_stores = load_completed_tray_stores(
            business_date,
            stores,
            env_file=args.tray_env_file,
        )
        if completed_stores:
            print(
                "Skipping stores with existing Tray data for "
                f"{business_date}: {', '.join(sorted(completed_stores))}"
            )
        stores = [store for store in stores if store not in completed_stores]

    if not stores:
        print(f"All requested stores already have Tray data for {business_date}. Nothing to fetch.")
        return

    output_dir = Path(args.output_dir or f"/tmp/performance-dash/downloads/tray/{business_date}")
    output_dir.mkdir(parents=True, exist_ok=True)

    order_files = []
    check_files = []
    for store in stores:
        print(f"Fetching Tray reports for {store}...")
        order_files.append(
            str(
                tray_api.fetch_tray_report(
                    store_number=store,
                    business_date=pd.to_datetime(business_date).date(),
                    report_type="orders",
                    username=args.tray_username,
                    password=args.tray_password,
                    debug_visible=args.debug_visible,
                    output_dir=output_dir,
                    env_file=args.tray_env_file,
                )
            )
        )
        check_files.append(
            str(
                tray_api.fetch_tray_report(
                    store_number=store,
                    business_date=pd.to_datetime(business_date).date(),
                    report_type="checks",
                    username=args.tray_username,
                    password=args.tray_password,
                    debug_visible=args.debug_visible,
                    output_dir=output_dir,
                    env_file=args.tray_env_file,
                )
            )
        )

    sys.argv = [
        "import_tray_daily_files.py",
        "--business-date",
        business_date,
        *sum([["--orders-file", path] for path in order_files], []),
        *sum([["--checks-file", path] for path in check_files], []),
    ]
    import_tray_main()


if __name__ == "__main__":
    main()
