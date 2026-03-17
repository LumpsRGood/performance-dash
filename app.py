import pandas as pd
import streamlit as st

st.set_page_config(page_title="FOH Performance Dashboard", layout="wide")

st.title("FOH Performance Dashboard")
st.caption("Combined Tablet Use + Turn Time + Dine In Beverage %")

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
    type=["csv", "xlsx"],
    accept_multiple_files=True,
)

beverage_files = st.file_uploader(
    "Upload Dine In Beverage file(s)",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True,
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


def pick_col(df, keywords):
    for col in df.columns:
        col_l = str(col).lower().strip()
        for key in keywords:
            if key in col_l:
                return col
    return None


# =========================
# Tablet Processing
# =========================
def process_tablet_file(file):
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

    return df[["Server", "Device Orders", "Base"]]


def process_all_tablet_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_tablet_file(file))
        except Exception as e:
            st.error(f"Tablet file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Server", "Tablet %"])

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
        "pos": "POS Sales",
    })

    grouped["Tablet %"] = (
        grouped["Tablet Sales"] /
        (grouped["Tablet Sales"] + grouped["POS Sales"])
    ).fillna(0)

    return grouped.reset_index()[["Server", "Tablet %"]]


# =========================
# Turn Time Processing
# =========================
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

    result = combined_raw.groupby("Server", as_index=False)["Turn Time"].mean()
    result["Turn Time"] = result["Turn Time"].round(2)
    return result


# =========================
# Beverage Processing
# Real header starts on row 4 of the sheet
# Uses Employee + % of Net Sales
# =========================
def process_beverage_file(file):
    if file.name.lower().endswith(".csv"):
        # CSV export already has its true header on the first row
        df = pd.read_csv(file)
    else:
        # Excel file's real header is on row 5
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

    df = df.dropna(subset=["Dine In Bev %"]).copy()
    df["Server"] = df["Server"].fillna("").astype(str).str.strip()
    df = df[df["Server"] != ""].copy()

    # Safety net in case a future export comes as 19 instead of 0.19
    non_null = df["Dine In Bev %"].dropna()
    if not non_null.empty and non_null.median() > 1:
        df["Dine In Bev %"] = df["Dine In Bev %"] / 100

    return df[["Server", "Dine In Bev %"]]

def process_all_beverage_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_beverage_file(file))
        except Exception as e:
            st.error(f"Beverage file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Server", "Dine In Bev %"])

    combined = pd.concat(all_rows, ignore_index=True)
    return combined.groupby("Server", as_index=False)["Dine In Bev %"].mean()


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
        combined = turn_df.copy() if combined.empty else pd.merge(combined, turn_df, on="Server", how="outer")

    if not beverage_df.empty:
        combined = beverage_df.copy() if combined.empty else pd.merge(combined, beverage_df, on="Server", how="outer")

    if not combined.empty:
        combined["Server"] = combined["Server"].fillna("").astype(str).str.strip()
        combined = combined[combined["Server"] != ""].copy()

        if "Tablet %" not in combined.columns:
            combined["Tablet %"] = pd.NA
        if "Turn Time" not in combined.columns:
            combined["Turn Time"] = pd.NA
        if "Dine In Bev %" not in combined.columns:
            combined["Dine In Bev %"] = pd.NA

        combined["All Green"] = combined.apply(
            lambda row: (
                is_tablet_green(row["Tablet %"])
                and is_turn_green(row["Turn Time"])
                and is_bev_green(row["Dine In Bev %"])
            ),
            axis=1,
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

        display_df = combined.copy()
        display_df["Tablet %"] = display_df["Tablet %"].apply(tablet_metric_with_dot)
        display_df["Turn Time"] = display_df["Turn Time"].apply(turn_metric_with_dot)
        display_df["Dine In Bev %"] = display_df["Dine In Bev %"].apply(beverage_metric_with_dot)
        display_df["All Green"] = display_df["All Green"].apply(lambda x: "⭐" if x else "")

        display_df = display_df[[
            "All Green",
            "Server",
            "Tablet %",
            "Turn Time",
            "Dine In Bev %",
        ]]

        sort_df = combined.copy()
        sort_df["All Green Sort"] = sort_df["All Green"].astype(int)
        sort_df["Tablet Sort"] = sort_df["Tablet %"].fillna(-1)

        sort_order = sort_df.sort_values(
            by=["All Green Sort", "Tablet Sort"],
            ascending=[False, False],
        ).index

        display_df = display_df.loc[sort_order].reset_index(drop=True)

        def highlight_all_green(row):
            if row["All Green"] == "⭐":
                return ["background-color: #e8f5e9"] * len(row)
            return [""] * len(row)

        styled_df = display_df.style.apply(highlight_all_green, axis=1)

        st.subheader("Combined Server Performance")
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        all_green_count = int(combined["All Green"].sum())
        st.caption(f"All Green servers: {all_green_count}")
    else:
        st.warning("No valid data could be processed from the uploaded files.")
else:
    st.info("Upload tablet files, turn files, beverage files, or any combination to begin.")
