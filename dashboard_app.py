import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re

st.set_page_config(page_title="Server Performance Dashboard", layout="wide")

# ---------- Utility Functions ---------- #
def parse_sales(file):
    try:
        df = pd.read_excel(file, header=4)
        df.columns = df.columns.str.strip()
        df["Store ID"] = df["Location"].astype(str).str.extract(r"(\\d{4})")
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
    return pd.merge(sales_df, turn_df, on="Employee Name", how="left")

def compute_deltas(curr, prev, is_pct=False):
    try:
        curr = float(curr)
        prev = float(prev)
        delta = curr - prev
        return f"{delta:+.2%}" if is_pct else f"{delta:+.2f}"
    except:
        return "NEW"

def render_comparison_table(df, store_id):
    st.subheader(f"📍 Store {store_id} Performance Comparison")
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

    plt.title(f"Store {store_id} – Server Performance", fontsize=12, weight="bold", pad=10)
    st.pyplot(fig)

# ---------- Streamlit UI ---------- #
st.title("📊 Server Performance Dashboard")

st.header("Step 1: Upload Sales Data")
tw_file = st.file_uploader("Upload This Week's Sales Data", type=["xlsx"], key="tw_sales")
lw_file = st.file_uploader("Upload Last Week's Sales Data", type=["xlsx"], key="lw_sales")

if tw_file and lw_file:
    tw_sales_df = parse_sales(tw_file)
    lw_sales_df = parse_sales(lw_file)

    if not tw_sales_df.empty and not lw_sales_df.empty:
        stores_tw = tw_sales_df["Store ID"].dropna().unique()
        stores_lw = lw_sales_df["Store ID"].dropna().unique()
        common_stores = sorted(set(stores_tw) & set(stores_lw))

        st.success(f"Sales data uploaded! Found stores: {', '.join(common_stores)}")

        st.header("Step 2: Upload Turn Time Data Per Store")
        store_turn_data = {}

        for store_id in common_stores:
            st.subheader(f"Turn Time Files for Store {store_id}")
            tw_turn = st.file_uploader(f"This Week's Turn Data for Store {store_id}", type=["xlsx"], key=f"tw_turn_{store_id}")
            lw_turn = st.file_uploader(f"Last Week's Turn Data for Store {store_id}", type=["xlsx"], key=f"lw_turn_{store_id}")

            if tw_turn and lw_turn:
                store_turn_data[store_id] = {"tw": tw_turn, "lw": lw_turn}

        if store_turn_data:
            st.header("Step 3: Generate Dashboards")

            for store_id, files in store_turn_data.items():
                tw_turn_df = parse_turn(files["tw"])
                lw_turn_df = parse_turn(files["lw"])

                tw_sales = tw_sales_df[tw_sales_df["Store ID"] == store_id]
                lw_sales = lw_sales_df[lw_sales_df["Store ID"] == store_id]

                merged_tw = merge_data(tw_sales, tw_turn_df)
                merged_lw = merge_data(lw_sales, lw_turn_df)

                final_df = merged_tw.copy()
                final_df["+/- PPA LW"] = final_df.apply(lambda r: compute_deltas(r["PPA"], merged_lw.loc[r.name, "PPA"]), axis=1)
                final_df["+/- Disc % LW"] = final_df.apply(lambda r: compute_deltas(r["Discount %"], merged_lw.loc[r.name, "Discount %"], True), axis=1)
                final_df["+/- Bev % LW"] = final_df.apply(lambda r: compute_deltas(r["Beverage %"], merged_lw.loc[r.name, "Beverage %"], True), axis=1)
                final_df["+/- Turn LW"] = final_df.apply(lambda r: compute_deltas(r["Turn Time"], merged_lw.loc[r.name, "Turn Time"]), axis=1)

                render_comparison_table(final_df, store_id)

            st.success("All dashboards generated!")
        else:
            st.warning("Please upload Turn Time files for each store.")
    else:
        st.warning("Could not parse one or both sales files. Check formatting.")
else:
    st.info("Upload both This Week and Last Week sales files to begin.")
