
import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Server Performance Dashboard - v1.2.39", layout="wide")

st.title("📊 Weekly Performance Dashboard")

uploaded_files = st.file_uploader(
    "Upload Turn and Sales Excel Files",
    type=["xlsx"],
    accept_multiple_files=True
)

turn_files = []
sales_files = []

for f in uploaded_files:
    fname = f.name.lower()
    if "turn" in fname:
        turn_files.append(f)
    elif "sales" in fname:
        sales_files.append(f)
    else:
        st.warning(f"⚠️ File '{f.name}' not recognized as sales or turn. Skipping.")

# Sort by modified date or name if needed — assume most recent is this week
# Here we just show them for now
st.markdown("### 📂 Detected Files")

def list_files(label, file_list):
    if file_list:
        st.write(f"**{label}:**")
        for file in file_list:
            st.write(f"📄 {file.name}")
    else:
        st.write(f"**{label}:** None found.")

list_files("Turn Files", turn_files)
list_files("Sales Files", sales_files)

# You can now use: turn_files[0], sales_files[0] as "this week"
# And optionally turn_files[1], sales_files[1] as "last week"
if turn_files:
    st.success(f"Ready to parse turn file: {turn_files[0].name}")
    # df_turn = parse_turn(turn_files[0])

if sales_files:
    st.success(f"Ready to parse sales file: {sales_files[0].name}")
    # df_sales = parse_sales(sales_files[0])
