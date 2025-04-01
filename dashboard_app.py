import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import os
import re

# Constants
STORE_NAMES = {
    "3231": "Prattville",
    "4445": "Montgomery",
    "4456": "Oxford",
    "4463": "Decatur",
    "EASTERN BLVD": "4445"
}

COLOR_RULES = {
    "PPA": lambda val: "green" if val >= 15.5 else "yellow" if val >= 15.0 else "red",
    "Discount %": lambda val: "green" if val < 1.5 else "yellow" if val < 2.0 else "red",
    "Beverage %": lambda val: "green" if val > 18.5 else "yellow" if val >= 18.0 else "red",
    "Turn Time": lambda val: "green" if val < 35 else "yellow" if val < 40 else "red",
    "+/- PPA LW": lambda val: "green" if val > 0 else "red" if val < 0 else "yellow",
    "+/- Disc % LW": lambda val: "green" if val < 0 else "red" if val > 0 else "yellow",
    "+/- Bev % LW": lambda val: "green" if val > 0 else "red" if val < 0 else "yellow",
    "+/- Turn LW": lambda val: "green" if val < 0 else "red" if val > 0 else "yellow",
}

def parse_store_name(name):
    if pd.isna(name):
        return None
    text = str(name).upper()
    match = re.search(r"\b(3231|4445|4456|4463)\b", text)
    if match:
        return match.group(1)
    for sid, sname in STORE_NAMES.items():
        if sname.upper() in text or sid in text:
            return sid
    for label, sid in STORE_NAMES.items():
        if label.upper() in text:
            return sid
    fallback = {"STORE 1": "3231", "STORE 2": "4445", "STORE 3": "4456", "STORE 4": "4463"}
    for k, v in fallback.items():
        if k in text:
            return v
    return None

def read_turn_file(file):
    try:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()
        store_id = parse_store_name(df.iloc[1, 0])
        df = df.iloc[3:].copy()
        df.columns = df.iloc[0]
        df = df[1:]
        df.columns = df.columns.str.strip()
        df["Store"] = store_id
        return df
    except Exception as e:
        st.error(f"Error reading turn file: {e}")
        return pd.DataFrame()

def load_data(file, is_turn=False):
    try:
        if is_turn:
            return read_turn_file(file)
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()
        df["Store"] = df["Location"].apply(parse_store_name)
        return df
    except Exception as e:
        st.error(f"Error reading sales file: {e}")
        return pd.DataFrame()

def merge_and_prepare(tw_sales, tw_turns, lw_sales, lw_turns):
    df = pd.merge(tw_sales, tw_turns, on=["Employee Name", "Store"], how="left")
    df_lw = pd.merge(lw_sales, lw_turns, on=["Employee Name", "Store"], how="left")

    df_all = pd.merge(df, df_lw, on=["Employee Name", "Store"], how="left", suffixes=("", " LW"))

    def format_change(curr, prev, is_pct=False):
        try:
            if pd.isna(curr) or pd.isna(prev):
                return "NEW"
            delta = float(curr) - float(prev)
            if is_pct:
                return f"{delta:+.2%}"
            return f"{delta:+.2f}"
        except:
            return "NEW"

    df_all["+/- PPA LW"] = df_all.apply(lambda r: format_change(r["PPA"], r["PPA LW"]), axis=1)
    df_all["+/- Disc % LW"] = df_all.apply(lambda r: format_change(r["Discount %"], r["Discount % LW"], True), axis=1)
    df_all["+/- Bev % LW"] = df_all.apply(lambda r: format_change(r["Beverage %"], r["Beverage % LW"], True), axis=1)
    df_all["+/- Turn LW"] = df_all.apply(lambda r: format_change(r["Turn Time"], r["Turn Time LW"]), axis=1)

    return df_all

def get_color(val, col):
    if val == "NEW":
        return "yellow"
    try:
        val = float(str(val).replace('%', '').replace('+', ''))
        return COLOR_RULES[col](val)
    except:
        return "white"

def render_table(df, store_id):
    df = df[df["Store"] == store_id].copy()
    df = df.sort_values(by="PPA", ascending=False)

    cols = ["Employee Name", "PPA", "+/- PPA LW", "Discount %", "+/- Disc % LW",
            "Beverage %", "+/- Bev % LW", "Turn Time", "+/- Turn LW"]

    fig, ax = plt.subplots(figsize=(12, 0.6 * len(df)))
    ax.axis("off")

    table_data = [cols] + df[cols].values.tolist()
    table = ax.table(cellText=table_data, colLabels=None, loc='center')

    table.auto_set_font_size(False)
    table.set_fontsize(10)

    for i in range(len(table_data)):
        for j in range(len(cols)):
            cell = table[i, j]
            if i == 0:
                cell.set_text_props(weight="bold", color="white")
                cell.set_facecolor("#003366")
            else:
                color = get_color(table_data[i][j], cols[j])
                cell.set_facecolor(color)
                cell.get_text().set_weight("bold")

    title = f"Store {STORE_NAMES.get(store_id, store_id)} – Performance Comparison"
    plt.title(title, fontsize=12, weight="bold", pad=10)
    st.pyplot(fig)

# Streamlit App
st.title("📊 Server Performance Dashboard")

with st.expander("Upload Files", expanded=True):
    tw_file = st.file_uploader("This Week: Sales Data", type=["xlsx"], key="tw_sales")
    lw_file = st.file_uploader("Last Week: Sales Data", type=["xlsx"], key="lw_sales")
    tw_turns_files = st.file_uploader("This Week: All Turn Times", type=["xlsx"], key="tw_turns", accept_multiple_files=True)
    lw_turns_files = st.file_uploader("Last Week: All Turn Times", type=["xlsx"], key="lw_turns", accept_multiple_files=True)

if tw_file and lw_file and tw_turns_files and lw_turns_files:
    tw_sales = load_data(tw_file)
    lw_sales = load_data(lw_file)
    tw_turns = pd.concat([read_turn_file(f) for f in tw_turns_files], ignore_index=True)
    lw_turns = pd.concat([read_turn_file(f) for f in lw_turns_files], ignore_index=True)

    final_df = merge_and_prepare(tw_sales, tw_turns, lw_sales, lw_turns)
    stores = final_df["Store"].dropna().unique()

    st.success("Files received! Dashboards will be displayed below.")
    st.header("📍 Dashboard Results")

    for store_id in stores:
        st.subheader(f"Store {STORE_NAMES.get(store_id, store_id)}")
        render_table(final_df, store_id)
else:
    st.warning("Please upload all 4 required files to proceed.")
