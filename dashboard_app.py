import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re

st.set_page_config(page_title="Server Performance Dashboard - v1.0.5", layout="wide")

# ---------- Utility Functions ---------- #
def parse_sales(file):
    try:
        df = pd.read_excel(file, header=4)
        df.columns = df.columns.str.strip()
        df = df[~df["Location"].astype(str).str.contains("Total|Copyright|Rosnet", case=False, na=False)]
        df = df[df["Employee Name"].notna()]
        df = df[df["Location"].notna()]
        df["Location Key"] = df["Location"].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Error reading sales file: {e}")
        return pd.DataFrame()

def parse_turn(file):
    try:
        df = pd.read_excel(file, skiprows=5)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error reading turn file: {e}")
        return pd.DataFrame()

def merge_data(sales_df, turn_df):
    if "Employee Name" not in sales_df.columns or "Employee Name" not in turn_df.columns:
        st.error("❌ 'Employee Name' column is missing from one of the files.")
        return pd.DataFrame()
    return pd.merge(sales_df, turn_df, on="Employee Name", how="left")

def compute_deltas(curr, prev, is_pct=False):
    try:
        curr = float(curr)
        prev = float(prev)
        delta = curr - prev
        return f"{delta:+.2%}" if is_pct else f"{delta:+.2f}"
    except:
        return "NEW"

def render_comparison_table(df, location):
    st.subheader(f"📍 Location: {location} Performance Comparison")
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
                cell.set_facecolor("white")
                cell.get_text().set_weight("bold")

    plt.title(f"{location} – Server Performance", fontsize=12, weight="bold", pad=10)
    st.pyplot(fig)

# ---------- Streamlit UI ---------- #
st.title("📊 Server Performance Dashboard – v1.0.5")

st.header("Step 1: Upload Sales Data")
tw_file = st.file_uploader("Upload This Week's Sales Data", type=["xlsx"], key="tw_sales")
lw_file = st.file_uploader("Upload Last Week's Sales Data", type=["xlsx"], key="lw_sales")

if tw_file and lw_file:
    tw_sales_df = parse_sales(tw_file)
    lw_sales_df = parse_sales(lw_file)

    if not tw_sales_df.empty and not lw_sales_df.empty:
        locations_tw = tw_sales_df["Location Key"].dropna().unique()
        locations_lw = lw_sales_df["Location Key"].dropna().unique()
        all_locations = sorted(set(locations_tw) | set(locations_lw))

        with st.expander("🔍 Preview Detected Locations"):
            st.write(pd.DataFrame({
                "This Week": pd.Series(locations_tw),
                "Last Week": pd.Series(locations_lw)
            }))

        st.success(f"Sales data uploaded! Found locations: {', '.join(all_locations)}")

        st.header("Step 2: Upload Turn Time Data Per Location")
        location_turn_data = {}

        for loc in all_locations:
            st.subheader(f"Turn Time Files for Location: {loc}")
            tw_turn = st.file_uploader(f"This Week's Turn Data for {loc}", type=["xlsx"], key=f"tw_turn_{loc}")
            lw_turn = st.file_uploader(f"Last Week's Turn Data for {loc}", type=["xlsx"], key=f"lw_turn_{loc}")

            if tw_turn and lw_turn:
                location_turn_data[loc] = {"tw": tw_turn, "lw": lw_turn}

        if location_turn_data:
            st.header("Step 3: Generate Dashboards")

            for loc, files in location_turn_data.items():
                tw_turn_df = parse_turn(files["tw"])
                lw_turn_df = parse_turn(files["lw"])

                tw_sales = tw_sales_df[tw_sales_df["Location Key"] == loc]
                lw_sales = lw_sales_df[lw_sales_df["Location Key"] == loc]

                merged_tw = merge_data(tw_sales, tw_turn_df)
                merged_lw = merge_data(lw_sales, lw_turn_df)

                final_df = merged_tw.copy()
                final_df["+/- PPA LW"] = final_df.apply(lambda r: compute_deltas(r["PPA"], merged_lw.loc[r.name, "PPA"]), axis=1)
                final_df["+/- Disc % LW"] = final_df.apply(lambda r: compute_deltas(r["Discount %"], merged_lw.loc[r.name, "Discount %"], True), axis=1)
                final_df["+/- Bev % LW"] = final_df.apply(lambda r: compute_deltas(r["Beverage %"], merged_lw.loc[r.name, "Beverage %"], True), axis=1)
                final_df["+/- Turn LW"] = final_df.apply(lambda r: compute_deltas(r["Turn Time"], merged_lw.loc[r.name, "Turn Time"]), axis=1)

                render_comparison_table(final_df, loc)

            st.success("All dashboards generated!")
        else:
            st.warning("Please upload Turn Time files for each location.")
    else:
        st.warning("Could not parse one or both sales files. Check formatting.")
else:
    st.info("Upload both This Week and Last Week sales files to begin.")
