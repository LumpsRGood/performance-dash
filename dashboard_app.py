import streamlit as st
import pandas as pd

st.set_page_config(page_title="Server Performance Dashboard", layout="wide")
st.markdown("<h1 style='text-align: center;'>📊 Server Performance Dashboard – v1.2.28</h1>", unsafe_allow_html=True)

# ========== Helpers ==========

def describe_change(curr, prev, is_pct=False):
    try:
        curr = float(curr)
        prev = float(prev)
        diff = curr - prev
        direction = "Improved" if diff > 0 else "Declined" if diff < 0 else "No Change"
        amount = f"{abs(diff):.2%}" if is_pct else f"{abs(diff):.2f}"
        return f"{direction} by {amount}"
    except:
        return "No Change"

def get_color_class(val, col_name):
    if col_name == "ppa":
        if val >= 15.5: return "background-color: #145A32; color: white; font-weight: bold"
        elif val >= 15.0: return "background-color: #9A7D0A; color: white; font-weight: bold"
        else: return "background-color: #922B21; color: white; font-weight: bold"
    elif col_name == "discount %":
        if val < 1.5: return "background-color: #145A32; color: white; font-weight: bold"
        elif val < 2.0: return "background-color: #9A7D0A; color: white; font-weight: bold"
        else: return "background-color: #922B21; color: white; font-weight: bold"
    elif col_name == "beverage %":
        if val >= 18.5: return "background-color: #145A32; color: white; font-weight: bold"
        elif val >= 18.0: return "background-color: #9A7D0A; color: white; font-weight: bold"
        else: return "background-color: #922B21; color: white; font-weight: bold"
    elif col_name == "turn time":
        if val <= 35: return "background-color: #145A32; color: white; font-weight: bold"
        elif val <= 39: return "background-color: #9A7D0A; color: white; font-weight: bold"
        else: return "background-color: #922B21; color: white; font-weight: bold"
    return ""

def get_change_color(text, positive_good=True):
    if "Improved" in text:
        return "background-color: #145A32; color: white; font-weight: bold" if positive_good else "background-color: #922B21; color: white; font-weight: bold"
    elif "Declined" in text:
        return "background-color: #922B21; color: white; font-weight: bold" if positive_good else "background-color: #145A32; color: white; font-weight: bold"
    else:
        return "background-color: #9A7D0A; color: white; font-weight: bold"

def style_table(df):
    styled = df.style
    for col in df.columns:
        if col in ["ppa", "discount %", "beverage %", "turn time"]:
            styled = styled.applymap(lambda v: get_color_class(v, col), subset=[col])
        elif col == "+/- ppa lw":
            styled = styled.applymap(lambda v: get_change_color(v, True), subset=[col])
        elif col == "+/- discount % lw":
            styled = styled.applymap(lambda v: get_change_color(v, False), subset=[col])
        elif col == "+/- beverage % lw":
            styled = styled.applymap(lambda v: get_change_color(v, True), subset=[col])
        elif col == "+/- turn time lw":
            styled = styled.applymap(lambda v: get_change_color(v, False), subset=[col])
    return styled

# ========== Uploads ==========

st.subheader("📤 Upload This Week's Sales Data (Employee Sales Statistics File)")
tw_file = st.file_uploader("This Week", type=["xlsx"], key="thisweek")

st.subheader("📤 Upload Last Week's Sales Data")
lw_file = st.file_uploader("Last Week", type=["xlsx"], key="lastweek")

if tw_file and lw_file:
    try:
        df_tw = pd.read_excel(tw_file, skiprows=4)
        df_lw = pd.read_excel(lw_file, skiprows=4)

        df_tw.columns = [c.lower().strip() for c in df_tw.columns]
        df_lw.columns = [c.lower().strip() for c in df_lw.columns]

        # Use lowercase column names for consistency
        df_lw = df_lw.set_index("employee name")
        df_tw = df_tw.set_index("employee name")

        df_merged = df_tw[["ppa", "disc %", "bev %", "turn time"]].copy()

        df_merged["+/- ppa lw"] = df_merged.apply(lambda r: describe_change(r["ppa"], df_lw.loc[r.name, "ppa"]), axis=1)
        df_merged["+/- discount % lw"] = df_merged.apply(lambda r: describe_change(r["disc %"], df_lw.loc[r.name, "disc %"], is_pct=True), axis=1)
        df_merged["+/- beverage % lw"] = df_merged.apply(lambda r: describe_change(r["bev %"], df_lw.loc[r.name, "bev %"], is_pct=True), axis=1)
        df_merged["+/- turn time lw"] = df_merged.apply(lambda r: describe_change(r["turn time"], df_lw.loc[r.name, "turn time"]), axis=1)

        df_merged["discount %"] = df_merged.pop("disc %")
        df_merged["beverage %"] = df_merged.pop("bev %")
        df_merged = df_merged.reset_index()

        st.dataframe(style_table(df_merged), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"⚠️ Error processing files: {e}")
else:
    st.info("Please upload both This Week and Last Week sales Excel files to begin.")
