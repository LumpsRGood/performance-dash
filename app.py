import re
import textwrap
from io import BytesIO

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

st.set_page_config(page_title="FOH Performance Dashboard", layout="wide")

st.title("FOH Performance Dashboard")
st.caption("Upload your source reports below to build the combined store dashboards.")

# =========================
# Preferred Store Mapping
# =========================
STORE_MAP = {
    "3231": "Prattville",
    "4445": "Montgomery",
    "4456": "Oxford",
    "4463": "Decatur",
}

# Dynamic labels pulled from Rosnet beverage file
DYNAMIC_STORE_LABELS = {}

# =========================
# Upload Section
# =========================
tablet_files = st.file_uploader(
    "Upload Tray Orders CSV(s)",
    type=["csv"],
    accept_multiple_files=True,
)
st.caption("Use the Tray Orders export that includes handheld and POS order activity.")

turn_files = st.file_uploader(
    "Upload Tray Checks CSV(s)",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=True,
)
st.caption("Use the Tray Checks export to calculate Eat-In turn times.")

beverage_files = st.file_uploader(
    "Upload Rosnet Contest Detail XLSX",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True,
)
st.caption("Use the Rosnet Contest Detail export for Dine-In Beverage % by employee.")

ppa_files = st.file_uploader(
    "Upload Employee Sales Statistics XLSX",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True,
)
st.caption("Use the Employee Sales Statistics export for employee-level PPA.")

# =========================
# Helpers
# =========================
def clean_name(name):
    if pd.isna(name):
        return ""
    name = str(name).strip()
    if "," in name:
        parts = name.split(",", 1)
        name = f"{parts[1].strip()} {parts[0].strip()}"
    return " ".join(name.split()).title()


def is_support_staff(name):
    name = str(name or "").strip().lower()
    if not name:
        return False
    return "olo" in name or "online ordering" in name


def strip_employee_id(name):
    if pd.isna(name):
        return ""
    name = str(name).strip()
    name = re.sub(r"^\d+\s*-\s*", "", name)
    return name


def pick_col(df, keywords):
    for col in df.columns:
        col_l = str(col).lower().strip()
        for key in keywords:
            if key in col_l:
                return col
    return None


def read_excel_with_header_search(file, required_terms, default_header=4, max_header_row=10):
    file.seek(0)
    raw = pd.read_excel(file, header=None)

    for header_idx in range(min(max_header_row, len(raw))):
        row_values = [str(v).strip() for v in raw.iloc[header_idx].tolist()]
        normalized = [v.lower() for v in row_values]
        if all(any(term in cell for cell in normalized) for term in required_terms):
            columns = raw.iloc[header_idx].tolist()
            data = raw.iloc[header_idx + 1 :].copy()
            data.columns = columns
            data = data.dropna(how="all")
            return data

    file.seek(0)
    return pd.read_excel(file, header=default_header)


def normalize_store_label(label):
    label = str(label).strip()
    label = re.sub(r"\s+", " ", label)
    return label


def normalize_store_number(store):
    if pd.isna(store) or store is None:
        return None

    store = str(store).strip()
    if store == "":
        return None

    match = re.search(r"(\d{3,4})", store)
    if not match:
        return store

    return str(int(match.group(1)))


def extract_store_number(text):
    if pd.isna(text):
        return None

    text = str(text).strip()

    # 1. Best match: IHOP #560 or IHOP #3231
    match = re.search(r'IHOP\s*#\s*(\d{3,4})\b', text, flags=re.IGNORECASE)
    if match:
        return normalize_store_number(match.group(1))

    # 2. Leading store label like "491 - Lanada Road" or "5656 - Mebane TC"
    match = re.match(r'^\s*(\d{3,4})\s*[-–:]', text)
    if match:
        return normalize_store_number(match.group(1))

    # 3. Exact cell value is just a 3- or 4-digit store number
    match = re.fullmatch(r'\s*(\d{3,4})(?:\.0)?\s*', text)
    if match:
        return normalize_store_number(match.group(1))

    # 4. Site / Store labels like "Site 560" or "Store: 3231"
    match = re.search(r'(?:site|id site|store)\D{0,10}(\d{3,4})\b', text, flags=re.IGNORECASE)
    if match:
        return normalize_store_number(match.group(1))

    return None


def resolve_store_from_text(text):
    store_num = extract_store_number(text)
    if store_num:
        return store_num

    label = normalize_store_label(str(text)).lower()
    if not label:
        return None

    for store_num, store_label in DYNAMIC_STORE_LABELS.items():
        stripped = re.sub(r"^\d{3,4}\s*[-–:]\s*", "", store_label).strip().lower()
        if label == stripped:
            return normalize_store_number(store_num)

    aliases = {
        "prattville": "3231",
        "3231- prattville": "3231",
        "eastern blvd": "4445",
        "montgomery": "4445",
        "oxford": "4456",
        "decatur": "4463",
    }
    return aliases.get(label)


def extract_store_label_from_text(text):
    text = str(text).strip()

    # Accept:
    # 491 - Lanada Road
    # 5656 - Mebane TC
    # IHOP #491 Lanada Road
    # IHOP #5656 Mebane TC
    match = re.match(r'^\s*(?:IHOP\s*#\s*)?(\d{3,4})\b\s*[-–:]?\s*(.+)', text, flags=re.IGNORECASE)
    if match:
        store_num = normalize_store_number(match.group(1))
        remainder = match.group(2).strip()

        if remainder and "copyright" not in remainder.lower():
            return store_num, normalize_store_label(f"{store_num} - {remainder}")

    return None, None


def register_store_label(store_num, label):
    store_num = normalize_store_number(store_num)
    if store_num and label:
        DYNAMIC_STORE_LABELS[store_num] = normalize_store_label(label)


def get_store_label(store_num):
    store_num = normalize_store_number(store_num)

    if not store_num or store_num == "Unknown":
        return "Unknown"

    if store_num in DYNAMIC_STORE_LABELS:
        return DYNAMIC_STORE_LABELS[store_num]

    if store_num in STORE_MAP:
        return f"{store_num} - {STORE_MAP[store_num]}"

    return f"{store_num} - Unknown"


def extract_store_from_filename(file):
    return extract_store_number(file.name)


def safe_mean(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return pd.NA
    return s.mean()


def weighted_mean(df, value_col, weight_col, default=pd.NA):
    if value_col not in df.columns or weight_col not in df.columns:
        return default

    working = df[[value_col, weight_col]].copy()
    working[value_col] = pd.to_numeric(working[value_col], errors="coerce")
    working[weight_col] = pd.to_numeric(working[weight_col], errors="coerce")
    working = working.dropna(subset=[value_col, weight_col])
    working = working[working[weight_col] > 0]

    if working.empty:
        return default

    return (working[value_col] * working[weight_col]).sum() / working[weight_col].sum()


def format_single_rank_line(df, column, label, ascending=False):
    working = df[["Server", column]].copy()
    working[column] = pd.to_numeric(working[column], errors="coerce")
    working = working.dropna(subset=[column])

    if working.empty:
        return f"**{label}:** No data"

    best_value = working[column].min() if ascending else working[column].max()
    tied = working[working[column] == best_value].sort_values("Server")

    people = " • ".join(tied["Server"].tolist())
    return f"**{label}:** {people}"


def get_rank_names(df, column, ascending=False):
    working = df[["Server", column]].copy()
    working[column] = pd.to_numeric(working[column], errors="coerce")
    working = working.dropna(subset=[column])

    if working.empty:
        return "No data"

    best_value = working[column].min() if ascending else working[column].max()
    tied = working[working[column] == best_value].sort_values("Server")

    return " • ".join(tied["Server"].tolist())


def wrap_names(text, width=18):
    if not text or text == "No data":
        return text
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False))


def fig_to_png_bytes(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    plt.close(fig)
    return buf


# =========================
# Tablet Processing
# =========================
def process_tablet_file(file):
    file.seek(0)
    df = pd.read_csv(file)
    df.columns = df.columns.str.replace("\n", " ", regex=False).str.strip()

    df = df.rename(columns={
        "Device Orders Report": "Device Orders",
        "Staff Customer": "Server",
        "Base (Including Disc.)": "Base",
    })

    col_store = pick_col(df, ["id site", "site", "store"])

    required = ["Device Orders", "Server", "Base"]
    missing = [col for col in required if col not in df.columns]
    if not col_store:
        missing.append("Site / ID Site")

    if missing:
        raise ValueError(f"{file.name}: missing required tray orders columns: {', '.join(missing)}")

    df["Device Orders"] = df["Device Orders"].astype(str).str.strip().str.lower()
    df["Device Orders"] = df["Device Orders"].replace({
        "handheld": "handheld",
        "hand held": "handheld",
        "pos": "pos",
        "pos terminal": "pos",
    })
    df["Device Orders"] = df["Device Orders"].str.extract(r"(handheld|pos)", expand=False).fillna("unknown")
    df["Base"] = pd.to_numeric(df["Base"], errors="coerce").fillna(0)
    df["Server"] = df["Server"].apply(clean_name)
    df["Store"] = df[col_store].apply(extract_store_number)

    fallback_store = extract_store_from_filename(file)
    if fallback_store:
        df["Store"] = df["Store"].fillna(fallback_store)

    df["Store"] = df["Store"].apply(normalize_store_number).fillna("Unknown")

    return df[["Store", "Server", "Device Orders", "Base"]]


def process_all_tablet_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_tablet_file(file))
        except Exception as e:
            st.error(f"Tray Orders file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Store", "Server", "Tablet %"])

    combined_raw = pd.concat(all_rows, ignore_index=True)

    grouped = (
        combined_raw
        .groupby(["Store", "Server", "Device Orders"])["Base"]
        .sum()
        .unstack(fill_value=0)
    )

    if "handheld" not in grouped.columns:
        grouped["handheld"] = 0
    if "pos" not in grouped.columns:
        grouped["pos"] = 0

    grouped = grouped.rename(columns={
        "handheld": "Tablet Sales",
        "pos": "POS Sales",
    })

    grouped["Tablet %"] = (
        grouped["Tablet Sales"] /
        (grouped["Tablet Sales"] + grouped["POS Sales"])
    ).fillna(0)

    grouped["Tablet Weight"] = grouped["Tablet Sales"] + grouped["POS Sales"]

    return grouped.reset_index()[["Store", "Server", "Tablet %", "Tablet Weight"]]


# =========================
# Turn Time Processing
# =========================
def process_turn_file(file):
    file.seek(0)
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)

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
        raise ValueError(f"{file.name}: missing required tray checks columns: {', '.join(missing)}")

    df[col_open] = pd.to_datetime(df[col_open], errors="coerce")
    df[col_close] = pd.to_datetime(df[col_close], errors="coerce")

    eat = df[df[col_service].astype(str).str.contains("eat in", case=False, na=False)].copy()
    eat["Turn Time"] = (eat[col_close] - eat[col_open]).dt.total_seconds() / 60
    eat = eat.dropna(subset=["Turn Time"])
    eat = eat[eat["Turn Time"] >= 0]

    eat[col_server] = eat[col_server].fillna("(Unknown)").replace("", "(Unknown)")
    eat["Server"] = eat[col_server].apply(clean_name)
    eat["Store"] = eat[col_store].apply(extract_store_number)

    fallback_store = extract_store_from_filename(file)
    if fallback_store:
        eat["Store"] = eat["Store"].fillna(fallback_store)

    eat["Store"] = eat["Store"].apply(normalize_store_number).fillna("Unknown")

    return eat[["Store", "Server", "Turn Time"]]


def process_all_turn_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_turn_file(file))
        except Exception as e:
            st.error(f"Tray Checks file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Store", "Server", "Turn Time", "Turn Check Count"])

    combined_raw = pd.concat(all_rows, ignore_index=True)
    result = combined_raw.groupby(["Store", "Server"], as_index=False).agg(
        **{
            "Turn Time": ("Turn Time", "mean"),
            "Turn Check Count": ("Turn Time", "size"),
        }
    )
    result["Turn Time"] = result["Turn Time"].round(2)
    return result


# =========================
# Beverage Processing
# =========================
def process_beverage_file(file):
    file.seek(0)
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file, header=4)

    df.columns = [str(col).strip() for col in df.columns]

    col_store = pick_col(df, ["location"])
    col_server = pick_col(df, ["employee"])
    col_bev = pick_col(df, ["% of net sales"])
    col_net_sales = pick_col(df, ["net sales", "net sls", "net sales $", "net sls $"])

    missing = []
    if not col_store:
        missing.append("Location")
    if not col_server:
        missing.append("Employee")
    if not col_bev:
        missing.append("% of Net Sales")

    if missing:
        raise ValueError(f"{file.name}: missing required Rosnet Contest Detail columns: {', '.join(missing)}")

    raw_locations = df[col_store].astype(str)

    for loc in raw_locations.dropna().unique():
        store_num, label = extract_store_label_from_text(loc)
        if store_num and label:
            register_store_label(store_num, label)

    df["Store"] = raw_locations.apply(extract_store_number).apply(normalize_store_number)
    df["Server"] = df[col_server].apply(strip_employee_id).apply(clean_name)
    df["Dine In Bev %"] = pd.to_numeric(df[col_bev], errors="coerce")
    df["Bev Weight"] = pd.to_numeric(df[col_net_sales], errors="coerce") if col_net_sales else pd.NA

    df = df.dropna(subset=["Store", "Dine In Bev %"]).copy()
    df["Store"] = df["Store"].astype(str).str.strip()
    df["Server"] = df["Server"].fillna("").astype(str).str.strip()

    df = df[df["Store"] != ""].copy()
    df = df[df["Server"] != ""].copy()
    df = df[~df["Server"].str.lower().str.contains("total", na=False)].copy()

    non_null = df["Dine In Bev %"].dropna()
    if not non_null.empty and non_null.median() > 1:
        df["Dine In Bev %"] = df["Dine In Bev %"] / 100

    return df[["Store", "Server", "Dine In Bev %", "Bev Weight"]]


def process_all_beverage_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_beverage_file(file))
        except Exception as e:
            st.error(f"Rosnet Contest Detail file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Store", "Server", "Dine In Bev %", "Bev Weight"])

    combined = pd.concat(all_rows, ignore_index=True)

    def aggregate_bev(group):
        weights = pd.to_numeric(group["Bev Weight"], errors="coerce")
        values = pd.to_numeric(group["Dine In Bev %"], errors="coerce")
        valid = values.notna()
        weighted = valid & weights.notna() & (weights > 0)

        if weighted.any():
            bev_pct = (values[weighted] * weights[weighted]).sum() / weights[weighted].sum()
            bev_weight = weights[weighted].sum()
        else:
            bev_pct = values[valid].mean() if valid.any() else pd.NA
            bev_weight = pd.NA

        return pd.Series({
            "Dine In Bev %": bev_pct,
            "Bev Weight": bev_weight,
        })

    return combined.groupby(["Store", "Server"], as_index=False).apply(aggregate_bev, include_groups=False)


# =========================
# PPA Processing
# =========================
def process_ppa_file(file):
    file.seek(0)
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = read_excel_with_header_search(
            file,
            required_terms=["location", "employee name", "net sales", "covers", "ppa"],
            default_header=4,
        )

    df.columns = [str(col).strip() for col in df.columns]

    col_store = pick_col(df, ["location"])
    col_server = pick_col(df, ["employee name", "employee"])
    col_net_sales = pick_col(df, ["net sales"])
    col_covers = pick_col(df, ["covers"])
    col_ppa = pick_col(df, ["ppa"])

    missing = []
    if not col_store:
        missing.append("Location")
    if not col_server:
        missing.append("Employee Name")
    if not col_net_sales:
        missing.append("Net Sales")
    if not col_covers:
        missing.append("Covers")
    if not col_ppa:
        missing.append("PPA")

    if missing:
        raise ValueError(f"{file.name}: missing required Employee Sales Statistics columns: {', '.join(missing)}")

    raw_locations = df[col_store].astype(str)
    for loc in raw_locations.dropna().unique():
        store_num, label = extract_store_label_from_text(loc)
        if store_num and label:
            register_store_label(store_num, label)

    df["Store"] = raw_locations.apply(resolve_store_from_text).apply(normalize_store_number)
    df["Server"] = df[col_server].apply(clean_name)
    df["Net Sales"] = pd.to_numeric(df[col_net_sales], errors="coerce")
    df["PPA Weight"] = pd.to_numeric(df[col_covers], errors="coerce")
    reported_ppa = pd.to_numeric(df[col_ppa], errors="coerce")
    computed_ppa = (df["Net Sales"] / df["PPA Weight"]).where(df["PPA Weight"] > 0)
    # Trust Rosnet's employee-level PPA when provided; use computed values only as fallback.
    df["PPA"] = reported_ppa.fillna(computed_ppa)

    df = df.dropna(subset=["Store", "PPA"]).copy()
    df["Store"] = df["Store"].astype(str).str.strip()
    df["Server"] = df["Server"].fillna("").astype(str).str.strip()

    df = df[df["Store"] != ""].copy()
    df = df[df["Server"] != ""].copy()
    df = df[~df["Server"].str.lower().str.contains("total", na=False)].copy()

    return df[["Store", "Server", "PPA", "PPA Weight", "Net Sales"]]


def process_all_ppa_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_ppa_file(file))
        except Exception as e:
            st.error(f"Employee Sales Statistics file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Store", "Server", "PPA", "PPA Weight", "Net Sales"])

    if len(all_rows) == 1:
        return all_rows[0].copy()

    combined = pd.concat(all_rows, ignore_index=True)

    def aggregate_ppa(group):
        net_sales = pd.to_numeric(group["Net Sales"], errors="coerce")
        covers = pd.to_numeric(group["PPA Weight"], errors="coerce")
        valid = net_sales.notna() & covers.notna() & (covers > 0)

        if valid.any():
            total_sales = net_sales[valid].sum()
            total_covers = covers[valid].sum()
            ppa = total_sales / total_covers if total_covers > 0 else pd.NA
        else:
            total_sales = pd.NA
            total_covers = pd.NA
            ppa_values = pd.to_numeric(group["PPA"], errors="coerce")
            ppa = ppa_values.dropna().mean() if ppa_values.notna().any() else pd.NA

        return pd.Series({
            "PPA": ppa,
            "PPA Weight": total_covers,
            "Net Sales": total_sales,
        })

    return combined.groupby(["Store", "Server"], as_index=False).apply(aggregate_ppa, include_groups=False)


# =========================
# Score Helpers
# =========================
def is_tablet_green(x):
    return pd.notna(x) and x >= 0.90


def is_turn_green(x):
    return pd.notna(x) and x <= 40


def is_bev_green(x):
    return pd.notna(x) and x >= 0.19


def is_ppa_green(x):
    return pd.notna(x) and x >= 21


def tablet_score_icon(x):
    if pd.isna(x):
        return ""
    if x >= 0.90:
        return "🟢"
    elif x >= 0.80:
        return "🟡"
    return "🔴"


def turn_score_icon(x):
    if pd.isna(x):
        return ""
    if x <= 40:
        return "🟢"
    elif x <= 45:
        return "🟡"
    return "🔴"


def beverage_score_icon(x):
    if pd.isna(x):
        return ""
    if x >= 0.19:
        return "🟢"
    elif x >= 0.18:
        return "🟡"
    return "🔴"


def ppa_score_icon(x):
    if pd.isna(x):
        return ""
    if x >= 21:
        return "🟢"
    elif x >= 20:
        return "🟡"
    return "🔴"

def tablet_box_color(x):
    if pd.isna(x):
        return "#f5f8fc"  # neutral
    if x >= 0.90:
        return "#6fdc8c"
    elif x >= 0.80:
        return "#ffe066"
    return "#ff6b6b"


def turn_box_color(x):
    if pd.isna(x):
        return "#f5f8fc"
    if x <= 40:
        return "#6fdc8c"
    elif x <= 45:
        return "#ffe066"
    return "#ff6b6b"


def beverage_box_color(x):
    if pd.isna(x):
        return "#f5f8fc"
    if x >= 0.19:
        return "#6fdc8c"
    elif x >= 0.18:
        return "#ffe066"
    return "#ff6b6b"


def ppa_box_color(x):
    if pd.isna(x):
        return "#f5f8fc"
    if x >= 21:
        return "#6fdc8c"
    elif x >= 20:
        return "#ffe066"
    return "#ff6b6b"


def box_text_color(fill_color):
    if fill_color in ["#ff6b6b", "#1d4f91"]:
        return "white"
    return "#222222"


def greens_count(row):
    count = 0
    if is_tablet_green(row["Tablet %"]):
        count += 1
    if is_turn_green(row["Turn Time"]):
        count += 1
    if is_bev_green(row["Dine In Bev %"]):
        count += 1
    if "PPA" in row and is_ppa_green(row["PPA"]):
        count += 1
    return count


# =========================
# WhatsApp Card Export
# =========================
def create_whatsapp_store_card(store_label, store_df):
    avg_turn = weighted_mean(store_df, "Turn Time", "Turn Check Count", default=safe_mean(store_df["Turn Time"]))
    avg_bev = weighted_mean(store_df, "Dine In Bev %", "Bev Weight", default=safe_mean(store_df["Dine In Bev %"]))
    avg_ppa = weighted_mean(store_df, "PPA", "PPA Weight", default=safe_mean(store_df["PPA"]))

    visible_df = store_df[~store_df["Server"].apply(is_support_staff)].copy()
    total_servers = len(visible_df)
    ppa_available = visible_df["PPA"].notna().any()
    all_green_mask = (
        visible_df["Turn Time"].apply(is_turn_green)
        & visible_df["Dine In Bev %"].apply(is_bev_green)
    )
    if ppa_available:
        all_green_mask = all_green_mask & visible_df["PPA"].apply(is_ppa_green)
    all_green = visible_df[all_green_mask]
    all_green_count = len(all_green)

    export_df = visible_df.copy()

    def export_turn_text(x):
        if pd.isna(x):
            return ""
        return f"{x:.2f}"

    def export_bev_text(x):
        if pd.isna(x):
            return ""
        return f"{x:.2%}"

    def export_ppa_text(x):
        if pd.isna(x):
            return ""
        return f"${x:.2f}"

    export_df["Turn Time"] = export_df["Turn Time"].apply(export_turn_text)
    export_df["Dine In Bev %"] = export_df["Dine In Bev %"].apply(export_bev_text)
    export_df["PPA"] = export_df["PPA"].apply(export_ppa_text)

    export_df = export_df[["Server", "Turn Time", "Dine In Bev %", "PPA"]].copy()

    badge_df = visible_df.copy()
    badge_df["_turn_green"] = badge_df["Turn Time"].apply(is_turn_green)
    badge_df["_bev_green"] = badge_df["Dine In Bev %"].apply(is_bev_green)
    badge_df["_ppa_green"] = badge_df["PPA"].apply(is_ppa_green) if ppa_available else True
    badge_df["_pass_count"] = (
        badge_df["_turn_green"].astype(int)
        + badge_df["_bev_green"].astype(int)
        + badge_df["_ppa_green"].astype(int)
    )

    badge_by_row = {}
    if not badge_df.empty:
        top_idx = badge_df.sort_values(
            by=["_pass_count", "PPA", "Dine In Bev %", "Turn Time", "Server"],
            ascending=[False, False, False, True, True],
        ).index[0]
        badge_by_row[top_idx] = ("TOP PERFORMER", "#8b5cf6", "white")

        for idx in badge_df.index[
            badge_df["_turn_green"] & badge_df["_bev_green"] & badge_df["_ppa_green"]
        ]:
            badge_by_row.setdefault(idx, ("ALL GREEN", "#22c55e", "#111827"))

        coach_mask = (~badge_df["_turn_green"]) & (~badge_df["_bev_green"]) & (~badge_df["_ppa_green"])
        for idx in badge_df.index[coach_mask]:
            badge_by_row.setdefault(idx, ("COACH", "#facc15", "#111827"))

        slow_turn = pd.to_numeric(badge_df["Turn Time"], errors="coerce")
        if slow_turn.notna().any():
            slowest_idx = slow_turn.idxmax()
            badge_by_row.setdefault(slowest_idx, ("SLOWEST TURN", "#ef4444", "white"))

    row_count = len(export_df)
    fig_height = max(9.4, 4.9 + (row_count * 0.42))
    fig, ax = plt.subplots(figsize=(8.2, fig_height))
    fig.patch.set_facecolor("white")
    ax.set_axis_off()

    ax.add_patch(Rectangle(
        (0.01, 0.01), 0.98, 0.98,
        transform=ax.transAxes,
        facecolor="white",
        edgecolor="#d7dee8",
        linewidth=1.2,
        zorder=0
    ))

    ax.add_patch(Rectangle(
        (0.01, 0.91), 0.98, 0.08,
        transform=ax.transAxes,
        facecolor="#1d4f91",
        edgecolor="#1d4f91",
        zorder=1
    ))
    ax.text(
        0.50, 0.95, store_label,
        transform=ax.transAxes,
        fontsize=17,
        fontweight="bold",
        color="white",
        ha="center",
        va="center",
        zorder=2
    )

    lane_y = 0.67
    lane_h = 0.16
    lane_w = 0.22
    lane_xs = [0.03, 0.27, 0.51, 0.75]

    lane_data = [
        (
            "TURN",
            "No data" if pd.isna(avg_turn) else f"{avg_turn:.2f}",
            turn_box_color(avg_turn),
        ),
        (
            "BEVERAGE",
            "No data" if pd.isna(avg_bev) else f"{avg_bev:.2%}",
            beverage_box_color(avg_bev),
        ),
        (
            "PPA",
            "No data" if pd.isna(avg_ppa) else f"${avg_ppa:.2f}",
            ppa_box_color(avg_ppa),
        ),
        (
            "ALL GREEN",
            f"{all_green_count} of {total_servers}",
            "#b160f0",
        ),
    ]

    for lane_x, lane in zip(lane_xs, lane_data):
        title, avg_value, fill_color = lane
        text_color = box_text_color(fill_color)

        ax.add_patch(Rectangle(
            (lane_x, lane_y), lane_w, lane_h,
            transform=ax.transAxes,
            facecolor=fill_color,
            edgecolor="#cfd9e6",
            linewidth=1,
            zorder=1
        ))

        ax.text(
            lane_x + lane_w / 2, lane_y + lane_h - 0.03, title,
            transform=ax.transAxes,
            fontsize=11,
            fontweight="bold",
            color="white",
            ha="center",
            va="top",
            zorder=2
        )

        ax.text(
            lane_x + lane_w / 2, lane_y + 0.06, avg_value,
            transform=ax.transAxes,
            fontsize=18,
            fontweight="bold",
            color="#111827",
            ha="center",
            va="center",
            zorder=2
        )
    table_bbox = [0.08, 0.09, 0.84, 0.49]
    table = ax.table(
        cellText=export_df.values,
        colLabels=export_df.columns,
        cellLoc="left",
        loc="center",
        bbox=table_bbox,
        colWidths=[0.36, 0.20, 0.24, 0.20],
    )

    table.auto_set_font_size(False)
    table.set_fontsize(9.8)
    table.scale(1, 1.42)

    ncols = len(export_df.columns)

    for col_idx in range(ncols):
        header_cell = table[0, col_idx]
        header_cell.set_text_props(weight="bold", color="white")
        header_cell.set_facecolor("#2d6cb5")
        header_cell.set_edgecolor("#d7dee8")

    for row_idx in range(1, len(export_df) + 1):
        original_row = visible_df.iloc[row_idx - 1]

        for col_idx in range(ncols):
            cell = table[row_idx, col_idx]
            cell.set_edgecolor("#dfe5ec")
            if row_idx % 2 == 0:
                cell.set_facecolor("#fbfcfe")
            else:
                cell.set_facecolor("white")

        turn_cell = table[row_idx, 1]
        turn_val = original_row["Turn Time"]
        if pd.notna(turn_val):
            if turn_val <= 40:
                turn_cell.set_facecolor("#6fdc8c")
                turn_cell.set_text_props(weight="bold", color="black")
            elif turn_val <= 45:
                turn_cell.set_facecolor("#ffe066")
                turn_cell.set_text_props(weight="bold", color="black")
            else:
                turn_cell.set_facecolor("#ff6b6b")
                turn_cell.set_text_props(weight="bold", color="white")

        bev_cell = table[row_idx, 2]
        bev_val = original_row["Dine In Bev %"]
        if pd.notna(bev_val):
            if bev_val >= 0.19:
                bev_cell.set_facecolor("#6fdc8c")
                bev_cell.set_text_props(weight="bold", color="black")
            elif bev_val >= 0.18:
                bev_cell.set_facecolor("#ffe066")
                bev_cell.set_text_props(weight="bold", color="black")
            else:
                bev_cell.set_facecolor("#ff6b6b")
                bev_cell.set_text_props(weight="bold", color="white")

        ppa_cell = table[row_idx, 3]
        ppa_val = original_row["PPA"]
        if pd.notna(ppa_val):
            if ppa_val >= 21:
                ppa_cell.set_facecolor("#6fdc8c")
                ppa_cell.set_text_props(weight="bold", color="black")
            elif ppa_val >= 20:
                ppa_cell.set_facecolor("#ffe066")
                ppa_cell.set_text_props(weight="bold", color="black")
            else:
                ppa_cell.set_facecolor("#ff6b6b")
                ppa_cell.set_text_props(weight="bold", color="white")

    fig.canvas.draw()
    for row_idx in range(1, len(export_df) + 1):
        original_row = visible_df.iloc[row_idx - 1]
        badge = badge_by_row.get(original_row.name)
        if not badge:
            continue
        label, fill_color, text_color = badge
        server_cell = table[row_idx, 0]
        x = server_cell.get_x()
        y = server_cell.get_y()
        w = server_cell.get_width()
        h = server_cell.get_height()
        ax.text(
            x + w - 0.006,
            y + h / 2,
            label,
            transform=ax.transAxes,
            ha="right",
            va="center",
            fontsize=6.0,
            fontweight="bold",
            color=text_color,
            bbox=dict(
                boxstyle="round,pad=0.18,rounding_size=0.25",
                facecolor=fill_color,
                edgecolor="none",
            ),
            zorder=3,
        )

    return fig


# =========================
# Main Processing
# =========================
if tablet_files or turn_files or beverage_files or ppa_files:
    if beverage_files and len(beverage_files) > 1:
        st.warning("Multiple Contest Detail files uploaded. Using only the most recent file for Dine-In Bev %.")
    if ppa_files and len(ppa_files) > 1:
        st.warning("Multiple Employee Sales Statistics files uploaded. Using only the most recent file for PPA.")

    tablet_df = process_all_tablet_files(tablet_files or [])
    turn_df = process_all_turn_files(turn_files or [])
    beverage_input = beverage_files[-1:] if beverage_files else []
    ppa_input = ppa_files[-1:] if ppa_files else []
    beverage_df = process_all_beverage_files(beverage_input)
    ppa_df = process_all_ppa_files(ppa_input)

    combined = pd.DataFrame()

    if not tablet_df.empty:
        combined = tablet_df.copy()

    if not turn_df.empty:
        combined = turn_df.copy() if combined.empty else pd.merge(
            combined, turn_df, on=["Store", "Server"], how="outer"
        )

    if not beverage_df.empty:
        combined = beverage_df.copy() if combined.empty else pd.merge(
            combined, beverage_df, on=["Store", "Server"], how="outer"
        )

    if not ppa_df.empty:
        combined = ppa_df.copy() if combined.empty else pd.merge(
            combined, ppa_df, on=["Store", "Server"], how="outer"
        )

    if not combined.empty:
        combined["Store"] = combined["Store"].fillna("Unknown").astype(str).str.strip()
        combined["Store"] = combined["Store"].apply(normalize_store_number).fillna("Unknown")
        combined["Server"] = combined["Server"].fillna("").astype(str).str.strip()

        combined = combined[combined["Server"] != ""].copy()
        combined = combined[~combined["Server"].str.lower().str.contains("total", na=False)].copy()
        combined["_support_staff"] = combined["Server"].apply(is_support_staff)

        if "Tablet %" not in combined.columns:
            combined["Tablet %"] = pd.NA
        if "Turn Time" not in combined.columns:
            combined["Turn Time"] = pd.NA
        if "Dine In Bev %" not in combined.columns:
            combined["Dine In Bev %"] = pd.NA
        if "PPA" not in combined.columns:
            combined["PPA"] = pd.NA

        visible_combined = combined[~combined["_support_staff"]].copy()
        ppa_available = visible_combined["PPA"].notna().any()

        combined["_all_green"] = combined.apply(
            lambda row: (
                (not row["_support_staff"])
                and
                is_tablet_green(row["Tablet %"])
                and is_turn_green(row["Turn Time"])
                and is_bev_green(row["Dine In Bev %"])
                and (is_ppa_green(row["PPA"]) if ppa_available else True)
            ),
            axis=1,
        )

        combined["_greens_count"] = combined.apply(greens_count, axis=1)

        store_order = sorted(
            combined["Store"].dropna().unique(),
            key=lambda x: (x == "Unknown", x)
        )

        st.subheader("Combined Server Performance")

        for store in store_order:
            store_df = combined[combined["Store"] == store].copy()

            if store_df.empty:
                continue

            store_label = get_store_label(store)
            store_display_df = store_df[~store_df["_support_staff"]].copy()
            st.markdown(f"### 📍 {store_label}")

            avg_tablet = weighted_mean(store_df, "Tablet %", "Tablet Weight", default=safe_mean(store_df["Tablet %"]))
            avg_turn = weighted_mean(store_df, "Turn Time", "Turn Check Count", default=safe_mean(store_df["Turn Time"]))
            avg_bev = weighted_mean(store_df, "Dine In Bev %", "Bev Weight", default=safe_mean(store_df["Dine In Bev %"]))
            avg_ppa = weighted_mean(store_df, "PPA", "PPA Weight", default=safe_mean(store_df["PPA"]))

            tablet_col, turn_col, bev_col, ppa_col = st.columns(4)

            with tablet_col:
                st.metric(
                    "Avg Tablet %",
                    "No data" if pd.isna(avg_tablet) else f"{avg_tablet:.2%}"
                )
                st.markdown(format_single_rank_line(store_display_df, "Tablet %", "Top", ascending=False))
                st.markdown(format_single_rank_line(store_display_df, "Tablet %", "Bottom", ascending=True))

            with turn_col:
                st.metric(
                    "Avg Turn",
                    "No data" if pd.isna(avg_turn) else f"{avg_turn:.2f}"
                )
                st.markdown(format_single_rank_line(store_display_df, "Turn Time", "Best", ascending=True))
                st.markdown(format_single_rank_line(store_display_df, "Turn Time", "Slowest", ascending=False))

            with bev_col:
                st.metric(
                    "Avg Dine In Bev %",
                    "No data" if pd.isna(avg_bev) else f"{avg_bev:.2%}"
                )
                st.markdown(format_single_rank_line(store_display_df, "Dine In Bev %", "Top", ascending=False))
                st.markdown(format_single_rank_line(store_display_df, "Dine In Bev %", "Bottom", ascending=True))

            with ppa_col:
                st.metric(
                    "Avg PPA",
                    "No data" if pd.isna(avg_ppa) else f"${avg_ppa:.2f}"
                )
                st.markdown(format_single_rank_line(store_display_df, "PPA", "Top", ascending=False))
                st.markdown(format_single_rank_line(store_display_df, "PPA", "Bottom", ascending=True))

            def tablet_metric_with_dot(x):
                if pd.isna(x):
                    return ""
                return f"{tablet_score_icon(x)} {x:.2%}"

            def turn_metric_with_dot(x):
                if pd.isna(x):
                    return ""
                return f"{turn_score_icon(x)} {x:.2f}"

            def beverage_metric_with_dot(x):
                if pd.isna(x):
                    return ""
                return f"{beverage_score_icon(x)} {x:.2%}"

            def ppa_metric_with_dot(x):
                if pd.isna(x):
                    return ""
                return f"{ppa_score_icon(x)} ${x:.2f}"

            store_df_sorted = store_display_df.copy()
            store_df_sorted["_tablet_sort"] = pd.to_numeric(store_df_sorted["Tablet %"], errors="coerce").fillna(-1)
            store_df_sorted["_turn_sort"] = pd.to_numeric(store_df_sorted["Turn Time"], errors="coerce").fillna(999999)
            store_df_sorted["_bev_sort"] = pd.to_numeric(store_df_sorted["Dine In Bev %"], errors="coerce").fillna(-1)
            store_df_sorted["_ppa_sort"] = pd.to_numeric(store_df_sorted["PPA"], errors="coerce").fillna(-1)

            store_df_sorted = store_df_sorted.sort_values(
                by=["_greens_count", "_tablet_sort", "_turn_sort", "_bev_sort", "_ppa_sort", "Server"],
                ascending=[False, False, True, False, False, True]
            ).reset_index(drop=True)

            display_df = store_df_sorted.copy()
            display_df["Tablet %"] = display_df["Tablet %"].apply(tablet_metric_with_dot)
            display_df["Turn Time"] = display_df["Turn Time"].apply(turn_metric_with_dot)
            display_df["Dine In Bev %"] = display_df["Dine In Bev %"].apply(beverage_metric_with_dot)
            display_df["PPA"] = display_df["PPA"].apply(ppa_metric_with_dot)

            display_df = display_df[[
                "Server",
                "Tablet %",
                "Turn Time",
                "Dine In Bev %",
                "PPA",
            ]]

            def highlight_all_green(row):
                original_row = store_df_sorted.iloc[row.name]
                if original_row["_all_green"]:
                    return ["background-color: #e8f5e9"] * len(row)
                return [""] * len(row)

            styled_df = display_df.style.apply(highlight_all_green, axis=1)

            st.dataframe(styled_df, use_container_width=True, hide_index=True)

            card_fig = create_whatsapp_store_card(store_label, store_df)
            card_buf = fig_to_png_bytes(card_fig)
            safe_store_label = store_label.replace(" - ", "_").replace(" ", "_")

            st.download_button(
                label=f"Download {store_label} WhatsApp Card",
                data=card_buf,
                file_name=f"{safe_store_label}_whatsapp_card.png",
                mime="image/png",
            )

            st.divider()
    else:
        st.warning("No valid data could be processed from the uploaded files.")
else:
    st.info("Upload your Tray Orders CSV(s), Tray Checks CSV(s), Rosnet Contest Detail XLSX, and/or Employee Sales Statistics XLSX to begin.")
