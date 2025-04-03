
import streamlit as st
import pandas as pd
from openpyxl import load_workbook

st.set_page_config(page_title="Server Performance Dashboard - v1.2.39", layout="wide")
st.title("📊 Weekly Performance Dashboard")

# Upload main sales file
sales_file = st.file_uploader("📥 Upload the MAIN Sales Summary file", type=["xlsx"])

if sales_file:
    st.success(f"✅ Loaded sales file: {sales_file.name}")
    
    # Example mock sales_df from uploaded file (replace with your parser)
    sales_df = pd.DataFrame({
        "Location": ["5430", "5450", "5461"],
        "Store Name": ["Atlanta", "Chicago", "Dallas"]
    })

    st.markdown("### 🏬 Upload Turn Files for Each Store")
    uploaded_turn_files = {}

    for _, row in sales_df.iterrows():
        loc = row["Location"]
        store = row["Store Name"]
        uploaded_turn_files[loc] = st.file_uploader(f"Turn File for {store} ({loc})", type=["xlsx"], key=loc)

    def is_valid_turn_file(file):
        try:
            wb = load_workbook(file, read_only=True, data_only=True)
            ws = wb.active
            cell = ws["A1"].value
            header = str(cell).strip() if cell is not None else ""
            if "Server Table Turn Stats" in header:
                return True, header
            return False, header
        except Exception as e:
            return False, f"Error reading A1: {e}"

    all_uploaded = True
    for loc, file in uploaded_turn_files.items():
        if file:
            valid, msg = is_valid_turn_file(file)
            if valid:
                st.success(f"📄 {file.name} looks good (Turn Stats file detected)")
            else:
                all_uploaded = False
                st.error(f"⛔ {file.name} may be invalid: {msg}")
        else:
            all_uploaded = False
            st.info(f"Waiting on turn file for location {loc}...")

    if all_uploaded:
        st.success("✅ All valid turn files uploaded. Proceed to parsing and dashboard rendering.")
        # for loc, file in uploaded_turn_files.items():
        #     df_turn = parse_turn(file)
        #     render_dashboard(sales_df, df_turn, location=loc)
    else:
        st.warning("⬆️ Please upload all required and valid turn files to continue.")
