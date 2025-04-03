import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io
from datetime import datetime

st.set_page_config(page_title="Server Performance Dashboard - v1.2.40", layout="wide")

# ---------- Utility Functions ---------- #
def parse_sales(file):
    try:
        df = pd.read_excel(file, header=4)
        df.columns = df.columns.str.strip().str.lower()
        df = df[~df["location"].astype(str).str.contains("Total|Copyright|Rosnet", case=False, na=False)]
        df = df[df["employee name"].notna() & df["location"].notna()]
        df = df[df["employee name"].str.upper().str.strip() != "STAFF, OLO"]
        df["location key"] = df["location"].astype(str).str.strip()
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

def style_lw_change(val, inverse=False):
    try:
        if isinstance(val, str):
            if "NEW" in val:
                return "background-color: #f9a825; color: black; font-weight: bold; text-align: center"
            elif "Improved" in val:
                return "background-color: #1b5e20; color: white; font-weight: bold; text-align: center"
            elif "Declined" in val:
                return "background-color: #c62828; color: white; font-weight: bold; text-align: center"
        return "text-align: center"
    except:
        return "text-align: center"

def ppa_bg(val):
    try:
        v = float(val)
        return "#1b5e20" if v >= 15.5 else "#c62828"
    except:
        return "#ffffff"

def disc_pct_bg(val):
    try:
        v = float(val.strip('%')) if isinstance(val, str) else float(val)
        return "#1b5e20" if v < 1.5 else "#c62828"
    except:
        return "#ffffff"

def bev_pct_bg(val):
    try:
        v = float(val.strip('%')) if isinstance(val, str) else float(val)
        return "#1b5e20" if v >= 18.5 else "#c62828"
    except:
        return "#ffffff"

def turn_time_bg(val):
    try:
        v = float(val)
        return "#1b5e20" if v <= 35 else "#c62828"
    except:
        return "#ffffff"

def extract_first_name(full_name):
    try:
        name = full_name.replace("🏆", "").replace("🔼", "").strip()
        if "," in name:
            return name.split(",")[1].strip().split()[0]
        return name.split()[0]
    except:
        return full_name

# ---------- Highlighting ---------- #
def is_top_performer(row):
    return (
        ppa_bg(row["PPA"]) == "#1b5e20"
        and disc_pct_bg(row["Discount %"]) == "#1b5e20"
        and bev_pct_bg(row["Beverage %"]) == "#1b5e20"
        and turn_time_bg(row["Turn Time"]) == "#1b5e20"
    )

def is_most_improved(row):
    try:
        return all([
            isinstance(row["+/- PPA LW"], str) and "Improved" in row["+/- PPA LW"],
            isinstance(row["+/- Discount % LW"], str) and "Improved" in row["+/- Discount % LW"],
            isinstance(row["+/- Beverage % LW"], str) and "Improved" in row["+/- Beverage % LW"],
            isinstance(row["+/- Turn Time LW"], str) and "Improved" in row["+/- Turn Time LW"]
        ])
    except:
        return False

# ---------- Snapshot Export ---------- #
def render_image_dashboard(display_df, location):
    fig, ax = plt.subplots(figsize=(12, 0.6 * len(display_df)))
    ax.axis("off")

    columns = list(display_df.columns)
    table_data = [columns] + display_df.values.tolist()
    table = ax.table(cellText=table_data, colLabels=None, loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)

    for i in range(len(table_data)):
        for j in range(len(columns)):
            cell = table[i, j]
            if i == 0:
                cell.set_text_props(weight="bold", color="white")
                cell.set_facecolor("#003366")
            else:
                val = table_data[i][j]
                col = columns[j].lower()
                color = "#ffffff"
                if col == "ppa":
                    color = ppa_bg(val)
                elif col == "discount %":
                    color = disc_pct_bg(val)
                elif col == "beverage %":
                    color = bev_pct_bg(val)
                elif col == "turn time":
                    color = turn_time_bg(val)
                elif col in ["+/- ppa lw", "+/- beverage % lw", "+/- turn time lw"]:
                    color = "#1b5e20" if "Improved" in str(val) else "#c62828" if "Declined" in str(val) else "#f9a825"
                elif col == "+/- discount % lw":
                    color = "#1b5e20" if "Improved" in str(val) else "#c62828" if "Declined" in str(val) else "#f9a825"
                cell.set_facecolor(color)
                cell.get_text().set_weight("bold")
                cell.get_text().set_color("white" if color not in ["#f9a825", "#ffffff"] else "black")

    plt.title(f"{location} – Performance Dashboard", fontsize=14, weight="bold")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    return buf

# ---------- Table Renderer ---------- #
def render_comparison_table(df, location):
    st.subheader(f"📍 {location} Performance Comparison")
    df = df.sort_values(by="ppa", ascending=False)

    cols = ["employee name", "ppa", "+/- ppa lw", "disc %", "+/- disc % lw",
            "bev %", "+/- bev % lw", "turn time", "+/- turn lw"]
    display_df = df[cols].copy()

    display_df.rename(columns={
        "employee name": "Employee Name", "ppa": "PPA",
        "+/- ppa lw": "+/- PPA LW", "disc %": "Discount %",
        "+/- disc % lw": "+/- Discount % LW", "bev %": "Beverage %",
        "+/- bev % lw": "+/- Beverage % LW", "turn time": "Turn Time",
        "+/- turn lw": "+/- Turn Time LW"
    }, inplace=True)

    display_df["PPA"] = display_df["PPA"].map("{:.2f}".format)
    display_df["Discount %"] = display_df["Discount %"].map("{:.2%}".format)
    display_df["Beverage %"] = display_df["Beverage %"].map("{:.2%}".format)
    display_df["Turn Time"] = display_df["Turn Time"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "n/a")

    top_names, improved_names = [], []
    for i, row in display_df.iterrows():
        name = display_df.at[i, "Employee Name"]
        badge = ""
        if is_top_performer(row):
            badge += "🏆"
            top_names.append(extract_first_name(name))
        if is_most_improved(row):
            badge += "🔼"
            improved_names.append(extract_first_name(name))
        if badge:
            display_df.at[i, "Employee Name"] = name + " " + badge

    if top_names:
        st.success("🏅 Top Performers: " + ", ".join(top_names))
    if improved_names:
        st.info("🔼 Most Improved: " + ", ".join(improved_names))

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    img_buf = render_image_dashboard(display_df, location)
    st.download_button(
        label="📸 Download Snapshot",
        data=img_buf,
        file_name=f"{location}_dashboard.png",
        mime="image/png"
    )

# ---------- Streamlit UI ---------- #
st.title("📊 Server Performance Dashboard – v1.2.40")

with st.expander("", expanded=True):
    st.markdown("### 📄 Upload this week's **Employee Sales Statistics**")
    this_week_file = st.file_uploader("", type="xlsx", key="tw_sales")
    st.markdown("### 📄 Upload last week's **Employee Sales Statistics**")
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

                        lw_index = merged_lw.set_index("employee name")
                        merged_tw["+/- ppa lw"] = merged_tw.apply(
                            lambda r: describe_change(r["ppa"], lw_index["ppa"].get(r["employee name"], None)), axis=1
                        )
                        merged_tw["+/- disc % lw"] = merged_tw.apply(
                            lambda r: describe_change(lw_index["disc %"].get(r["employee name"], None), r["disc %"], is_pct=True), axis=1
                        )
                        merged_tw["+/- bev % lw"] = merged_tw.apply(
                            lambda r: describe_change(r["bev %"], lw_index["bev %"].get(r["employee name"], None), is_pct=True), axis=1
                        )
                        merged_tw["+/- turn lw"] = merged_tw.apply(
                            lambda r: describe_change(lw_index["turn time"].get(r["employee name"], None), r["turn time"]), axis=1
                        )

                        render_comparison_table(merged_tw, loc)
