import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import os
import re

STORE_NAMES = {
    "3231": "Prattville",
    "4445": "Montgomery",
    "4456": "Oxford",
    "4463": "Decatur",
    "EASTERN BLVD": "4445"
}

def parse_store_name(name):
    if pd.isna(name): return None
    text = str(name).upper()
    match = re.search(r"\b(3231|4445|4456|4463)\b", text)
    if match:
        return match.group(1)
    for sid, sname in STORE_NAMES.items():
        if sname.upper() in text or sid in text:
            return sid
    for label, sid in STORE_NAMES.items():
        if label.upper() in text:
            return sid
    fallback = {"STORE 1": "3231", "STORE 2": "4445", "STORE 3": "4456", "STORE 4": "4463"}
    for k, v in fallback.items():
        if k in text:
            return v
    return None

def clean_name(name):
    return str(name).strip().upper() if pd.notna(name) else None

def load_sales(file):
    raw = pd.read_excel(file, header=None)
    df = raw.iloc[5:, [0, 1, 4, 6, 11]]
    df.columns = ['Store Location', 'Employee', 'PPA', 'Discount %', 'Beverage %']
    df['Store'] = df['Store Location'].map(parse_store_name).astype(str)
    df['Employee'] = df['Employee'].apply(clean_name)
    df = df.dropna(subset=['Store', 'Employee'])
    df[['PPA', 'Discount %', 'Beverage %']] = df[['PPA', 'Discount %', 'Beverage %']].apply(pd.to_numeric, errors='coerce')
    return df

def load_turn(file):
    raw = pd.read_excel(file, header=None)
    store_line = str(raw.iloc[1, 0])
    store = parse_store_name(store_line)
    df = raw.iloc[5:, [0, 7]]
    df.columns = ['Employee', 'Turn Time']
    df['Store'] = str(store)
    df['Employee'] = df['Employee'].apply(clean_name)
    df['Turn Time'] = pd.to_numeric(df['Turn Time'], errors='coerce')
    return df.dropna(subset=['Employee', 'Store'])

def merge_data(sales, turns):
    sales['Store'] = sales['Store'].astype(str)
    turns['Store'] = turns['Store'].astype(str)
    return pd.merge(sales, turns, on=['Store', 'Employee'], how='left')

def calculate_deltas(df_tw, df_lw):
    merged = pd.merge(df_tw, df_lw, on=['Store', 'Employee'], suffixes=('', '_LW'), how='left')
    for col in ['PPA', 'Discount %', 'Beverage %', 'Turn Time']:
        if col + '_LW' in merged.columns:
            merged[f'+/- {col} LW'] = merged[col] - merged[f'{col}_LW']
            merged[f'{col}_LW'] = merged[f'{col}_LW'].round(2)
        else:
            merged[f'+/- {col} LW'] = 'NEW'
    return merged

def get_color(value, metric):
    if value == 'NEW': return 'yellow'
    try:
        if metric == 'PPA':
            return 'green' if value >= 15.5 else 'yellow' if 15.0 <= value < 15.5 else 'red'
        if metric == 'Discount %':
            return 'green' if value < 1.5 else 'yellow' if value < 2.0 else 'red'
        if metric == 'Beverage %':
            return 'green' if value > 18.5 else 'yellow' if value >= 18.0 else 'red'
        if metric == 'Turn Time':
            return 'green' if value < 35 else 'yellow' if value < 40 else 'red'
    except:
        return 'white'

def get_delta_color(val):
    if val == 'NEW': return 'yellow'
    try:
        if val > 0:
            return 'green'
        elif val < 0:
            return 'red'
        else:
            return 'yellow'
    except:
        return 'white'

def render_table(df, store_num):
    store_name = STORE_NAMES.get(store_num, f"Store {store_num}")
    df = df[df['Store'] == store_num].copy()
    df = df.sort_values(by='PPA', ascending=False)
    fig, ax = plt.subplots(figsize=(14, 0.5 + 0.4 * len(df)))
    ax.axis('off')
    cols = ['Employee', 'PPA', '+/- PPA LW', 'Discount %', '+/- Discount % LW',
            'Beverage %', '+/- Beverage % LW', 'Turn Time', '+/- Turn Time LW']
    cell_data = df[cols].values.tolist()
    table = plt.table(cellText=cell_data,
                      colLabels=cols,
                      loc='center',
                      cellLoc='center',
                      colLoc='center')
    for i, row in enumerate(cell_data):
        for j, val in enumerate(row):
            color = 'white'
            if j == 1: color = get_color(val, 'PPA')
            elif j == 2: color = get_delta_color(val)
            elif j == 3: color = get_color(val, 'Discount %')
            elif j == 4: color = get_delta_color(val)
            elif j == 5: color = get_color(val, 'Beverage %')
            elif j == 6: color = get_delta_color(val)
            elif j == 7: color = get_color(val, 'Turn Time')
            elif j == 8: color = get_delta_color(val)
            table[(i+1, j)].set_facecolor(color)
            table[(i+1, j)].get_text().set_weight('bold')
    table.scale(1, 2.0)
    ax.set_title(f'Store {store_num} - Performance Comparison', fontsize=14, fontweight='bold')
    return fig

# === Streamlit App ===
st.title("Server Performance Dashboard")

tw_sales = st.file_uploader("This Week: Sales (main)", type="xlsx", key="tw_sales")
tw_turns = st.file_uploader("This Week: Turn Times", type="xlsx", accept_multiple_files=True)
lw_sales = st.file_uploader("Last Week: Sales (main)", type="xlsx", key="lw_sales")
lw_turns = st.file_uploader("Last Week: Turn Times", type="xlsx", accept_multiple_files=True)

if tw_sales and tw_turns and lw_sales and lw_turns:
    df_tw_sales = load_sales(tw_sales)
    df_tw_turns = pd.concat([load_turn(f) for f in tw_turns])
    df_lw_sales = load_sales(lw_sales)
    df_lw_turns = pd.concat([load_turn(f) for f in lw_turns])
    
    df_this = merge_data(df_tw_sales, df_tw_turns)
    df_last = merge_data(df_lw_sales, df_lw_turns)
    df_final = calculate_deltas(df_this, df_last)

    st.subheader("2. Dashboard Results")
    for store_id in sorted(df_final['Store'].unique()):
        st.write(f"**Store {store_id}**")
        fig = render_table(df_final, store_id)
        st.pyplot(fig)
