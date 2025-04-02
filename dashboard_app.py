import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="Server Performance Dashboard – v1.2.30")

st.markdown("## 📊 **Server Performance Dashboard – v1.2.30**")

# === File Uploads ===
st.markdown("### 📥 Upload Employee Sales Statistics")
sales_file = st.file_uploader("Upload the file named *Employee Sales Statistics*", type=["xlsx"])

st.markdown("### 📥 Upload Last Week's Sales Data")
last_week_file = st.file_uploader("Upload the file for *Last Week's Performance*", type=["xlsx"])

if sales_file and last_week_file:
    # === Load Data ===
    def load_data(file):
        df = pd.read_excel(file, skiprows=4)
        df.columns = df.columns.str.strip().str.lower()
        return df

    df_curr = load_data(sales_file)
    df_lw = load_data(last_week_file)

    # === Merge Data ===
    df_merged = pd.merge(
        df_curr,
        df_lw,
        on="employee name",
        suffixes=("", "_lw"),
        how="left"
    )

    # === Helpers ===
    def describe_change(curr, prev, is_pct=False):
        try:
            curr = float(curr)
            prev = float(prev)
            diff = curr - prev
            if abs(diff) < 0.0001:
                return "No Change"
            direction = "Improved" if diff > 0 else "Declined"
            val = f"{abs(diff):.2%}" if is_pct else f"{abs(diff):.2f}"
            return f"{direction} by {val}"
        except:
            return "No Change"

    def highlight_cell(val, good, caution, is_pct=False):
        try:
            v = float(str(val).replace('%', '').strip())
            color = "#1a7f37" if v >= good else "#ffcc00" if v >= caution else "#d62728"
            return f"background-color: {color}; color: white; font-weight: bold; text-align: center"
        except:
            return "text-align: center"

    def highlight_inverse(val, low_good, low_caution, is_pct=False):
        try:
            v = float(str(val).replace('%', '').strip())
            color = "#1a7f37" if v <= low_good else "#ffcc00" if v <= low_caution else "#d62728"
            return f"background-color: {color}; color: white; font-weight: bold; text-align: center"
        except:
            return "text-align: center"

    def highlight_trend(val, metric):
        try:
            if val == "No Change":
                return "background-color: #ffcc00; color: black; font-weight: bold; text-align: center"
            if "Improved" in val:
                if metric in ["ppa", "bev %"]:
                    return "background-color: #1a7f37; color: white; font-weight: bold; text-align: center"
                else:
                    return "background-color: #d62728; color: white; font-weight: bold; text-align: center"
            elif "Declined" in val:
                if metric in ["ppa", "bev %"]:
                    return "background-color: #d62728; color: white; font-weight: bold; text-align: center"
                else:
                    return "background-color: #1a7f37; color: white; font-weight: bold; text-align: center"
        except:
            return "text-align: center"

    # === Metrics ===
    df_merged["+/- ppa lw"] = df_merged.apply(
        lambda r: describe_change(r["ppa"], r["ppa_lw"]), axis=1
    )
    df_merged["+/- discount % lw"] = df_merged.apply(
        lambda r: describe_change(r["discount %"], r["discount %_lw"], is_pct=True), axis=1
    )
    df_merged["+/- beverage % lw"] = df_merged.apply(
        lambda r: describe_change(r["beverage %"], r["beverage %_lw"], is_pct=True), axis=1
    )
    df_merged["+/- turn time lw"] = df_merged.apply(
        lambda r: describe_change(r["turn time"], r["turn time_lw"]), axis=1
    )

    # === Final Columns ===
    display_cols = [
        "employee name",
        "ppa", "+/- ppa lw",
        "discount %", "+/- discount % lw",
        "beverage %", "+/- beverage % lw",
        "turn time", "+/- turn time lw"
    ]
    df_final = df_merged[display_cols]

    # === Styling ===
    styled_df = df_final.style.set_properties(**{"text-align": "center"})
    styled_df = styled_df.set_table_styles([
        {"selector": "th", "props": [("text-align", "center")]}
    ])

    # Apply conditional formatting
    styled_df = styled_df.applymap(lambda v: highlight_cell(v, 15.5, 15.0), subset=["ppa"])
    styled_df = styled_df.applymap(lambda v: highlight_inverse(v, 1.5, 2.0, is_pct=True), subset=["discount %"])
    styled_df = styled_df.applymap(lambda v: highlight_cell(v, 18.5, 18.0, is_pct=True), subset=["beverage %"])
    styled_df = styled_df.applymap(lambda v: highlight_inverse(v, 35, 39), subset=["turn time"])

    # Apply trend coloring
    styled_df = styled_df.applymap(lambda v: highlight_trend(v, "ppa"), subset=["+/- ppa lw"])
    styled_df = styled_df.applymap(lambda v: highlight_trend(v, "disc %"), subset=["+/- discount % lw"])
    styled_df = styled_df.applymap(lambda v: highlight_trend(v, "bev %"), subset=["+/- beverage % lw"])
    styled_df = styled_df.applymap(lambda v: highlight_trend(v, "turn time"), subset=["+/- turn time lw"])

    # === Display ===
    st.dataframe(styled_df, use_container_width=True)

else:
    st.info("⬆️ Please upload both the current and last week's Employee Sales Statistics Excel files to begin.")
