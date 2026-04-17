import argparse
import hashlib
import json
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
STORE_ALIASES = {
    "prattville": "3231",
    "eastern blvd": "4445",
    "montgomery": "4445",
    "oxford": "4456",
    "decatur": "4463",
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


def normalize_store_label(label):
    return re.sub(r"\s+", " ", str(label).strip())


def extract_store_label_from_text(text):
    text = str(text).strip()
    match = re.match(r"^\s*(?:IHOP\s*#\s*)?(\d{3,4})\b\s*[-–:]?\s*(.+)", text, flags=re.IGNORECASE)
    if match:
        store_num = normalize_store_number(match.group(1))
        remainder = match.group(2).strip()
        if remainder and "copyright" not in remainder.lower():
            return store_num, normalize_store_label(f"{store_num} - {remainder}")
    return None, None


def resolve_store_from_text(text):
    store_num, label = extract_store_label_from_text(text)
    if store_num:
        return store_num, label

    normalized = normalize_store_label(text).lower()
    if normalized in STORE_ALIASES:
        store_num = STORE_ALIASES[normalized]
        return store_num, f"{store_num} - {STORE_MAP.get(store_num, 'Unknown')}"

    match = re.search(r"(?:location|site|store)\D{0,10}(\d{3,4})\b", str(text), flags=re.IGNORECASE)
    if match:
        store_num = normalize_store_number(match.group(1))
        return store_num, f"{store_num} - {STORE_MAP.get(store_num, 'Unknown')}"
    return None, None


def workbook_date(path: Path):
    first = pd.read_excel(path, header=None, nrows=1).iloc[0, 0]
    match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", str(first))
    if not match:
        raise ValueError(f"Could not find business date in A1 of {path.name}")
    return pd.to_datetime(match.group(1)).date()


def read_excel_with_header_search(path: Path, required_terms, default_header=4, max_header_row=10):
    raw = pd.read_excel(path, header=None)
    for header_idx in range(min(max_header_row, len(raw))):
        row_values = [str(v).strip().lower() for v in raw.iloc[header_idx].tolist()]
        if all(any(term in cell for cell in row_values) for term in required_terms):
            columns = raw.iloc[header_idx].tolist()
            data = raw.iloc[header_idx + 1 :].copy()
            data.columns = columns
            return data.dropna(how="all")
    return pd.read_excel(path, header=default_header)


def parse_ppa(path: Path):
    business_date = workbook_date(path)
    df = read_excel_with_header_search(
        path,
        required_terms=["location", "employee name", "net sales", "covers", "ppa"],
        default_header=4,
    )
    df.columns = [str(c).strip() for c in df.columns]
    col_store = pick_col(df, ["location"])
    col_server = pick_col(df, ["employee name", "employee"])
    col_net_sales = pick_col(df, ["net sales"])
    col_covers = pick_col(df, ["covers"])
    col_ppa = pick_col(df, ["ppa"])
    if not all([col_store, col_server, col_net_sales, col_covers, col_ppa]):
        raise ValueError(f"{path.name}: missing required PPA columns")

    records = []
    for _, row in df.iterrows():
        store_number, store_label = resolve_store_from_text(row[col_store])
        if store_number not in STORE_MAP:
            continue
        server = clean_name(row[col_server])
        if not server or "total" in server.lower():
            continue
        net_sales = pd.to_numeric(row[col_net_sales], errors="coerce")
        ppa_weight = pd.to_numeric(row[col_covers], errors="coerce")
        ppa = pd.to_numeric(row[col_ppa], errors="coerce")
        if pd.isna(ppa):
            continue
        records.append(
            {
                "business_date": business_date,
                "store_number": int(store_number),
                "store_label": store_label or f"{store_number} - {STORE_MAP.get(store_number, 'Unknown')}",
                "employee_name": server,
                "support_staff": "olo" in server.lower() or "online ordering" in server.lower(),
                "ppa": None if pd.isna(ppa) else float(ppa),
                "ppa_weight": None if pd.isna(ppa_weight) else float(ppa_weight),
                "net_sales": None if pd.isna(net_sales) else float(net_sales),
            }
        )
    return business_date, records


def parse_bev(path: Path):
    business_date = workbook_date(path)
    df = read_excel_with_header_search(
        path,
        required_terms=["location", "employee", "% of net sales"],
        default_header=4,
    )
    df.columns = [str(c).strip() for c in df.columns]
    col_store = pick_col(df, ["location"])
    col_server = pick_col(df, ["employee"])
    col_bev = pick_col(df, ["% of net sales"])
    col_net_sales = pick_col(df, ["net sales"])
    if not all([col_store, col_server, col_bev]):
        raise ValueError(f"{path.name}: missing required beverage columns")

    records = []
    for _, row in df.iterrows():
        store_number, store_label = resolve_store_from_text(row[col_store])
        if store_number not in STORE_MAP:
            continue
        server = clean_name(row[col_server])
        if not server or "total" in server.lower():
            continue
        bev = pd.to_numeric(row[col_bev], errors="coerce")
        bev_weight = pd.to_numeric(row[col_net_sales], errors="coerce") if col_net_sales else pd.NA
        if pd.isna(bev):
            continue
        if bev > 1:
            bev = bev / 100
        records.append(
            {
                "business_date": business_date,
                "store_number": int(store_number),
                "store_label": store_label or f"{store_number} - {STORE_MAP.get(store_number, 'Unknown')}",
                "employee_name": server,
                "support_staff": "olo" in server.lower() or "online ordering" in server.lower(),
                "dine_in_bev_pct": None if pd.isna(bev) else float(bev),
                "bev_weight": None if pd.isna(bev_weight) else float(bev_weight),
            }
        )
    return business_date, records


def file_hash(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def insert_import_run(cur, business_date, report_type, source_file):
    metadata = {"script": "import_rosnet_daily_workbooks.py"}
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
            source_file.name,
            file_hash(source_file),
            json.dumps(metadata),
        ),
    )
    return cur.fetchone()[0]


def upsert_rows(cur, rows, ppa_run_id=None, bev_run_id=None):
    for row in rows:
        cur.execute(
            """
            insert into public.foh_daily_metrics (
                business_date, store_number, store_label, employee_name, support_staff,
                dine_in_bev_pct, bev_weight, ppa, ppa_weight, net_sales,
                bev_import_run_id, ppa_import_run_id, updated_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            on conflict (business_date, store_number, employee_name)
            do update set
                store_label = excluded.store_label,
                support_staff = excluded.support_staff,
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
                row["business_date"],
                row["store_number"],
                row["store_label"],
                row["employee_name"],
                row["support_staff"],
                row.get("dine_in_bev_pct"),
                row.get("bev_weight"),
                row.get("ppa"),
                row.get("ppa_weight"),
                row.get("net_sales"),
                bev_run_id,
                ppa_run_id,
            ),
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ppa-file", required=True)
    parser.add_argument("--bev-file", required=True)
    parser.add_argument("--env-file", default="/Users/chad/Documents/New project/.env")
    args = parser.parse_args()

    ppa_path = Path(args.ppa_file)
    bev_path = Path(args.bev_file)

    ppa_date, ppa_rows = parse_ppa(ppa_path)
    bev_date, bev_rows = parse_bev(bev_path)
    if ppa_date != bev_date:
        raise ValueError(f"Date mismatch: PPA={ppa_date}, Bev={bev_date}")

    merged = {}
    for row in ppa_rows:
        merged[(row["business_date"], row["store_number"], row["employee_name"])] = row
    for row in bev_rows:
        key = (row["business_date"], row["store_number"], row["employee_name"])
        if key in merged:
            merged[key].update(row)
        else:
            merged[key] = row

    cfg = dotenv_values(args.env_file)
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
        ppa_run_id = insert_import_run(cur, ppa_date, "employee_sales_statistics", ppa_path)
        bev_run_id = insert_import_run(cur, bev_date, "employee_contest_detail", bev_path)
        upsert_rows(cur, list(merged.values()), ppa_run_id=ppa_run_id, bev_run_id=bev_run_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    print(f"Imported {len(merged)} rows for {ppa_date}")


if __name__ == "__main__":
    main()
