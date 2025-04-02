import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import re

st.set_page_config(page_title="Server Performance Dashboard - v1.2.1", layout="wide")

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
            return "color: gray"
        v = float(val.strip('%+'))
        if v > 0:
            return "color: green"
        elif v < 0:
            return "color: red"
        else:
            return "color: black"
    except:
        return ""

def style_ppa(val):
    try:
        v = float(val)
        if v >= 15.5:
            return "color: green"
        elif 15.0 <= v < 15.5:
            return "color: orange"
        else:
            return "color: red"
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
        "+/- ppa lw": "Δ PPA",
        "disc %": "Disc %",
        "+/- disc % lw": "Δ Disc %",
        "bev %": "Bev %",
        "+/- bev % lw": "Δ Bev %",
        "turn time": "Turn Time",
        "+/- turn lw": "Δ Turn Time"
    }, inplace=True)

    display_df["PPA"] = display_df["PPA"].map("{:.2f}".format)
    display_df["Disc %"] = display_df["Disc %"].map("{:.2%}".format)
    display_df["Bev %"] = display_df["Bev %"].map("{:.2%}".format)
    display_df["Turn Time"] = display_df["Turn Time"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "n/a")

    st.dataframe(
        display_df.style
            .applymap(style_deltas, subset=["Δ PPA"])
            .applymap(style_ppa, subset=["PPA"]),
        use_container_width=True
    )

# ---------- Streamlit UI ---------- #
st.title("📊 Server Performance Dashboard – v1.2.1")

st.header("Step 1: Upload Sales Data")
tw_file = st.file_uploader("Upload This Week's Sales Data", type=["xlsx"], key="tw_sales")
lw_file = st.file_uploader("Upload Last Week's Sales Data", type=["xlsx"], key="lw_sales")

if tw_file and lw_file:
    tw_sales_df = parse_sales(tw_file)
    lw_sales_df = parse_sales(lw_file)

    if not tw_sales_df.empty and not lw_sales_df.empty:
        locations_tw = tw_sales_df["location key"].dropna().unique()
        locations_lw = lw_sales_df["location key"].dropna().unique()
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

                tw_sales = tw_sales_df[tw_sales_df["location key"] == loc]
                lw_sales = lw_sales_df[lw_sales_df["location key"] == loc]

                merged_tw = merge_data(tw_sales, tw_turn_df)
                merged_lw = merge_data(lw_sales, lw_turn_df)

                if merged_tw.empty or merged_lw.empty:
                    st.warning(f"Skipping {loc} due to missing or invalid data.")
                    continue

                final_df = merged_tw.copy()

                required_sales_cols = ["ppa", "disc %", "bev %"]
                required_turn_cols = ["turn time"]

                missing_sales = [col for col in required_sales_cols if col not in merged_tw.columns or col not in merged_lw.columns]
                missing_turn = [col for col in required_turn_cols if col not in merged_tw.columns or col not in merged_lw.columns]

                if missing_sales or missing_turn:
                    missing_all = missing_sales + missing_turn
                    st.warning(f"Skipping {loc} due to missing columns: {', '.join(missing_all)}")
                    continue

                merged_lw_dict = merged_lw.set_index("employee name").to_dict(orient="index")

                final_df["+/- ppa lw"] = final_df["employee name"].apply(
                    lambda name: compute_deltas(
                        final_df.loc[final_df["employee name"] == name, "ppa"].values[0],
                        merged_lw_dict.get(name, {}).get("ppa")
                    )
                )

                final_df["+/- disc % lw"] = final_df["employee name"].apply(
                    lambda name: compute_deltas(
                        final_df.loc[final_df["employee name"] == name, "disc %"].values[0],
                        merged_lw_dict.get(name, {}).get("disc %"), True
                    )
                )

                final_df["+/- bev % lw"] = final_df["employee name"].apply(
                    lambda name: compute_deltas(
                        final_df.loc[final_df["employee name"] == name, "bev %"].values[0],
                        merged_lw_dict.get(name, {}).get("bev %"), True
                    )
                )

                final_df["+/- turn lw"] = final_df["employee name"].apply(
                    lambda name: compute_deltas(
                        final_df.loc[final_df["employee name"] == name, "turn time"].values[0],
                        merged_lw_dict.get(name, {}).get("turn time")
                    )
                )

                render_comparison_table(final_df, loc)

            st.success("All dashboards generated!")
        else:
            st.warning("Please upload Turn Time files for each location.")
    else:
        st.warning("Could not parse one or both sales files. Check formatting.")
else:
    st.info("Upload both This Week and Last Week sales files to begin.")
