import pandas as pd
import streamlit as st
import numpy as np

st.set_page_config(page_title="FOH Performance Dashboard", layout="wide")

st.title("📊 FOH Performance Dashboard (Tablet + Turn)")

# =========================
# Upload Section
# =========================
tablet_file = st.file_uploader("Upload Tablet Usage CSV", type=["csv"])
turn_file = st.file_uploader("Upload Turn Time File", type=["csv", "xlsx"])

# =========================
# Helper: Name Cleanup
# =========================
def clean_name(name):
    if pd.isna(name):
        return ""
    name = str(name).strip().lower()
    if "," in name:
        parts = name.split(",")
        name = parts[1].strip() + " " + parts[0].strip()
    return name.title()

# =========================
# Tablet Processing
# =========================
def process_tablet(file):
    df = pd.read_csv(file)

    df.columns = df.columns.str.replace("\n", " ").str.strip()

    df = df.rename(columns={
        "Device Orders Report": "Device Orders",
        "Staff Customer": "Server",
        "Base (Including Disc.)": "Base"
    })

    df["Device Orders"] = df["Device Orders"].str.strip().str.lower()
    df["Device Orders"] = df["Device Orders"].replace({
        "handheld": "handheld",
        "hand held": "handheld",
        "pos": "pos",
        "pos terminal": "pos"
    })

    df["Device Orders"] = df["Device Orders"].str.extract(r"(handheld|pos)", expand=False).fillna("unknown")
    df["Base"] = pd.to_numeric(df["Base"], errors="coerce").fillna(0)

    grouped = df.groupby(["Server", "Device Orders"])["Base"].sum().unstack(fill_value=0)

    if "handheld" not in grouped.columns:
        grouped["handheld"] = 0
    if "pos" not in grouped.columns:
        grouped["pos"] = 0

    grouped = grouped.rename(columns={
        "handheld": "Handheld Sales",
        "pos": "POS Sales"
    }).reset_index()

    grouped["Tablet %"] = grouped["Handheld Sales"] / (grouped["Handheld Sales"] + grouped["POS Sales"])
    grouped["Tablet %"] = grouped["Tablet %"].fillna(0)

    grouped["Server"] = grouped["Server"].apply(clean_name)

    return grouped[["Server", "Tablet %"]]

# =========================
# Turn Time Processing
# =========================
def process_turn(file):
    if file.name.endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)

    df.columns = df.columns.str.strip()

    def pick_col(df, keywords):
        for col in df.columns:
            for key in keywords:
                if key in col.lower():
                    return col
        return None

    col_open = pick_col(df, ["opened"])
    col_close = pick_col(df, ["closed"])
    col_service = pick_col(df, ["service"])
    col_server = pick_col(df, ["created by", "server", "employee"])

    if not all([col_open, col_close, col_service, col_server]):
        st.error("Missing required columns in turn file")
        return pd.DataFrame()

    df[col_open] = pd.to_datetime(df[col_open], errors="coerce")
    df[col_close] = pd.to_datetime(df[col_close], errors="coerce")

    eat = df[df[col_service].astype(str).str.contains("eat in", case=False, na=False)].copy()

    eat["Turn Time"] = (eat[col_close] - eat[col_open]).dt.total_seconds() / 60
    eat = eat.dropna(subset=["Turn Time"])

    result = eat.groupby(col_server)["Turn Time"].mean().reset_index()
    result = result.rename(columns={col_server: "Server"})

    result["Server"] = result["Server"].apply(clean_name)

    return result

# =========================
# Main Processing
# =========================
if tablet_file and turn_file:

    tablet_df = process_tablet(tablet_file)
    turn_df = process_turn(turn_file)

    if not tablet_df.empty and not turn_df.empty:

        combined = pd.merge(tablet_df, turn_df, on="Server", how="outer")

        # =========================
        # Flags
        # =========================
        combined["Tablet %"] = combined["Tablet %"].fillna(0)
        combined["Turn Time"] = combined["Turn Time"].fillna(0)

        def tablet_color(x):
            if x >= 0.8:
                return "🟢"
            elif x >= 0.6:
                return "🟡"
            return "🔴"

        def turn_color(x):
            if x < 35:
                return "🟢"
            elif x <= 39:
                return "🟡"
            return "🔴"

        combined["Tablet Score"] = combined["Tablet %"].apply(tablet_color)
        combined["Turn Score"] = combined["Turn Time"].apply(turn_color)

        # =========================
        # Display
        # =========================
        combined["Tablet %"] = (combined["Tablet %"] * 100).round(2)

        combined = combined.sort_values(by="Tablet %", ascending=False)

        st.subheader("📋 Combined Server Performance")
        st.dataframe(combined, use_container_width=True)

    else:
        st.warning("One of the datasets failed to process.")

else:
    st.info("Upload both Tablet and Turn files to begin.")
