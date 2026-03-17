import re
from io import BytesIO

import pandas as pd
import streamlit as st

st.set_page_config(page_title="FOH Performance Dashboard", layout="wide")

st.title("FOH Performance Dashboard")
st.caption("Combined Tablet Use + Turn Time + Dine In Beverage %")

# =========================
# Store Mapping
# =========================
STORE_MAP = {
    "3231": "Prattville",
    "4445": "Montgomery",
    "4456": "Oxford",
    "4463": "Decatur",
}

KNOWN_STORES = set(STORE_MAP.keys())

# =========================
# Upload Section
# =========================
tablet_files = st.file_uploader(
    "Upload Tablet Usage CSV file(s)",
    type=["csv"],
    accept_multiple_files=True,
)

turn_files = st.file_uploader(
    "Upload Turn Time file(s)",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=True,
)

beverage_files = st.file_uploader(
    "Upload Dine In Beverage file(s)",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True,
)

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


def pick_col(df, keywords):
    for col in df.columns:
        col_l = str(col).lower().strip()
        for key in keywords:
            if key in col_l:
                return col
    return None


def get_store_label(store_num):
    if not store_num:
        return "Unknown"
    return f"{store_num} - {STORE_MAP.get(store_num, 'Unknown')}"


def extract_store_from_text(text):
    matches = re.findall(r"\b\d{4}\b", str(text))
    for match in matches:
        if match in KNOWN_STORES:
            return match
    return None


def extract_store_from_filename(file):
    return extract_store_from_text(file.name)


def extract_store_from_csv_content(file):
    try:
        file.seek(0)
        raw = file.read()
        file.seek(0)

        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="ignore")
        else:
            text = str(raw)

        store = extract_store_from_text(text[:5000])
        return store
    except Exception:
        file.seek(0)
        return None


def extract_store_from_excel_content(file):
    try:
        file.seek(0)
        content = file.read()
        file.seek(0)

        bio = BytesIO(content)
        preview = pd.read_excel(bio, header=None, nrows=10)

        for value in preview.astype(str).fillna("").values.flatten():
            store = extract_store_from_text(value)
            if store:
                return store
        return None
    except Exception:
        file.seek(0)
        return None


def detect_store(file):
    store = extract_store_from_filename(file)
    if store:
        return store

    name = file.name.lower()
    if name.endswith(".csv"):
        store = extract_store_from_csv_content(file)
    else:
        store = extract_store_from_excel_content(file)

    return store or "Unknown"


def safe_mean(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return pd.NA
    return s.mean()


# =========================
# Tablet Processing
# =========================
def process_tablet_file(file):
    store = detect_store(file)

    file.seek(0)
    df = pd.read_csv(file)
    df.columns = df.columns.str.replace("\n", " ", regex=False).str.strip()

    df = df.rename(columns={
        "Device Orders Report": "Device Orders",
        "Staff Customer": "Server",
        "Base (Including Disc.)": "Base",
    })

    required = ["Device Orders", "Server", "Base"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{file.name}: missing required tablet columns: {', '.join(missing)}")

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
    df["Store"] = store

    return df[["Store", "Server", "Device Orders", "Base"]]


def process_all_tablet_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_tablet_file(file))
        except Exception as e:
            st.error(f"Tablet file '{file.name}' failed: {e}")

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

    return grouped.reset_index()[["Store", "Server", "Tablet %"]]


# =========================
# Turn Time Processing
# =========================
def process_turn_file(file):
    store = detect_store(file)

    file.seek(0)
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)

    df.columns = df.columns.str.strip()

    col_open = pick_col(df, ["opened", "open", "order start", "start time", "opened at"])
    col_close = pick_col(df, ["closed", "close", "order end", "end time", "closed at"])
    col_service = pick_col(df, ["service", "service type", "order type"])
    col_server = pick_col(df, ["created by", "server", "server name", "employee", "cashier"])

    missing = []
    if not col_open:
        missing.append("Opened")
    if not col_close:
        missing.append("Closed")
    if not col_service:
        missing.append("Service")
    if not col_server:
        missing.append("Server")

    if missing:
        raise ValueError(f"{file.name}: missing required turn columns: {', '.join(missing)}")

    df[col_open] = pd.to_datetime(df[col_open], errors="coerce")
    df[col_close] = pd.to_datetime(df[col_close], errors="coerce")

    eat = df[df[col_service].astype(str).str.contains("eat in", case=False, na=False)].copy()
    eat["Turn Time"] = (eat[col_close] - eat[col_open]).dt.total_seconds() / 60
    eat = eat.dropna(subset=["Turn Time"])
    eat = eat[eat["Turn Time"] >= 0]

    eat[col_server] = eat[col_server].fillna("(Unknown)").replace("", "(Unknown)")
    eat["Server"] = eat[col_server].apply(clean_name)
    eat["Store"] = store

    return eat[["Store", "Server", "Turn Time"]]


def process_all_turn_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_turn_file(file))
        except Exception as e:
            st.error(f"Turn file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Store", "Server", "Turn Time"])

    combined_raw = pd.concat(all_rows, ignore_index=True)

    result = combined_raw.groupby(["Store", "Server"], as_index=False)["Turn Time"].mean()
    result["Turn Time"] = result["Turn Time"].round(2)
    return result


# =========================
# Beverage Processing
# Excel file real header is row 5 -> header=4
# CSV export uses first row as header
# Uses Employee + % of Net Sales
# =========================
def process_beverage_file(file):
    store = detect_store(file)

    file.seek(0)
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file, header=4)

    df.columns = [str(col).strip() for col in df.columns]

    col_server = pick_col(df, ["employee"])
    col_bev = pick_col(df, ["% of net sales"])

    missing = []
    if not col_server:
        missing.append("Employee")
    if not col_bev:
        missing.append("% of Net Sales")

    if missing:
        raise ValueError(f"{file.name}: missing required beverage columns: {', '.join(missing)}")

    df["Server"] = df[col_server].apply(clean_name)
    df["Dine In Bev %"] = pd.to_numeric(df[col_bev], errors="coerce")
    df["Store"] = store

    df = df.dropna(subset=["Dine In Bev %"]).copy()
    df["Server"] = df["Server"].fillna("").astype(str).str.strip()
    df = df[df["Server"] != ""].copy()
    df = df[~df["Server"].str.lower().str.contains("total", na=False)].copy()

    non_null = df["Dine In Bev %"].dropna()
    if not non_null.empty and non_null.median() > 1:
        df["Dine In Bev %"] = df["Dine In Bev %"] / 100

    return df[["Store", "Server", "Dine In Bev %"]]


def process_all_beverage_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_beverage_file(file))
        except Exception as e:
            st.error(f"Beverage file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Store", "Server", "Dine In Bev %"])

    combined = pd.concat(all_rows, ignore_index=True)
    return combined.groupby(["Store", "Server"], as_index=False)["Dine In Bev %"].mean()


# =========================
# Score Helpers
# =========================
def is_tablet_green(x):
    return pd.notna(x) and x >= 0.90


def is_turn_green(x):
    return pd.notna(x) and x <= 40


def is_bev_green(x):
    return pd.notna(x) and x >= 0.19


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


def metric_count(series, fn):
    s = pd.to_numeric(series, errors="coerce")
    return int(s.apply(fn).sum())


def format_rank_line(df, column, label, ascending=False, top_n=3):
    working = df[["Server", column]].copy()
    working[column] = pd.to_numeric(working[column], errors="coerce")
    working = working.dropna(subset=[column])

    if working.empty:
        return f"**{label}:** No data"

    ranked = working.sort_values(by=column, ascending=ascending).head(top_n)

    parts = []
    for _, row in ranked.iterrows():
        value = row[column]
        if "Tablet" in label or "Beverage" in label:
            parts.append(f"{row['Server']} ({value:.2%})")
        else:
            parts.append(f"{row['Server']} ({value:.2f})")

    return f"**{label}:** " + " • ".join(parts)


# =========================
# Main Processing
# =========================
if tablet_files or turn_files or beverage_files:
    tablet_df = process_all_tablet_files(tablet_files or [])
    turn_df = process_all_turn_files(turn_files or [])
    beverage_df = process_all_beverage_files(beverage_files or [])

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

    if not combined.empty:
        combined["Store"] = combined["Store"].fillna("Unknown").astype(str).str.strip()
        combined["Server"] = combined["Server"].fillna("").astype(str).str.strip()

        combined = combined[combined["Server"] != ""].copy()
        combined = combined[~combined["Server"].str.lower().str.contains("total", na=False)].copy()

        if "Tablet %" not in combined.columns:
            combined["Tablet %"] = pd.NA
        if "Turn Time" not in combined.columns:
            combined["Turn Time"] = pd.NA
        if "Dine In Bev %" not in combined.columns:
            combined["Dine In Bev %"] = pd.NA

        combined["_all_green"] = combined.apply(
            lambda row: (
                is_tablet_green(row["Tablet %"])
                and is_turn_green(row["Turn Time"])
                and is_bev_green(row["Dine In Bev %"])
            ),
            axis=1,
        )

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
            st.markdown(f"### 📍 {store_label}")

            all_green_count = int(store_df["_all_green"].sum())
            total_servers = len(store_df)

            tablet_green_count = metric_count(store_df["Tablet %"], is_tablet_green)
            turn_green_count = metric_count(store_df["Turn Time"], is_turn_green)
            bev_green_count = metric_count(store_df["Dine In Bev %"], is_bev_green)

            avg_tablet = safe_mean(store_df["Tablet %"])
            avg_turn = safe_mean(store_df["Turn Time"])
            avg_bev = safe_mean(store_df["Dine In Bev %"])

            summary_parts = [
                f"Servers: **{total_servers}**",
                f"All Green: **{all_green_count}**",
                f"Tablet Green: **{tablet_green_count}**",
                f"Turn Green: **{turn_green_count}**",
                f"Beverage Green: **{bev_green_count}**",
            ]

            if pd.notna(avg_tablet):
                summary_parts.append(f"Avg Tablet: **{avg_tablet:.2%}**")
            if pd.notna(avg_turn):
                summary_parts.append(f"Avg Turn: **{avg_turn:.2f}**")
            if pd.notna(avg_bev):
                summary_parts.append(f"Avg Dine In Bev: **{avg_bev:.2%}**")

            st.markdown(" | ".join(summary_parts))

            st.markdown(
                format_rank_line(store_df, "Tablet %", "Top Tablet", ascending=False)
            )
            st.markdown(
                format_rank_line(store_df, "Turn Time", "Best Turn", ascending=True)
            )
            st.markdown(
                format_rank_line(store_df, "Dine In Bev %", "Top Beverage", ascending=False)
            )

            st.markdown(
                format_rank_line(store_df, "Tablet %", "Bottom Tablet", ascending=True)
            )
            st.markdown(
                format_rank_line(store_df, "Turn Time", "Slowest Turn", ascending=False)
            )
            st.markdown(
                format_rank_line(store_df, "Dine In Bev %", "Bottom Beverage", ascending=True)
            )

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

            display_df = store_df.copy()

            display_df["Tablet %"] = display_df["Tablet %"].apply(tablet_metric_with_dot)
            display_df["Turn Time"] = display_df["Turn Time"].apply(turn_metric_with_dot)
            display_df["Dine In Bev %"] = display_df["Dine In Bev %"].apply(beverage_metric_with_dot)

            display_df = display_df[[
                "Server",
                "Tablet %",
                "Turn Time",
                "Dine In Bev %",
            ]]

            sort_helper = store_df["Tablet %"].fillna(-1)
            display_df = display_df.loc[
                sort_helper.sort_values(ascending=False).index
            ].reset_index(drop=True)

            store_df_sorted = store_df.loc[
                sort_helper.sort_values(ascending=False).index
            ].reset_index(drop=True)

            def highlight_all_green(row):
                original_row = store_df_sorted.iloc[row.name]
                if original_row["_all_green"]:
                    return ["background-color: #e8f5e9"] * len(row)
                return [""] * len(row)

            styled_df = display_df.style.apply(highlight_all_green, axis=1)

            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            st.divider()
    else:
        st.warning("No valid data could be processed from the uploaded files.")
else:
    st.info("Upload tablet files, turn files, beverage files, or any combination to begin.")
