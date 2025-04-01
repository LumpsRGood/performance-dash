import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
from io import BytesIO

# === Constants ===
STORE_NAMES = {
    "3231": "Prattville",
    "4445": "Montgomery",
    "4456": "Oxford",
    "4463": "Decatur"
}

# === Helper Functions ===
def parse_store_name(name):
    if pd.isna(name): return None
    for sid, sname in STORE_NAMES.items():
        if sname.upper() in str(name).upper():
            return sid
    return None

def clean_name(name):
    return str(name).strip().upper() if pd.notna(name) else None

def delta_color(metric, val):
    if pd.isna(val): return '#e0e0e0'
    if metric == "+/- PPA LW":
        return '#a8e6a3' if val > 0 else '#f7a8a8' if val < 0 else '#fff3a3'
    elif metric == "+/- Disc % LW":
        return '#a8e6a3' if val < 0 else '#f7a8a8' if val > 0 else '#fff3a3'
    elif metric == "+/- Bev % LW":
        return '#a8e6a3' if val > 0 else '#f7a8a8' if val < 0 else '#fff3a3'
    elif metric == "+/- Turn LW":
        return '#a8e6a3' if val < 0 else '#f7a8a8' if val > 0 else '#fff3a3'
    return '#fff3a3'

def base_color(metric, value):
    if pd.isna(value): return '#ffffff'
    if metric == "PPA":
        return '#a8e6a3' if value >= 15.5 else '#fff3a3' if value >= 15.0 else '#f7a8a8'
    elif metric == "Discount %":
        return '#a8e6a3' if value < 1.5 else '#fff3a3' if value <= 1.99 else '#f7a8a8'
    elif metric == "Beverage %":
        return '#a8e6a3' if value > 18.5 else '#fff3a3' if value >= 18.0 else '#f7a8a8'
    elif metric == "Turn Time":
        return '#a8e6a3' if value < 35 else '#fff3a3' if value <= 39 else '#f7a8a8'
    return '#ffffff'

def render_dashboard(df, store_id):
    fig, ax = plt.subplots(figsize=(14, 0.6 * len(df) + 1))
    ax.axis('off')
    columns = [
        ("Employee", None),
        ("PPA", "PPA"), ("+/- PPA LW", "+/- PPA LW"),
        ("Discount %", "Discount %"), ("+/- Disc % LW", "+/- Disc % LW"),
        ("Beverage %", "Beverage %"), ("+/- Bev % LW", "+/- Bev % LW"),
        ("Turn Time", "Turn Time"), ("+/- Turn LW", "+/- Turn LW")
    ]
    cell_w, cell_h = 1.4, 0.5
    start_x, start_y = 0.5, len(df) * cell_h + 1.2

    # Header
    for i, (col, _) in enumerate(columns):
        x, y = start_x + i * cell_w, start_y
        ax.add_patch(patches.Rectangle((x, y), cell_w, cell_h, color="#005792"))
        ax.text(x + cell_w/2, y + cell_h/2, col, color='white', ha='center', va='center', fontsize=10, weight='bold')

    # Rows
    for i, row in df.iterrows():
        y = start_y - (i + 1) * cell_h
        for j, (col, rule) in enumerate(columns):
            x = start_x + j * cell_w
            val = row[col]
            suffix = "%" if "Discount" in col or "Beverage" in col else ""
            if pd.isna(val):
                disp = "–"
            elif isinstance(val, float):
                disp = f"{val:.2f}{suffix}"
            else:
                disp = str(val)
            if "Employee" in col:
                color = "#f5f5f5"
            elif "+/-" in col:
                color = delta_color(col, val)
            else:
                color = base_color(col, val)
            ax.add_patch(patches.FancyBboxPatch((x, y), cell_w, cell_h, boxstyle="round,pad=0.1", edgecolor='white', facecolor=color))
            ax.text(x + cell_w/2, y + cell_h/2, disp, ha='center', va='center', fontsize=9, weight='bold')

    ax.set_xlim(0, start_x + len(columns) * cell_w)
    ax.set_ylim(0, start_y + 1.5)
    plt.title(f"📊 Store {store_id} – Performance Comparison", fontsize=16, pad=20, weight='bold')
    path = f"Store_{store_id}_TW_vs_LW_FinalColorFix.png"
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches='tight')
    plt.close()
    return path

# === Streamlit App ===
st.title("Peachtree Server Performance Dashboard")
st.markdown("Upload this week and last week’s Excel files below:")

# Uploads
tw_main = st.file_uploader("This Week: Sales (main)", type="xlsx", key="tw")
tw_turns = [st.file_uploader(f"This Week: Store {i} Turn Times", type="xlsx", key=f"tw{i}") for i in range(1, 5)]

lw_main = st.file_uploader("Last Week: Sales (main)", type="xlsx", key="lw")
lw_turns = [st.file_uploader(f"Last Week: Store {i} Turn Times", type="xlsx", key=f"lw{i}") for i in range(1, 5)]

if st.button("Generate Dashboards"):
    if not all([tw_main, lw_main] + tw_turns + lw_turns):
        st.warning("Please upload all required files.")
    else:
        def load_sales(file):
            raw = pd.read_excel(file, header=None)
            df = raw.iloc[5:, [0, 1, 4, 6, 11]]
            df.columns = ['Store Location', 'Employee', 'PPA', 'Discount %', 'Beverage %']
            df['Store'] = df['Store Location'].map(parse_store_name)
            df['Employee'] = df['Employee'].apply(clean_name)
            df = df.dropna(subset=['Store', 'Employee'])
            df[['PPA', 'Discount %', 'Beverage %']] = df[['PPA', 'Discount %', 'Beverage %']].apply(pd.to_numeric, errors='coerce')
            return df

        def load_turn(file):
            raw = pd.read_excel(file, header=None)
            store_line = str(raw.iloc[1, 0])
            store = store_line.split(":")[-1].strip()
            df = raw.iloc[5:, [0, 7]]
            df.columns = ['Employee', 'Turn Time']
            df['Store'] = store
            df['Employee'] = df['Employee'].apply(clean_name)
            df['Turn Time'] = pd.to_numeric(df['Turn Time'], errors='coerce')
            return df.dropna(subset=['Employee'])

        sales_tw = load_sales(tw_main)
        sales_lw = load_sales(lw_main)
        turn_tw = pd.concat([load_turn(f) for f in tw_turns])
        turn_lw = pd.concat([load_turn(f) for f in lw_turns])

        tw = pd.merge(sales_tw, turn_tw, on=["Store", "Employee"], how="inner")
        lw = pd.merge(sales_lw, turn_lw, on=["Store", "Employee"], how="inner")
        lw = lw.rename(columns={
            "PPA": "PPA_LW", "Discount %": "Discount %_LW",
            "Beverage %": "Beverage %_LW", "Turn Time": "Turn Time_LW"
        })

        df = pd.merge(tw, lw, on=["Store", "Employee"], how="inner")
        df["+/- PPA LW"] = df["PPA"] - df["PPA_LW"]
        df["+/- Disc % LW"] = df["Discount %"] - df["Discount %_LW"]
        df["+/- Bev % LW"] = df["Beverage %"] - df["Beverage %_LW"]
        df["+/- Turn LW"] = df["Turn Time"] - df["Turn Time_LW"]

        view = df[[
            "Store", "Employee", "PPA", "+/- PPA LW",
            "Discount %", "+/- Disc % LW",
            "Beverage %", "+/- Bev % LW",
            "Turn Time", "+/- Turn LW"
        ]].copy()

        st.success("Files received! Dashboards will be displayed below (mock view).")
        st.header("2. Dashboard Results")
        cols = st.columns(2)
        for i, (store_id, store_df) in enumerate(view.groupby("Store")):
            store_df = store_df.sort_values(by="PPA", ascending=False).reset_index(drop=True)
            img_path = render_dashboard(store_df, store_id)
            with cols[i % 2]:
                st.subheader(f"Store {store_id}")
                st.image(img_path, caption=f"Dashboard for Store {store_id}", use_container_width=True)
