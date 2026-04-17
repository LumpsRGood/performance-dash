import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import dotenv_values, load_dotenv


STORE_MAP = {
    "3231": "Prattville",
    "4445": "Eastern Blvd",
    "4456": "Oxford",
    "4463": "Decatur",
}


def normalize_store_number(store):
    if pd.isna(store) or store is None:
        return None
    store = str(store).strip()
    if not store:
        return None
    match = __import__("re").search(r"(\d{3,4})", store)
    if not match:
        return store
    return str(int(match.group(1)))


def normalize_store_label(store_number):
    store_number = normalize_store_number(store_number)
    return f"{store_number} - {STORE_MAP.get(store_number, 'Unknown')}"


def clean_name(name):
    if pd.isna(name):
        return ""
    name = str(name).strip()
    if "," in name:
        parts = [part.strip() for part in name.split(",") if part.strip()]
        if len(parts) >= 2:
            name = " ".join(parts[1:] + [parts[0]])
    name = name.replace(",", " ")
    tokens = []
    for token in name.split():
        if not tokens or tokens[-1].lower() != token.lower():
            tokens.append(token)
    return " ".join(tokens).title()


def is_support_staff(name):
    name = str(name or "").strip().lower()
    if not name:
        return False
    return "olo" in name or "online ordering" in name


def stable_employee_id(store_id, business_date, server_name):
    raw = f"{int(store_id)}|{business_date}|{str(server_name).strip()}".encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def filter_to_true_dine_in(df):
    if df.empty:
        return df.copy()
    if "orderType" not in df.columns:
        return pd.DataFrame()
    order_type = df["orderType"].fillna("").astype(str).str.lower()
    return df[
        order_type.str.contains("dine")
        | order_type.str.contains("eat")
    ].copy()


def transform_checks(df, store_id, business_date):
    if df.empty:
        return pd.DataFrame()

    df = filter_to_true_dine_in(df)
    if df.empty:
        return pd.DataFrame()

    required = {
        "serverName",
        "checkNumber",
        "netSales",
        "beverageSales",
        "openTime",
        "closeTime",
        "guestCount",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required Rosnet columns: {sorted(missing)}")

    df = df.dropna(
        subset=[
            "serverName",
            "checkNumber",
            "netSales",
            "beverageSales",
            "guestCount",
        ]
    ).copy()

    if df.empty:
        return pd.DataFrame()

    df["serverName"] = df["serverName"].apply(clean_name)
    df = df[df["serverName"] != ""].copy()
    df["guestCount"] = pd.to_numeric(df["guestCount"], errors="coerce").fillna(0)
    df = df[df["guestCount"] > 0].copy()
    if df.empty:
        return pd.DataFrame()

    df["openTimeObj"] = pd.to_datetime(df["openTime"], format="%H:%M:%S", errors="coerce")
    df["closeTimeObj"] = pd.to_datetime(df["closeTime"], format="%H:%M:%S", errors="coerce")
    df["turn_time"] = (df["closeTimeObj"] - df["openTimeObj"]).dt.total_seconds() / 60
    df.loc[df["turn_time"] < 0, "turn_time"] += 24 * 60
    df["turn_time"] = df["turn_time"].apply(lambda x: x if pd.notna(x) and x > 0 else pd.NA)

    grouped = (
        df.groupby("serverName", dropna=False)
        .agg(
            net_sales=("netSales", "sum"),
            beverage_sales=("beverageSales", "sum"),
            turn_time=("turn_time", "mean"),
            turn_check_count=("checkNumber", "count"),
            ppa_weight=("guestCount", "sum"),
        )
        .reset_index()
    )

    grouped = grouped[grouped["ppa_weight"] > 0].copy()
    if grouped.empty:
        return pd.DataFrame()

    grouped["PPA"] = grouped["net_sales"] / grouped["ppa_weight"]
    grouped["Dine In Bev %"] = (grouped["beverage_sales"] / grouped["net_sales"]).fillna(0)
    grouped["Store"] = str(int(store_id))
    grouped["Server"] = grouped["serverName"].apply(clean_name)
    grouped["employee_source_id"] = grouped["Server"].apply(
        lambda name: stable_employee_id(store_id, business_date, name)
    )
    grouped["support_staff"] = grouped["Server"].apply(is_support_staff)
    return grouped[
        [
            "Store",
            "Server",
            "employee_source_id",
            "support_staff",
            "turn_time",
            "turn_check_count",
            "Dine In Bev %",
            "beverage_sales",
            "PPA",
            "ppa_weight",
            "net_sales",
        ]
    ]


def file_hash_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_conn(env_file):
    load_dotenv(env_file)
    cfg = dotenv_values(env_file)
    return psycopg2.connect(
        host=cfg["DB_HOST"],
        port=cfg.get("DB_PORT", 6543),
        dbname=cfg.get("DB_NAME", "postgres"),
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
    )


def load_rosnet_api_module(api_module_path, env_file):
    load_dotenv(env_file)
    spec = importlib.util.spec_from_file_location("rosnet_api", api_module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rosnet_api"] = module
    spec.loader.exec_module(module)
    return module


def insert_import_run(cur, business_date, report_type, store_ids):
    metadata = {
        "script": "fetch_and_import_rosnet_daily.py",
        "stores": [int(s) for s in store_ids],
    }
    cur.execute(
        """
        insert into public.foh_import_runs (
            business_date, source_system, report_type, source_filename, source_file_hash,
            status, metadata, started_at, completed_at
        )
        values (%s, 'rosnet', %s, %s, %s, 'processed', %s::jsonb, now(), now())
        returning id
        """,
        (
            business_date,
            report_type,
            f"rosnet_api_{business_date}.json",
            file_hash_text(json.dumps(metadata, sort_keys=True)),
            json.dumps(metadata),
        ),
    )
    return cur.fetchone()[0]


def upsert_rows(cur, business_date, rows, import_run_id):
    for row in rows:
        employee_name = str(row["Server"]).strip()
        if not employee_name:
            continue
        cur.execute(
            """
            insert into public.foh_daily_metrics (
                business_date, store_number, store_label, employee_name, employee_source_id, support_staff,
                turn_time, turn_check_count, dine_in_bev_pct, bev_weight, ppa, ppa_weight, net_sales,
                bev_import_run_id, ppa_import_run_id, updated_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            on conflict (business_date, store_number, employee_name)
            do update set
                store_label = excluded.store_label,
                employee_source_id = coalesce(excluded.employee_source_id, public.foh_daily_metrics.employee_source_id),
                support_staff = excluded.support_staff,
                turn_time = coalesce(excluded.turn_time, public.foh_daily_metrics.turn_time),
                turn_check_count = coalesce(excluded.turn_check_count, public.foh_daily_metrics.turn_check_count),
                dine_in_bev_pct = coalesce(excluded.dine_in_bev_pct, public.foh_daily_metrics.dine_in_bev_pct),
                bev_weight = coalesce(excluded.bev_weight, public.foh_daily_metrics.bev_weight),
                ppa = coalesce(excluded.ppa, public.foh_daily_metrics.ppa),
                ppa_weight = coalesce(excluded.ppa_weight, public.foh_daily_metrics.ppa_weight),
                net_sales = coalesce(excluded.net_sales, public.foh_daily_metrics.net_sales),
                bev_import_run_id = coalesce(excluded.bev_import_run_id, public.foh_daily_metrics.bev_import_run_id),
                ppa_import_run_id = coalesce(excluded.ppa_import_run_id, public.foh_daily_metrics.ppa_import_run_id),
                updated_at = now()
            """,
            (
                business_date,
                int(row["Store"]),
                normalize_store_label(row["Store"]),
                employee_name,
                row["employee_source_id"],
                row["support_staff"],
                None if pd.isna(row["turn_time"]) else float(row["turn_time"]),
                None if pd.isna(row["turn_check_count"]) else int(row["turn_check_count"]),
                None if pd.isna(row["Dine In Bev %"]) else float(row["Dine In Bev %"]),
                None if pd.isna(row["net_sales"]) else float(row["net_sales"]),
                None if pd.isna(row["PPA"]) else float(row["PPA"]),
                None if pd.isna(row["ppa_weight"]) else float(row["ppa_weight"]),
                None if pd.isna(row["net_sales"]) else float(row["net_sales"]),
                import_run_id,
                import_run_id,
            ),
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--stores", default="3231,4445,4456,4463")
    parser.add_argument("--env-file", default="/Users/chad/Documents/New project/.env")
    parser.add_argument("--api-module-path", default="/Users/chad/Documents/New project/api.py")
    args = parser.parse_args()

    business_date = pd.to_datetime(args.business_date).date()
    store_ids = [normalize_store_number(s) for s in args.stores.split(",") if str(s).strip()]

    rosnet_api = load_rosnet_api_module(args.api_module_path, args.env_file)
    bev_ids = rosnet_api.get_beverage_category_ids()
    conn = get_conn(args.env_file)
    all_rows = []

    try:
        for store_id in store_ids:
            print(f"Fetching Rosnet checks for {store_id} on {business_date}...")
            emp_map = rosnet_api.get_employees_map(int(store_id))
            checks = rosnet_api.get_checks(
                str(business_date),
                str(business_date),
                int(store_id),
                emp_map=emp_map,
                bev_cat_ids=bev_ids,
            )
            df = pd.DataFrame(checks)
            grouped = transform_checks(df, int(store_id), str(business_date))
            if grouped.empty:
                print(f"  no usable Rosnet rows for {store_id}")
                continue
            all_rows.extend(grouped.to_dict("records"))

        cur = conn.cursor()
        try:
            import_run_id = insert_import_run(cur, business_date, "rosnet_api_checks", store_ids)
            upsert_rows(cur, business_date, all_rows, import_run_id)
            conn.commit()
        finally:
            cur.close()
    finally:
        conn.close()

    print(f"Imported {len(all_rows)} Rosnet rows for {business_date}")


if __name__ == "__main__":
    main()
