import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re

st.set_page_config(page_title="Server Performance Dashboard - v1.2.17", layout="wide")

# ---------- Utility Functions ---------- #
def parse_sales(file):
    try:
        df = pd.read_excel(file, header=4)
        df.columns = df.columns.str.strip().str.lower()

        df = df[~df["location"].astype(str).str.contains("Total|Copyright|Rosnet", case=False, na=False)]
        df = df[df["employee name"].notna() & df["location"].notna()]
        df["location key"] = df["location"].astype(str).str.strip()

        st.caption("Sales Data Columns: " + ", ".join(df.columns))
        return df
    except Exception as e:
        st.error(f"Error reading sales file: {e}")
        return pd.DataFrame()

def parse_turn(file):
    try:
        df = pd.read_excel(file, header=4)
        df.columns = df.columns.str.strip().str.lower()
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

def style_deltas_text(val):
    try:
        if isinstance(val, str) and "NEW" in val:
            return "color: gray; font-weight: bold; text-align: center"
        v = float(val.strip('%+'))
        if v > 0:
            return "color: #2e7d32; font-weight: bold; text-align: center"
        elif v < 0:
            return "color: #c62828; font-weight: bold; text-align: center"
        else:
            return "color: gray; font-weight: bold; text-align: center"
    except:
        return "text-align: center; font-weight: bold"

def style_ppa_text(val):
    try:
        v = float(val)
        if v >= 15.5:
            return "color: #2e7d32; font-weight: bold; text-align: center"
        elif 15.0 <= v < 15.5:
            return "color: #fbc02d; font-weight: bold; text-align: center"
        else:
            return "color: #c62828; font-weight: bold; text-align: center"
    except:
        return "text-align: center; font-weight: bold"

def render_comparison_table(df, location):
    st.subheader(f"📍 Location: {location} Performance Comparison")
    df = df.sort_values(by="ppa", ascending=False)

    cols = ["employee name", "ppa", "+/- ppa lw", "disc %", "+/- disc % lw",
            "bev %", "+/- bev % lw", "turn time", "+/- turn lw"]

    display_df = df[cols].copy()

    display_df.rename(columns={
        "employee name": "Employee Name",
        "ppa": "PPA",
        "+/- ppa lw": "+/- PPA LW",
        "disc %": "Discount %",
        "+/- disc % lw": "+/- Discount % LW",
        "bev %": "Beverage %",
        "+/- bev % lw": "+/- Beverage % LW",
        "turn time": "Turn Time",
        "+/- turn lw": "+/- Turn Time LW"
    }, inplace=True)

    display_df["PPA"] = display_df["PPA"].map("{:.2f}".format)
    display_df["Discount %"] = display_df["Discount %"].map("{:.2%}".format)
    display_df["Beverage %"] = display_df["Beverage %"].map("{:.2%}".format)
    display_df["Turn Time"] = display_df["Turn Time"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "n/a")

    styles = display_df.style \
        .applymap(style_deltas_text, subset=["+/- PPA LW", "+/- Discount % LW", "+/- Beverage % LW", "+/- Turn Time LW"]) \
        .applymap(style_ppa_text, subset=["PPA"]) \
        .set_properties(subset=display_df.columns, **{
            'text-align': 'center',
            'font-weight': 'bold',
            'font-size': '14px'
        }) \
        .set_table_styles([
            {'selector': 'thead th', 'props': [('text-align', 'center'), ('font-weight', 'bold')]},
            {'selector': 'tbody td', 'props': [('text-align', 'center'), ('font-weight', 'bold')]}
        ], overwrite=False)

    st.dataframe(styles, use_container_width=True)

# ---------- Streamlit UI ---------- #
st.title("📊 Server Performance Dashboard – v1.2.17")

with st.expander("Step 1: Upload Sales Files", expanded=True):
    this_week_file = st.file_uploader("Upload This Week's Sales Data", type="xlsx", key="tw_sales")
    last_week_file = st.file_uploader("Upload Last Week's Sales Data", type="xlsx", key="lw_sales")

if this_week_file and last_week_file:
    sales_tw = parse_sales(this_week_file)
    sales_lw = parse_sales(last_week_file)

    if not sales_tw.empty and not sales_lw.empty:
        locations = sorted(sales_tw["location key"].unique())
        st.success(f"✅ Sales data uploaded! Found locations: {', '.join(locations)}")

        st.subheader("Step 2: Upload Turn Time Files")
        turn_data = {}
        for loc in locations:
            st.markdown(f"**📍 {loc}**")
            col1, col2 = st.columns(2)
            with col1:
                tw_file = st.file_uploader(f"This Week - {loc}", type="xlsx", key=f"tw_{loc}")
            with col2:
                lw_file = st.file_uploader(f"Last Week - {loc}", type="xlsx", key=f"lw_{loc}")
            turn_data[loc] = {"this_week": tw_file, "last_week": lw_file}

        if st.button("Step 3: Generate Dashboards"):
            for loc in locations:
                tw_file = turn_data[loc]["this_week"]
                lw_file = turn_data[loc]["last_week"]
                if tw_file and lw_file:
                    tw_df = parse_turn(tw_file)
                    lw_df = parse_turn(lw_file)
                    if not tw_df.empty and not lw_df.empty:
                        merged_tw = merge_data(sales_tw[sales_tw["location key"] == loc], tw_df)
                        merged_lw = merge_data(sales_lw[sales_lw["location key"] == loc], lw_df)

                        merged_tw["+/- ppa lw"] = merged_tw.apply(lambda r: compute_deltas(r["ppa"], merged_lw.loc[r.name, "ppa"]), axis=1)
                        merged_tw["+/- disc % lw"] = merged_tw.apply(lambda r: compute_deltas(r["disc %"], merged_lw.loc[r.name, "disc %"], True), axis=1)
                        merged_tw["+/- bev % lw"] = merged_tw.apply(lambda r: compute_deltas(r["bev %"], merged_lw.loc[r.name, "bev %"], True), axis=1)
                        merged_tw["+/- turn lw"] = merged_tw.apply(lambda r: compute_deltas(r["turn time"], merged_lw.loc[r.name, "turn time"]), axis=1)

                        render_comparison_table(merged_tw, loc)
