import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import dotenv_values


STORE_MAP = {
    "3231": "Prattville",
    "4445": "Eastern Blvd",
    "4456": "Oxford",
    "4463": "Decatur",
}


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


def pick_col(df, keywords):
    for col in df.columns:
        col_l = str(col).lower().strip()
        for key in keywords:
            if key in col_l:
                return col
    return None


def normalize_store_number(store):
    if pd.isna(store) or store is None:
        return None
    store = str(store).strip()
    if not store:
        return None
    match = re.search(r"(\d{3,4})", store)
    if not match:
        return store
    return str(int(match.group(1)))


def normalize_store_label(store_number):
    store_number = normalize_store_number(store_number)
    return f"{store_number} - {STORE_MAP.get(store_number, 'Unknown')}"


def extract_store_number(text):
    if pd.isna(text):
        return None
    text = str(text).strip()

    match = re.search(r"IHOP\s*#\s*(\d{3,4})\b", text, flags=re.IGNORECASE)
    if match:
        return normalize_store_number(match.group(1))

    match = re.match(r"^\s*(\d{3,4})\s*[-–:]", text)
    if match:
        return normalize_store_number(match.group(1))

    match = re.fullmatch(r"\s*(\d{3,4})(?:\.0)?\s*", text)
    if match:
        return normalize_store_number(match.group(1))

    match = re.search(r"(?:site|id site|store)\D{0,10}(\d{3,4})\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    return normalize_store_number(match.group(1))


def extract_store_from_filename(path: Path):
    return extract_store_number(path.name)


def is_support_staff(name):
    name = str(name or "").strip().lower()
    if not name:
        return False
    return "olo" in name or "online ordering" in name


def file_hash(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process_orders_file(path: Path):
    df = pd.read_csv(path)
    df.columns = df.columns.str.replace("\n", " ", regex=False).str.strip()
    df = df.rename(
        columns={
            "Device Orders Report": "Device Orders",
            "Staff Customer": "Server",
            "Base (Including Disc.)": "Base",
        }
    )

    col_store = pick_col(df, ["id site", "site", "store"])
    required = ["Device Orders", "Server", "Base"]
    missing = [col for col in required if col not in df.columns]
    if not col_store:
        missing.append("Site / ID Site")
    if missing:
        raise ValueError(f"{path.name}: missing required tray orders columns: {', '.join(missing)}")

    df["Device Orders"] = df["Device Orders"].astype(str).str.strip().str.lower()
    df["Device Orders"] = df["Device Orders"].replace(
        {
            "handheld": "handheld",
            "hand held": "handheld",
            "pos": "pos",
            "pos terminal": "pos",
        }
    )
    df["Device Orders"] = df["Device Orders"].str.extract(r"(handheld|pos)", expand=False).fillna("unknown")
    df["Base"] = pd.to_numeric(df["Base"], errors="coerce").fillna(0)
    df["Server"] = df["Server"].apply(clean_name)
    df["Server"] = df["Server"].fillna("").astype(str).str.strip()
    df = df[df["Server"] != ""].copy()
    df = df[~df["Server"].str.lower().str.contains("total", na=False)].copy()
    df["Store"] = df[col_store].apply(extract_store_number)
    fallback_store = extract_store_from_filename(path)
    if fallback_store:
        df["Store"] = df["Store"].fillna(fallback_store)
    df["Store"] = df["Store"].apply(normalize_store_number)
    df = df.dropna(subset=["Store"]).copy()
    return df[["Store", "Server", "Device Orders", "Base"]]


def aggregate_orders(files):
    all_rows = [process_orders_file(path) for path in files]
    if not all_rows:
        return pd.DataFrame(columns=["Store", "Server", "Tablet %", "Tablet Weight"])

    combined = pd.concat(all_rows, ignore_index=True)
    grouped = combined.groupby(["Store", "Server", "Device Orders"])["Base"].sum().unstack(fill_value=0)
    if "handheld" not in grouped.columns:
        grouped["handheld"] = 0
    if "pos" not in grouped.columns:
        grouped["pos"] = 0

    grouped = grouped.rename(columns={"handheld": "Tablet Sales", "pos": "POS Sales"})
    grouped["Tablet %"] = (grouped["Tablet Sales"] / (grouped["Tablet Sales"] + grouped["POS Sales"])).fillna(0)
    grouped["Tablet Weight"] = grouped["Tablet Sales"] + grouped["POS Sales"]
    return grouped.reset_index()[["Store", "Server", "Tablet %", "Tablet Weight"]]


def process_checks_file(path: Path):
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)

    df.columns = df.columns.str.strip()
    col_store = pick_col(df, ["id site", "site", "store"])
    col_open = pick_col(df, ["opened", "open", "order start", "start time", "opened at"])
    col_close = pick_col(df, ["closed", "close", "order end", "end time", "closed at"])
    col_service = pick_col(df, ["service", "service type", "order type"])
    col_server = pick_col(df, ["created by", "server", "server name", "employee", "cashier"])

    missing = []
    if not col_store:
        missing.append("Site / ID Site")
    if not col_open:
        missing.append("Opened")
    if not col_close:
        missing.append("Closed")
    if not col_service:
        missing.append("Service")
    if not col_server:
        missing.append("Server")
    if missing:
        raise ValueError(f"{path.name}: missing required tray checks columns: {', '.join(missing)}")

    df[col_open] = pd.to_datetime(df[col_open], errors="coerce")
    df[col_close] = pd.to_datetime(df[col_close], errors="coerce")
    eat = df[df[col_service].astype(str).str.contains("eat in", case=False, na=False)].copy()
    eat["Turn Time"] = (eat[col_close] - eat[col_open]).dt.total_seconds() / 60
    eat = eat.dropna(subset=["Turn Time"])
    eat = eat[eat["Turn Time"] >= 0]
    eat[col_server] = eat[col_server].fillna("(Unknown)").replace("", "(Unknown)")
    eat["Server"] = eat[col_server].apply(clean_name)
    eat["Server"] = eat["Server"].fillna("").astype(str).str.strip()
    eat = eat[eat["Server"] != ""].copy()
    eat = eat[~eat["Server"].str.lower().str.contains("total", na=False)].copy()
    eat["Store"] = eat[col_store].apply(extract_store_number)
    fallback_store = extract_store_from_filename(path)
    if fallback_store:
        eat["Store"] = eat["Store"].fillna(fallback_store)
    eat["Store"] = eat["Store"].apply(normalize_store_number)
    eat = eat.dropna(subset=["Store"]).copy()
    return eat[["Store", "Server", "Turn Time"]]


def aggregate_checks(files):
    all_rows = [process_checks_file(path) for path in files]
    if not all_rows:
        return pd.DataFrame(columns=["Store", "Server", "Turn Time", "Turn Check Count"])
    combined = pd.concat(all_rows, ignore_index=True)
    result = combined.groupby(["Store", "Server"], as_index=False).agg(
        **{
            "Turn Time": ("Turn Time", "mean"),
            "Turn Check Count": ("Turn Time", "size"),
        }
    )
    result["Turn Time"] = result["Turn Time"].round(2)
    return result


def insert_import_run(cur, business_date, report_type, files):
    metadata = {
        "script": "import_tray_daily_files.py",
        "files": [path.name for path in files],
        "hashes": {path.name: file_hash(path) for path in files},
    }
    cur.execute(
        """
        insert into public.foh_import_runs (
            business_date, source_system, report_type, source_filename, source_file_hash,
            status, metadata, started_at, completed_at
        )
        values (%s, 'tray', %s, %s, %s, 'processed', %s::jsonb, now(), now())
        returning id
        """,
        (
            business_date,
            report_type,
            files[0].name if files else None,
            file_hash(files[0]) if files else None,
            json.dumps(metadata),
        ),
    )
    return cur.fetchone()[0]


def upsert_rows(cur, rows, orders_run_id=None, checks_run_id=None):
    for row in rows:
        employee_name = str(row.get("employee_name") or "").strip()
        if not employee_name:
            continue
        cur.execute(
            """
            insert into public.foh_daily_metrics (
                business_date, store_number, store_label, employee_name, support_staff,
                tablet_pct, tablet_weight, turn_time, turn_check_count,
                tablet_import_run_id, turn_import_run_id, updated_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            on conflict (business_date, store_number, employee_name)
            do update set
                store_label = excluded.store_label,
                support_staff = excluded.support_staff,
                tablet_pct = coalesce(excluded.tablet_pct, public.foh_daily_metrics.tablet_pct),
                tablet_weight = coalesce(excluded.tablet_weight, public.foh_daily_metrics.tablet_weight),
                turn_time = coalesce(excluded.turn_time, public.foh_daily_metrics.turn_time),
                turn_check_count = coalesce(excluded.turn_check_count, public.foh_daily_metrics.turn_check_count),
                tablet_import_run_id = coalesce(excluded.tablet_import_run_id, public.foh_daily_metrics.tablet_import_run_id),
                turn_import_run_id = coalesce(excluded.turn_import_run_id, public.foh_daily_metrics.turn_import_run_id),
                updated_at = now()
            """,
            (
                row["business_date"],
                row["store_number"],
                row["store_label"],
                employee_name,
                row["support_staff"],
                row.get("tablet_pct"),
                row.get("tablet_weight"),
                row.get("turn_time"),
                row.get("turn_check_count"),
                orders_run_id,
                checks_run_id,
            ),
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--business-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--orders-file", action="append", default=[])
    parser.add_argument("--checks-file", action="append", default=[])
    parser.add_argument("--env-file", default=None)
    args = parser.parse_args()

    business_date = pd.to_datetime(args.business_date).date()
    order_paths = [Path(p) for p in args.orders_file]
    check_paths = [Path(p) for p in args.checks_file]

    orders_df = aggregate_orders(order_paths) if order_paths else pd.DataFrame(columns=["Store", "Server", "Tablet %", "Tablet Weight"])
    checks_df = aggregate_checks(check_paths) if check_paths else pd.DataFrame(columns=["Store", "Server", "Turn Time", "Turn Check Count"])

    merged = {}
    for _, row in orders_df.iterrows():
        key = (business_date, int(row["Store"]), row["Server"])
        merged[key] = {
            "business_date": business_date,
            "store_number": int(row["Store"]),
            "store_label": normalize_store_label(row["Store"]),
            "employee_name": row["Server"],
            "support_staff": is_support_staff(row["Server"]),
            "tablet_pct": None if pd.isna(row["Tablet %"]) else float(row["Tablet %"]),
            "tablet_weight": None if pd.isna(row["Tablet Weight"]) else float(row["Tablet Weight"]),
        }
    for _, row in checks_df.iterrows():
        key = (business_date, int(row["Store"]), row["Server"])
        existing = merged.get(
            key,
            {
                "business_date": business_date,
                "store_number": int(row["Store"]),
                "store_label": normalize_store_label(row["Store"]),
                "employee_name": row["Server"],
                "support_staff": is_support_staff(row["Server"]),
            },
        )
        existing.update(
            {
                "turn_time": None if pd.isna(row["Turn Time"]) else float(row["Turn Time"]),
                "turn_check_count": None if pd.isna(row["Turn Check Count"]) else int(row["Turn Check Count"]),
            }
        )
        merged[key] = existing

    file_cfg = dotenv_values(args.env_file) if args.env_file else {}
    cfg = {
        "DB_HOST": os.getenv("DB_HOST") or file_cfg.get("DB_HOST"),
        "DB_PORT": os.getenv("DB_PORT") or file_cfg.get("DB_PORT"),
        "DB_NAME": os.getenv("DB_NAME") or file_cfg.get("DB_NAME"),
        "DB_USER": os.getenv("DB_USER") or file_cfg.get("DB_USER"),
        "DB_PASSWORD": os.getenv("DB_PASSWORD") or file_cfg.get("DB_PASSWORD"),
    }
    conn = psycopg2.connect(
        host=cfg["DB_HOST"],
        port=cfg["DB_PORT"],
        dbname=cfg["DB_NAME"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        sslmode="require",
    )
    conn.autocommit = False
    cur = conn.cursor()
    try:
        orders_run_id = insert_import_run(cur, business_date, "tray_orders", order_paths) if order_paths else None
        checks_run_id = insert_import_run(cur, business_date, "tray_checks", check_paths) if check_paths else None
        upsert_rows(cur, merged.values(), orders_run_id=orders_run_id, checks_run_id=checks_run_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    print(f"Imported {len(merged)} Tray rows for {business_date}")


if __name__ == "__main__":
    main()
