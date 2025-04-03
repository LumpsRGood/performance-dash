import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Server Performance Dashboard - v1.2.39", layout="wide")

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
                return (
                    "background-color: #1b5e20; color: white; font-weight: bold; text-align: center"
                    if not inverse else
                    "background-color: #1b5e20; color: white; font-weight: bold; text-align: center"
                )
            elif "Declined" in val:
                return (
                    "background-color: #c62828; color: white; font-weight: bold; text-align: center"
                    if not inverse else
                    "background-color: #c62828; color: white; font-weight: bold; text-align: center"
                )
        return "text-align: center"
    except:
        return "text-align: center"

def ppa_bg(val):
    try:
        v = float(val)
        if v >= 15.5:
            return "background-color: #1b5e20; color: white; text-align: center; font-weight: bold"
        else:
            return "background-color: #c62828; color: white; text-align: center; font-weight: bold"
    except:
        return "text-align: center; font-weight: bold"

def disc_pct_bg(val):
    try:
        v = float(val.strip('%')) if isinstance(val, str) else float(val)
        if v < 1.5:
            return "background-color: #1b5e20; color: white; text-align: center; font-weight: bold"
        else:
            return "background-color: #c62828; color: white; text-align: center; font-weight: bold"
    except:
        return "text-align: center; font-weight: bold"

def bev_pct_bg(val):
    try:
        v = float(val.strip('%')) if isinstance(val, str) else float(val)
        if v >= 18.5:
            return "background-color: #1b5e20; color: white; text-align: center; font-weight: bold"
        else:
            return "background-color: #c62828; color: white; text-align: center; font-weight: bold"
    except:
        return "text-align: center; font-weight: bold"

def turn_time_bg(val):
    try:
        v = float(val)
        if v <= 35:
            return "background-color: #1b5e20; color: white; text-align: center; font-weight: bold"
        else:
            return "background-color: #c62828; color: white; text-align: center; font-weight: bold"
    except:
        return "text-align: center"

def extract_first_name(full_name):
    try:
        name = full_name.replace("🏆", "").replace("🔼", "").strip()
        if "," in name:
            return name.split(",")[1].strip().split()[0]
        return name.split()[0]
    except:
        return full_name

# ---------- Highlighting Functions ---------- #
def is_top_performer(row):
    return (
        ppa_bg(row["PPA"]).startswith("background-color: #1b5e20")
        and disc_pct_bg(row["Discount %"]).startswith("background-color: #1b5e20")
        and bev_pct_bg(row["Beverage %"]).startswith("background-color: #1b5e20")
        and turn_time_bg(row["Turn Time"]).startswith("background-color: #1b5e20")
    )

def is_most_improved(row):
    try:
        return all([
            isinstance(row["+/- PPA LW"], str) and row["+/- PPA LW"].startswith("Improved"),
            isinstance(row["+/- Discount % LW"], str) and row["+/- Discount % LW"].startswith("Improved"),
            isinstance(row["+/- Beverage % LW"], str) and row["+/- Beverage % LW"].startswith("Improved"),
            isinstance(row["+/- Turn Time LW"], str) and row["+/- Turn Time LW"].startswith("Improved"),
        ])
    except:
        return False

def highlight_top_performer(row):
    if is_top_performer(row):
        return ["background-color: #2e7d32; color: white; font-weight: bold"] * len(row)
    else:
        return [""] * len(row)

def highlight_most_improved(row):
    if is_most_improved(row):
        return ["background-color: #1565c0; color: white; font-weight: bold"] * len(row)
    else:
        return [""] * len(row)

# ---------- Render Table ---------- #
def render_comparison_table(df, location):
    import streamlit as st
    import streamlit.components.v1 as components

    st.markdown(f"<div id='dashboard-{location}'>", unsafe_allow_html=True)

    # Placeholder: Actual dashboard rendering logic goes here
    st.write(f"Dashboard content for {location}")

    export_html = """
<div style="text-align: right; margin-top: 10px;">
  <button onclick="downloadDashboard('dashboard-{location}')" style="padding: 6px 12px; font-size: 14px;">Download PNG</button>
</div>
<script src="https://html2canvas.hertzen.com/dist/html2canvas.min.js"></script>
<script>
function downloadDashboard(id) {
  html2canvas(document.getElementById(id)).then(canvas => {
    let link = document.createElement('a');
    link.download = id + '.png';
    link.href = canvas.toDataURL();
    link.click();
  });
}
</script>
    """.format(location=location)

    components.html(export_html, height=120)
    st.markdown("</div>", unsafe_allow_html=True)