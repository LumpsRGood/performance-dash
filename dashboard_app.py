import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("📊 Server Performance Dashboard – v1.2.30")

# ===================== FILE UPLOAD =====================
st.markdown("### 📥 Upload Employee Sales Statistics File")
sales_file = st.file_uploader("Upload This Week's Sales Data", type=["xlsx"])

st.markdown("### 📥 Upload Turn Time File")
turn_file = st.file_uploader("Upload This Week's Turn Time Data", type=["xlsx"])

if sales_file and turn_file:
    # ===================== LOAD DATA =====================
    sales_df = pd.read_excel(sales_file, skiprows=4)
    turn_df = pd.read_excel(turn_file, skiprows=4)

    # Normalize column names
    sales_df.columns = sales_df.columns.str.strip().str.lower()
    turn_df.columns = turn_df.columns.str.strip().str.lower()

    # Rename for consistency
    sales_df.rename(columns={
        "employee name": "employee",
        "ppa": "ppa",
        "disc %": "discount %",
        "bev %": "beverage %"
    }, inplace=True)

    turn_df.rename(columns={
        "employee name": "employee",
        "avg mins": "turn time"
    }, inplace=True)

    # Merge data
    df_merged = pd.merge(sales_df, turn_df[["employee", "turn time"]], on="employee", how="left")

    # Simulated last week data for testing
    df_merged["ppa lw"] = df_merged["ppa"] - [0.5, 0.3, -0.2]
    df_merged["discount % lw"] = df_merged["discount %"] + [0.1, -0.5, 0.0]
    df_merged["beverage % lw"] = df_merged["beverage %"] - [0.5, 0.3, -0.2]
    df_merged["turn time lw"] = df_merged["turn time"] + [-2, 1, -1.5]

    # ===================== CHANGE TEXT =====================
    def describe_change(curr, prev, is_pct=False):
        try:
            curr = float(curr)
            prev = float(prev)
            diff = curr - prev
            if diff > 0:
                direction = "Improved"
            elif diff < 0:
                direction = "Declined"
            else:
                direction = "No Change"
            amount = f"{abs(diff):.2%}" if is_pct else f"{abs(diff):.2f}"
            return f"{direction} by {amount}"
        except:
            return "No Change"

    df_merged["+/- ppa lw"] = df_merged.apply(lambda r: describe_change(r["ppa"], r["ppa lw"]), axis=1)
    df_merged["+/- discount % lw"] = df_merged.apply(lambda r: describe_change(r["discount %"], r["discount % lw"], is_pct=True), axis=1)
    df_merged["+/- beverage % lw"] = df_merged.apply(lambda r: describe_change(r["beverage %"], r["beverage % lw"], is_pct=True), axis=1)
    df_merged["+/- turn time lw"] = df_merged.apply(lambda r: describe_change(r["turn time lw"], r["turn time"]), axis=1)

    # ===================== FORMATTING =====================
    def color_cell(val, metric, lw=False):
        try:
            if isinstance(val, str) and ("Improved" in val or "Declined" in val):
                is_improve = "Improved" in val
                is_decline = "Declined" in val
                is_nochange = "No Change" in val
                if lw:
                    if metric in ["ppa", "beverage %"]:
                        return "background-color: darkgreen; color: white;" if is_improve else (
                            "background-color: darkred; color: white;" if is_decline else
                            "background-color: goldenrod; color: black;"
                        )
                    elif metric in ["discount %", "turn time"]:
                        return "background-color: darkred; color: white;" if is_improve else (
                            "background-color: darkgreen; color: white;" if is_decline else
                            "background-color: goldenrod; color: black;"
                        )
            else:
                v = float(val)
                if metric == "ppa":
                    if v >= 15.5:
                        return "background-color: darkgreen; color: white;"
                    elif 15.0 <= v < 15.5:
                        return "background-color: goldenrod; color: black;"
                    else:
                        return "background-color: darkred; color: white;"
                elif metric == "discount %":
                    if v < 0.015:
                        return "background-color: darkgreen; color: white;"
                    elif 0.015 <= v < 0.02:
                        return "background-color: goldenrod; color: black;"
                    else:
                        return "background-color: darkred; color: white;"
                elif metric == "beverage %":
                    if v >= 0.185:
                        return "background-color: darkgreen; color: white;"
                    elif 0.18 <= v < 0.185:
                        return "background-color: goldenrod; color: black;"
                    else:
                        return "background-color: darkred; color: white;"
                elif metric == "turn time":
                    if v <= 35:
                        return "background-color: darkgreen; color: white;"
                    elif 36 <= v <= 39:
                        return "background-color: goldenrod; color: black;"
                    else:
                        return "background-color: darkred; color: white;"
        except:
            return ""
        return ""

    # ===================== BUILD TABLE =====================
    display_cols = [
        "employee", "ppa", "+/- ppa lw",
        "discount %", "+/- discount % lw",
        "beverage %", "+/- beverage % lw",
        "turn time", "+/- turn time lw"
    ]

    styled = df_merged[display_cols].style

    for col in display_cols:
        if col in ["employee"]:
            continue
        base_col = col.replace("+/- ", "").replace(" lw", "")
        lw_flag = "+/-" in col
        styled = styled.applymap(lambda v: color_cell(v, base_col, lw=lw_flag), subset=[col])

    # ===================== DISPLAY =====================
    st.dataframe(styled, use_container_width=True)
