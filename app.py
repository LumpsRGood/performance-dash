import pandas as pd
import streamlit as st

st.set_page_config(page_title="FOH Performance Dashboard", layout="wide")

st.title("FOH Performance Dashboard")
st.caption("Combined Tablet Use + Turn Time")

# =========================
# Upload Section
# =========================
tablet_files = st.file_uploader(
    "Upload Tablet Usage CSV file(s)",
    type=["csv"],
    accept_multiple_files=True
)

turn_files = st.file_uploader(
    "Upload Turn Time file(s)",
    type=["csv", "xlsx"],
    accept_multiple_files=True
)

# =========================
# Helper: Name Cleanup
# =========================
def clean_name(name):
    if pd.isna(name):
        return ""
    name = str(name).strip()
    if "," in name:
        parts = name.split(",", 1)
        name = f"{parts[1].strip()} {parts[0].strip()}"
    return " ".join(name.split()).title()

# =========================
# Tablet Processing
# =========================
def process_tablet_file(file):
    df = pd.read_csv(file)
    df.columns = df.columns.str.replace("\n", " ", regex=False).str.strip()

    df = df.rename(columns={
        "Device Orders Report": "Device Orders",
        "Staff Customer": "Server",
        "Base (Including Disc.)": "Base"
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
        "pos terminal": "pos"
    })
    df["Device Orders"] = df["Device Orders"].str.extract(r"(handheld|pos)", expand=False).fillna("unknown")
    df["Base"] = pd.to_numeric(df["Base"], errors="coerce").fillna(0)
    df["Server"] = df["Server"].apply(clean_name)

    return df[["Server", "Device Orders", "Base"]]

def process_all_tablet_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_tablet_file(file))
        except Exception as e:
            st.error(f"Tablet file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Server", "Tablet Sales", "POS Sales", "Tablet %"])

    combined_raw = pd.concat(all_rows, ignore_index=True)

    grouped = (
        combined_raw
        .groupby(["Server", "Device Orders"])["Base"]
        .sum()
        .unstack(fill_value=0)
    )

    if "handheld" not in grouped.columns:
        grouped["handheld"] = 0
    if "pos" not in grouped.columns:
        grouped["pos"] = 0

    grouped = grouped.rename(columns={
        "handheld": "Tablet Sales",
        "pos": "POS Sales"
    }).reset_index()

    grouped["Tablet %"] = (
        grouped["Tablet Sales"] /
        (grouped["Tablet Sales"] + grouped["POS Sales"])
    ).fillna(0)

    return grouped[["Server", "Tablet Sales", "POS Sales", "Tablet %"]]

# =========================
# Turn Time Processing
# =========================
def pick_col(df, keywords):
    for col in df.columns:
        col_l = col.lower().strip()
        for key in keywords:
            if key in col_l:
                return col
    return None

def process_turn_file(file):
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

    return eat[["Server", "Turn Time"]]

def process_all_turn_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_turn_file(file))
        except Exception as e:
            st.error(f"Turn file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Server", "Turn Time"])

    combined_raw = pd.concat(all_rows, ignore_index=True)

    result = (
        combined_raw
        .groupby("Server", as_index=False)["Turn Time"]
        .mean()
    )

    result["Turn Time"] = result["Turn Time"].round(2)
    return result

# =========================
# Score Helpers
# =========================
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

# =========================
# Main Processing
# =========================
if tablet_files or turn_files:
    tablet_df = process_all_tablet_files(tablet_files or [])
    turn_df = process_all_turn_files(turn_files or [])

    if not tablet_df.empty and not turn_df.empty:
        combined = pd.merge(tablet_df, turn_df, on="Server", how="outer")
    elif not tablet_df.empty:
        combined = tablet_df.copy()
        combined["Turn Time"] = pd.NA
    elif not turn_df.empty:
        combined = turn_df.copy()
        combined["Tablet Sales"] = pd.NA
        combined["POS Sales"] = pd.NA
        combined["Tablet %"] = pd.NA
    else:
        combined = pd.DataFrame()

    if not combined.empty:
    # Drop blank / junk server rows
        combined["Server"] = combined["Server"].fillna("").astype(str).str.strip()
        combined = combined[combined["Server"] != ""].copy()

    def tablet_metric_with_dot(x):
        if pd.isna(x):
            return ""
        return f"{tablet_score_icon(x)} {x:.2%}"

    def turn_metric_with_dot(x):
        if pd.isna(x):
            return ""
        return f"{turn_score_icon(x)} {x:.2f}"

    display_df = combined.copy()

    # Apply formatting
    display_df["Tablet %"] = display_df["Tablet %"].apply(tablet_metric_with_dot)
    display_df["Turn Time"] = display_df["Turn Time"].apply(turn_metric_with_dot)

    # Only show what matters
    display_df = display_df[[
        "Server",
        "Tablet %",
        "Turn Time"
    ]]

    # Sort by actual tablet % (not the string)
    sort_helper = combined["Tablet %"].fillna(-1)
    display_df = display_df.loc[
        sort_helper.sort_values(ascending=False).index
    ].reset_index(drop=True)

    st.subheader("Combined Server Performance")
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No valid data could be processed from the uploaded files.")
else:
    st.info("Upload tablet files, turn files, or both to begin.")
