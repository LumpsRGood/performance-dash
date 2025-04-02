import streamlit as st
import pandas as pd
import numpy as np
import re

st.set_page_config(page_title="Server Performance Dashboard", layout="wide")
st.markdown("<h1 style='text-align: center;'>📊 Server Performance Dashboard – v1.2.31</h1>", unsafe_allow_html=True)

# ========== Utilities ==========

def describe_change(curr, prev, is_pct=False):
    try:
        curr, prev = float(curr), float(prev)
        diff = curr - prev
        direction = "Improved" if diff > 0 else "Declined" if diff < 0 else "No Change"
        amount = f"{abs(diff):.2%}" if is_pct else f"{abs(diff):.2f}"
        return f"{direction} by {amount}"
    except:
        return "No Change"

def classify_ppa(val):
    if val >= 15.5: return "good"
    elif val >= 15.0: return "caution"
    return "bad"

def classify_discount(val):
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
    "good": "#126e24",
    "caution": "#a37c00",
    "bad": "#8b0000"
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

def load_sales(file):
    df = pd.read_excel(file, skiprows=4)
    df.columns = [c.strip().lower() for c in df.columns]
    df["location key"] = df["location key"].astype(str)
    return df

def load_turn(file):
    df = pd.read_excel(file)
    df.columns = [c.strip().lower() for c in df.columns]
    df.rename(columns={df.columns[7]: "turn time"}, inplace=True)
    return df[["employee", "turn time"]]

# ========== Step 1: Upload Sales Files ==========

st.subheader("📤 Upload Employee Sales Statistics File")

tw_sales = st.file_uploader("Upload This Week's Sales Data", type="xlsx", key="tw_sales")
lw_sales = st.file_uploader("Upload Last Week's Sales Data", type="xlsx", key="lw_sales")

if tw_sales and lw_sales:
    try:
        tw_df = load_sales(tw_sales)
        lw_df = load_sales(lw_sales)
        locations = tw_df["location key"].unique()
        st.session_state["sales_ready"] = True
        st.success(f"✅ {len(locations)} location(s) found in this week's sales data.")
    except Exception as e:
        st.error(f"❌ Error parsing sales files: {e}")
        st.stop()
else:
    st.info("Please upload both This Week's and Last Week's Sales Data to proceed.")
    st.stop()

# ========== Step 2: Upload Turn Time Files per Location ==========

st.subheader("📤 Upload Turn Time Files")

tw_turn_files = {}
lw_turn_files = {}

for loc in locations:
    st.markdown(f"#### Turn Time Files for Location: {loc}")
    tw_turn = st.file_uploader(f"This Week’s Turn Data for {loc}", type="xlsx", key=f"tw_turn_{loc}")
    lw_turn = st.file_uploader(f"Last Week’s Turn Data for {loc}", type="xlsx", key=f"lw_turn_{loc}")
    if tw_turn and lw_turn:
        tw_turn_files[loc] = tw_turn
        lw_turn_files[loc] = lw_turn

# ========== Step 3: Generate Dashboards ==========

if len(tw_turn_files) != len(locations):
    st.warning("Please upload both turn time files for all locations to generate dashboards.")
    st.stop()

st.markdown("### ✅ All files uploaded. Generating dashboards...")

try:
    for loc in locations:
        df_tw = tw_df[tw_df["location key"] == loc].copy()
        df_lw = lw_df[lw_df["location key"] == loc].copy()

        turn_tw = load_turn(tw_turn_files[loc])
        turn_lw = load_turn(lw_turn_files[loc])

        df_tw = pd.merge(df_tw, turn_tw, left_on="employee name", right_on="employee", how="left").drop(columns=["employee"])
        df_lw = pd.merge(df_lw, turn_lw, left_on="employee name", right_on="employee", how="left").drop(columns=["employee"])

        df_lw.set_index("employee name", inplace=True)
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
