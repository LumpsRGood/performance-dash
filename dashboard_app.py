import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import re
import io
from datetime import datetime

st.set_page_config(page_title="Server Performance Dashboard - v1.2.28", layout="wide")

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
    return pd.merge(sales_df, turn_df.drop(columns=[
        col for col in turn_df.columns if col in sales_df.columns and col != "employee name"
    ]), on="employee name", how="left")

def describe_change(curr, prev, is_pct=False):
    try:
        curr = float(curr)
        prev = float(prev)
        diff = curr - prev
        if diff > 0:
            return f"Improved by {abs(diff):.2%}" if is_pct else f"Improved by {abs(diff):.2f}"
        elif diff < 0:
            return f"Declined by {abs(diff):.2%}" if is_pct else f"Declined by {abs(diff):.2f}"
        else:
            return "No Change"
    except:
        return "NEW"

# ---------- Styling Rules ---------- #
def get_cell_color(val, good_thresh, warn_thresh, bad_thresh, inverse=False):
    try:
        v = float(val.replace('%', '').strip()) if isinstance(val, str) else float(val)
        if inverse:
            if v <= good_thresh:
                return '#1b5e20'
            elif v <= warn_thresh:
                return '#f9a825'
            else:
                return '#b71c1c'
        else:
            if v >= good_thresh:
                return '#1b5e20'
            elif v >= warn_thresh:
                return '#f9a825'
            else:
                return '#b71c1c'
    except:
        return '#b0bec5'

def download_table_as_png(df, title):
    cols = df.columns.tolist()
    fig, ax = plt.subplots(figsize=(len(cols) * 1.2, 0.6 * len(df) + 1.5))
    ax.axis("off")
    table_data = [cols] + df.values.tolist()
    table = ax.table(cellText=table_data, colLabels=None, loc='center')

    table.auto_set_font_size(False)
    table.set_fontsize(10)

    for i, row in enumerate(table_data):
        for j, val in enumerate(row):
            cell = table[i, j]
            if i == 0:
                cell.set_text_props(weight="bold", color="white")
                cell.set_facecolor("#003366")
            else:
                col_name = cols[j].lower()
                color = "white"
                bgcolor = "white"
                try:
                    if "ppa" in col_name:
                        bgcolor = get_cell_color(val, 15.5, 15.0, 0)
                        color = "white" if bgcolor != '#f9a825' else 'black'
                    elif "disc %" in col_name:
                        bgcolor = get_cell_color(val, 0, 1.5, 2.0, inverse=True)
                        color = "white" if bgcolor != '#f9a825' else 'black'
                    elif "bev %" in col_name:
                        bgcolor = get_cell_color(val, 18.5, 18.0, 0)
                        color = "white" if bgcolor != '#f9a825' else 'black'
                    elif "turn time" in col_name:
                        bgcolor = get_cell_color(val, 35, 39, 100, inverse=True)
                        color = "white" if bgcolor != '#f9a825' else 'black'
                    elif "+/-" in col_name:
                        if "Improved" in str(val):
                            bgcolor = '#1b5e20'
                        elif "Declined" in str(val):
                            bgcolor = '#b71c1c'
                        else:
                            bgcolor = '#f9a825'
                        color = "white" if bgcolor != '#f9a825' else 'black'
                except:
                    bgcolor = "white"
                cell.set_facecolor(bgcolor)
                cell.get_text().set_color(color)
                cell.get_text().set_fontweight("bold")
                cell.get_text().set_ha("center")

    plt.title(title, fontsize=14, weight="bold", pad=10)

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches="tight", dpi=200)
    buffer.seek(0)
    return buffer

# ---------- Dashboard Renderer ---------- #
def render_comparison_table(df, location):
    st.subheader(f"📍 Location: {location} Performance Comparison")
    df = df.sort_values(by="ppa", ascending=False)

    display_df = df[[
        "employee name", "ppa", "+/- ppa lw", "disc %", "+/- disc % lw",
        "bev %", "+/- bev % lw", "turn time", "+/- turn lw"
    ]].copy()

    display_df.columns = [
        "Employee Name", "PPA", "+/- PPA LW", "Discount %", "+/- Discount % LW",
        "Beverage %", "+/- Beverage % LW", "Turn Time", "+/- Turn Time LW"
    ]

    display_df["PPA"] = display_df["PPA"].map("{:.2f}".format)
    display_df["Discount %"] = display_df["Discount %"].map("{:.2%}".format)
    display_df["Beverage %"] = display_df["Beverage %"].map("{:.2%}".format)
    display_df["Turn Time"] = display_df["Turn Time"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "n/a")

    st.dataframe(display_df, use_container_width=True, hide_index=True, height=min(800, 45 * len(display_df) + 100))

    img_buffer = download_table_as_png(display_df, f"{location} – Performance Dashboard")
    st.download_button(
        label="📷 Download PNG",
        data=img_buffer,
        file_name=f"{location.replace(' ', '_')}_dashboard.png",
        mime="image/png"
    )

# ---------- UI ---------- #
st.title("📊 Server Performance Dashboard – v1.2.28")

with st.expander("Step 1: Upload Sales Files", expanded=True):
    st.markdown("### 📄 Upload the file labeled: **Employee Sales Statistics**")
    this_week_file = st.file_uploader("", type="xlsx", key="tw_sales")
    st.markdown("### 📄 Upload the file labeled: **Employee Sales Statistics (Last Week)**")
    last_week_file = st.file_uploader("", type="xlsx", key="lw_sales")

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

                        merged_tw["+/- ppa lw"] = merged_tw.apply(
                            lambda r: describe_change(r["ppa"], merged_lw.loc[r.name, "ppa"]), axis=1
                        )
                        merged_tw["+/- disc % lw"] = merged_tw.apply(
                            lambda r: describe_change(merged_lw.loc[r.name, "disc %"], r["disc %"], is_pct=True), axis=1
                        )
                        merged_tw["+/- bev % lw"] = merged_tw.apply(
                            lambda r: describe_change(r["bev %"], merged_lw.loc[r.name, "bev %"], is_pct=True), axis=1
                        )
                        merged_tw["+/- turn lw"] = merged_tw.apply(
                            lambda r: describe_change(merged_lw.loc[r.name, "turn time"], r["turn time"]), axis=1
                        )

                        render_comparison_table(merged_tw, loc)
