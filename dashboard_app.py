
import streamlit as st

st.set_page_config(page_title="Server Performance Dashboard - UI Upload Step", layout="wide")
st.title("📊 Step 2: Upload Turn Time Files")

stores = [
    {"name": "Holland", "id": "holl"},
    {"name": "Lima OH", "id": "lima"},
    {"name": "Perrysburg OH", "id": "perrysburg"},
]

for store in stores:
    store_name = store["name"]
    store_id = store["id"]

    st.markdown(f"### 📍 {store_name}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"<div style='text-align:center; font-weight:bold; font-size:18px;'>This Week Turn File</div>", unsafe_allow_html=True)
        tw_file = st.file_uploader("", type=["xlsx"], key=f"{store_id}_tw")
        if tw_file:
            st.success(f"✅ Uploaded: {tw_file.name}")

    with col2:
        st.markdown(f"<div style='text-align:center; font-weight:bold; font-size:18px;'>Last Week Turn File</div>", unsafe_allow_html=True)
        lw_file = st.file_uploader("", type=["xlsx"], key=f"{store_id}_lw")
        if lw_file:
            st.success(f"✅ Uploaded: {lw_file.name}")
