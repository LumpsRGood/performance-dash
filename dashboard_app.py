import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os

# Create output directory if it doesn't exist
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

# Delta color logic
def delta_color(val, inverse=False):
    if pd.isna(val): return '#e0e0e0'
    if inverse:
        if val < 0: return '#a8e6a3'
        elif val > 0: return '#f7a8a8'
    else:
        if val > 0: return '#a8e6a3'
        elif val < 0: return '#f7a8a8'
    return '#fff3a3'

# Generate a dummy dashboard per store for demo (replace with real logic)
def generate_store_dashboard(store_code, df):
    fig, ax = plt.subplots(figsize=(12, 2))
    ax.axis('off')

    # Dummy content for now
    ax.text(0.5, 0.5, f"Dashboard for Store {store_code}", fontsize=20, ha='center')

    output_path = os.path.join(output_dir, f"{store_code}.png")
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()
    return output_path

# Streamlit interface
st.set_page_config(layout="wide")
st.title("IHOP Performance Dashboard")

uploaded_files = st.file_uploader("Upload all required Excel files", accept_multiple_files=True)

if uploaded_files:
    if st.button("Generate Dashboards"):
        store_codes = ["3231", "4445", "4456", "4463"]
        image_paths = {}

        for store in store_codes:
            # Replace with your real logic later (mock for now)
            dummy_df = pd.DataFrame()
            img_path = generate_store_dashboard(store, dummy_df)
            image_paths[store] = img_path

        st.success("Files received! Dashboards generated below.")

        st.markdown("## 2. Dashboard Results")
        cols = st.columns(2)
        for idx, store in enumerate(store_codes):
            with cols[idx % 2]:
                st.markdown(f"### Store {store}")
                if image_paths.get(store):
                    st.image(image_paths[store], use_column_width=True)
                else:
                    st.warning("Preview not found.")
