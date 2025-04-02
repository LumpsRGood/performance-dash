import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re

st.set_page_config(page_title="Server Performance Dashboard - v1.2.2", layout="wide")

# ---------- Utility Functions ---------- #
def parse_sales(file):
    try:
        df = pd.read_excel(file, header=4)  # Start reading from row 5 (0-indexed header=4)
        df.columns = df.columns.str.strip().str.lower()

        # Strip out summary/footer rows
        df = df[~df["location"].astype(str).str.contains("Total|Copyright|Rosnet", case=False, na=False)]
        df = df[df["employee name"].notna()]
        df = df[df["location"].notna()]

        # Add normalized key
        df["location key"] = df["location"].astype(str).str.strip()

        # Preview loaded columns (debugging aid)
        st.caption("Sales Data Columns: " + ", ".join(df.columns))
        return df
    except Exception as e:
        st.error(f"Error reading sales file: {e}")
        return pd.DataFrame()

def parse_turn(file):
    try:
        df = pd.read_excel(file, header=4)  # Row 5 contains headers
        df.columns = df.columns.str.strip().str.lower()
        if "employee name" not in df.columns:
            st.error("❌ 'Employee Name' column missing in Turn Time file.")
            return pd.DataFrame()
        for col in df.columns:
            if col.strip().lower() == "avg mins":
                df.rename(columns={col: "turn time"}, inplace=True)
        return df
    except Exception as e:
        st.error(f"Error reading turn file: {e}")
        return pd.DataFrame()

def merge_data(sales_df, turn_df):
    if "employee name" not in sales_df.columns or "employee name" not in turn_df.columns:
        st.error("❌ 'Employee Name' column is missing from one of the files.")
        return pd.DataFrame()
    merged = pd.merge(sales_df, turn_df.drop(columns=[col for col in turn_df.columns if col in sales_df.columns and col != "employee name"]), on="employee name", how="left")
    return merged

def compute_deltas(curr, prev, is_pct=False):
    try:
        curr = float(curr)
        prev = float(prev)
        delta = curr - prev
        return f"{delta:+.2%}" if is_pct else f"{delta:+.2f}"
    except:
        return "NEW"

def style_deltas(val):
    try:
        if isinstance(val, str) and "NEW" in val:
            return "background-color: lightgray"
        v = float(val.strip('%+'))
        if v > 0:
            return "background-color: lightgreen"
        elif v < 0:
            return "background-color: salmon"
        else:
            return "background-color: lightgray"
    except:
        return ""

def style_ppa(val):
    try:
        v = float(val)
        if v >= 15.5:
            return "background-color: lightgreen"
        elif 15.0 <= v < 15.5:
            return "background-color: orange"
        else:
            return "background-color: salmon"
    except:
        return ""

def render_comparison_table(df, location):
    st.subheader(f"📍 Location: {location} Performance Comparison")
    df = df.sort_values(by="ppa", ascending=False)

    cols = ["employee name", "ppa", "+/- ppa lw", "disc %", "+/- disc % lw",
            "bev %", "+/- bev % lw", "turn time", "+/- turn lw"]

    display_df = df[cols].copy()

    display_df.rename(columns={
        "employee name": "Employee",
        "ppa": "PPA",
        "+/- ppa lw": "+/- PPA LW",
        "disc %": "Disc %",
        "+/- disc % lw": "+/- Disc % LW",
        "bev %": "Bev %",
        "+/- bev % lw": "+/- Bev % LW",
        "turn time": "Turn Time",
        "+/- turn lw": "+/- Turn Time LW"
    }, inplace=True)

    display_df["PPA"] = display_df["PPA"].map("{:.2f}".format)
    display_df["Disc %"] = display_df["Disc %"].map("{:.2%}".format)
    display_df["Bev %"] = display_df["Bev %"].map("{:.2%}".format)
    display_df["Turn Time"] = display_df["Turn Time"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "n/a")

    st.dataframe(
        display_df.style
            .applymap(style_deltas, subset=["+/- PPA LW"])
            .applymap(style_ppa, subset=["PPA"]),
        use_container_width=True
    )

# ---------- Streamlit UI ---------- #
st.title("📊 Server Performance Dashboard – v1.2.2")

# (Remaining UI unchanged)
