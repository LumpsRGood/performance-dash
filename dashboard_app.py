import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(layout="wide", page_title="Server Performance Dashboard – v1.2.29")
st.title("📊 Server Performance Dashboard – v1.2.29")

def highlight_metric(val, metric):
    styles = {
        'green': 'background-color: #145A32; color: white; font-weight: bold;',
        'yellow': 'background-color: #9A7D0A; color: white; font-weight: bold;',
        'red': 'background-color: #922B21; color: white; font-weight: bold;',
        '': ''
    }
    try:
        if metric == "ppa":
            val = float(val)
            if val >= 15.50:
                return styles['green']
            elif 15.00 <= val < 15.50:
                return styles['yellow']
            else:
                return styles['red']

        elif metric == "+/- ppa lw":
            return styles['green'] if "Improved" in val else styles['red'] if "Declined" in val else styles['yellow']

        elif metric == "discount %":
            val = float(val.strip('%'))
            if val < 1.5:
                return styles['green']
            elif 1.5 <= val <= 1.99:
                return styles['yellow']
            else:
                return styles['red']

        elif metric == "+/- discount % lw":
            return styles['green'] if "Declined" in val else styles['red'] if "Improved" in val else styles['yellow']

        elif metric == "beverage %":
            val = float(val.strip('%'))
            if val >= 18.5:
                return styles['green']
            elif 18.0 <= val < 18.5:
                return styles['yellow']
            else:
                return styles['red']

        elif metric == "+/- beverage % lw":
            return styles['green'] if "Improved" in val else styles['red'] if "Declined" in val else styles['yellow']

        elif metric == "turn time":
            val = float(val)
            if val <= 35:
                return styles['green']
            elif 36 <= val <= 39:
                return styles['yellow']
            else:
                return styles['red']

        elif metric == "+/- turn time lw":
            return styles['green'] if "Improved" in val else styles['red'] if "Declined" in val else styles['yellow']

    except:
        return ''

def describe_change(curr, prev, is_pct=False):
    try:
        curr = float(curr)
        prev = float(prev)
        diff = curr - prev
        if diff == 0:
            return "No Change"
        direction = "Improved" if diff > 0 else "Declined"
        amount = f"{abs(diff):.2%}" if is_pct else f"{abs(diff):.2f}"
        return f"{direction} by {amount}"
    except:
        return "No Change"

# Sample DataFrame for illustration
data = {
    "Employee Name": ["Alice", "Bob", "Charlie"],
    "ppa": [16.0, 15.3, 14.8],
    "+/- ppa lw": ["Improved by 1.00", "Improved by 0.30", "Declined by 0.20"],
    "discount %": ["1.4%", "2.0%", "1.7%"],
    "+/- discount % lw": ["Declined by 0.10%", "Improved by 0.50%", "No Change"],
    "beverage %": ["19.0%", "17.5%", "18.2%"],
    "+/- beverage % lw": ["Improved by 0.50%", "Declined by 0.30%", "Improved by 0.20%"],
    "turn time": [34.0, 37.0, 41.0],
    "+/- turn time lw": ["Improved by 2.00", "Declined by 1.00", "Improved by 1.50"]
}
df = pd.DataFrame(data)

# Apply conditional styling
styled_df = df.style \
    .applymap(lambda v: highlight_metric(v, "ppa"), subset=["ppa"]) \
    .applymap(lambda v: highlight_metric(v, "+/- ppa lw"), subset=["+/- ppa lw"]) \
    .applymap(lambda v: highlight_metric(v, "discount %"), subset=["discount %"]) \
    .applymap(lambda v: highlight_metric(v, "+/- discount % lw"), subset=["+/- discount % lw"]) \
    .applymap(lambda v: highlight_metric(v, "beverage %"), subset=["beverage %"]) \
    .applymap(lambda v: highlight_metric(v, "+/- beverage % lw"), subset=["+/- beverage % lw"]) \
    .applymap(lambda v: highlight_metric(v, "turn time"), subset=["turn time"]) \
    .applymap(lambda v: highlight_metric(v, "+/- turn time lw"), subset=["+/- turn time lw"]) \
    .set_properties(**{'text-align': 'center'}) \
    .set_table_styles([dict(selector='th', props=[('text-align', 'center')])])

st.dataframe(styled_df, use_container_width=True)
