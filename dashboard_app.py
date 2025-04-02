import streamlit as st
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title="Server Performance Dashboard", layout="wide")
st.markdown("<h1 style='text-align: center;'>📊 Server Performance Dashboard – v1.2.31</h1>", unsafe_allow_html=True)

# Utility functions
def describe_change(curr, prev, is_pct=False):
    try:
        curr, prev = float(curr), float(prev)
        diff = curr - prev
        direction = "Improved" if diff > 0 else "Declined" if diff < 0 else "No Change"
        amount = f"{abs(diff):.2%}" if is_pct else f"{abs(diff):.2f}"
        return f"{direction} by {amount}"
    except:
        return "No Change"

def extract_location_name(filename):
    match = re.search(r"(\d{4})[\-_ ]?([a-zA-Z ]+)", filename)
    if match:
        return f"{match.group(1)} - {match.group(2).strip()}"
    return filename.split(".")[0]

def classify_ppa(val):
    if val >= 15.5: return "good"
    elif val >= 15.0: return "caution"
    return "bad"

def classify_discount(val):  # lower = better
    if val < 1.5: return "good"
    elif val < 2.0: return "caution"
    return "bad"

def classify_beverage(val):
    if val >= 18.5: return "good"
    elif val >= 18.0: return "caution"
    return "bad"

def classify_turn_time(val):
    if val <= 35: return "good"
    elif val <= 39: return "caution"
    return "bad"

def classify_change(text, positive_good=True):
    if "Improved" in text:
        return "good" if positive_good else "bad"
    elif "Declined" in text:
        return "bad" if positive_good else "good"
    return "caution"

color_map = {
    "good": "#126e24",     # dark green
    "caution": "#a37c00",  # amber
    "bad": "#8b0000",      # dark red
}

def colorize(val, category, positive_good=True):
    if category in ["ppa", "discount %", "beverage %", "turn time"]:
        if pd.isna(val): return ""
        classifier = {
            "ppa": classify_ppa,
            "discount %": classify_discount,
            "beverage %": classify_beverage,
            "turn time": classify_turn_time
        }[category]
        level = classifier(val)
    else:
        level = classify_change(val, positive_good)
    return f"background-color: {color_map[level]}; color: white; font-weight: bold; text-align: center"

def render_comparison_table(df, location):
    st.markdown(f"<h3>📍 Location: {location} Performance Comparison</h3>", unsafe_allow_html=True)
    styled = df.style.format(precision=2)

    for col, positive_good in {
        "ppa": True, "+/- ppa lw": True,
        "discount %": False, "+/- discount % lw": False,
        "beverage %": True, "+/- beverage % lw": True,
        "turn time": False, "+/- turn time lw": False
    }.items():
        styled = styled.applymap(lambda v: colorize(v, col, positive_good), subset=[col])

    st.dataframe(styled, use_container_width=True, hide_index=True)

# Upload section
with st.expander("Step 1: Upload Sales and Turn Time Files", expanded=True):
    st.subheader("📤 Upload Employee Sales Statistics File")
    tw_sales = st.file_uploader("Upload This Week's Sales Data", type="xlsx", key="tw_sales")
    lw_sales = st.file_uploader("Upload Last Week's Sales Data", type="xlsx", key="lw_sales")

    st.subheader("📤 Upload Turn Time File")
    tw_turn = st.file_uploader("Upload This Week's Turn Time Data", type="xlsx", key="tw_turn")
    lw_turn = st.file_uploader("Upload Last Week's Turn Time Data", type="xlsx", key="lw_turn")

# Generate dashboards
if tw_sales and lw_sales and tw_turn and lw_turn:
    try:
        def load_sales(file):
            df = pd.read_excel(file, skiprows=4)
            df.columns = [c.strip().lower() for c in df.columns]
            df["location key"] = df["location key"].astype(str)
            return df

        tw_df = load_sales(tw_sales)
        lw_df = load_sales(lw_sales)

        def load_turn(file):
            df = pd.read_excel(file)
            df.columns = [c.strip().lower() for c in df.columns]
            df.rename(columns={df.columns[7]: "turn time"}, inplace=True)
            return df[["employee", "turn time"]]

        tw_turn_df = load_turn(tw_turn)
        lw_turn_df = load_turn(lw_turn)

        tw_merged = pd.merge(tw_df, tw_turn_df, left_on="employee name", right_on="employee", how="left").drop(columns=["employee"])
        lw_merged = pd.merge(lw_df, lw_turn_df, left_on="employee name", right_on="employee", how="left").drop(columns=["employee"])

        locations = tw_merged["location key"].unique()

        for loc in locations:
            df_tw = tw_merged[tw_merged["location key"] == loc].copy()
            df_lw = lw_merged[lw_merged["location key"] == loc].copy()
            df_lw.set_index("employee name", inplace=True)

            if df_tw.empty or df_lw.empty:
                continue

            df_tw = df_tw.set_index("employee name")
            df_merged = df_tw[["ppa", "disc %", "bev %", "turn time"]].copy()

            df_merged["+/- ppa lw"] = df_merged.apply(lambda r: describe_change(r["ppa"], df_lw.loc[r.name, "ppa"]), axis=1)
            df_merged["+/- discount % lw"] = df_merged.apply(lambda r: describe_change(r["disc %"], df_lw.loc[r.name, "disc %"], is_pct=True), axis=1)
            df_merged["+/- beverage % lw"] = df_merged.apply(lambda r: describe_change(r["bev %"], df_lw.loc[r.name, "bev %"], is_pct=True), axis=1)
            df_merged["+/- turn time lw"] = df_merged.apply(lambda r: describe_change(r["turn time"], df_lw.loc[r.name, "turn time"]), axis=1)

            df_merged["discount %"] = df_merged.pop("disc %")
            df_merged["beverage %"] = df_merged.pop("bev %")
            df_merged = df_merged.reset_index()

            render_comparison_table(df_merged, loc)

    except Exception as e:
        st.error(f"❌ Error processing files: {e}")
