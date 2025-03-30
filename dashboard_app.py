import streamlit as st
from PIL import Image
import os

st.set_page_config(page_title="Server Performance Dashboards", layout="wide")
st.title("📊 Server Performance Dashboard Generator")

st.markdown("Upload your TW and LW files, then view the generated dashboards below. This is a mockup to show layout and file previews.")

# File upload placeholders
st.header("1. Upload Files")
tw_sales = st.file_uploader("This Week - Sales File (.xlsx)", type=["xlsx"])
tw_turns = st.file_uploader("This Week - Turn Time Files (4 files)", type=["xlsx"], accept_multiple_files=True)
lw_sales = st.file_uploader("Last Week - Sales File (.xlsx)", type=["xlsx"])
lw_turns = st.file_uploader("Last Week - Turn Time Files (4 files)", type=["xlsx"], accept_multiple_files=True)

if st.button("Generate Dashboards"):
    st.success("Files received! Dashboards will be displayed below (mock view).")

    # Simulate the 4 dashboards from zip file
    st.header("2. Dashboard Results")
    dashboard_dir = "./dashboards"  # folder where mock dashboards are stored
    store_names = ["3231", "4445", "4456", "4463"]

    cols = st.columns(2)
    for i, store in enumerate(store_names):
        img_path = f"{dashboard_dir}/Store_{store}_Performance_Comparison.png"
        if os.path.exists(img_path):
            with cols[i % 2]:
                st.subheader(f"Store {store}")
                st.image(img_path, use_container_width=True)  # ✅ updated here
        else:
            with cols[i % 2]:
                st.subheader(f"Store {store}")
                st.warning("Preview not found.")

st.markdown("---")
st.caption("Built for Peachtree Partners IHOP – powered by Streamlit")
