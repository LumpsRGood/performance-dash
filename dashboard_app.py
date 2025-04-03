
import streamlit as st
import pandas as pd
from openpyxl import load_workbook

st.set_page_config(page_title="Server Performance Dashboard - v1.2.39", layout="wide")
st.title("📊 Weekly Performance Dashboard")

def safe_strip(val):
    if isinstance(val, str):
        return val.strip()
    elif val is not None:
        return str(val).strip()
    return ""

def parse_turn(file):
    df = pd.read_excel(file)

    if "Server Table Turn Stats" in str(df.columns[0]):
        df.columns = df.iloc[1]
        df = df[2:]

    df = df.dropna(how="all")

    df.columns = [c.lower() for c in [safe_strip(c) for c in df.columns]]

    if "employee name" not in df.columns:
        return pd.DataFrame()

    df = df[df["employee name"].apply(lambda x: isinstance(x, str) and x.strip() != "")]
    df["employee name"] = df["employee name"].apply(lambda x: safe_strip(x).upper())
    df = df[df["employee name"] != "STAFF, OLO"]

    numeric_fields = ["covers", "checks", "guests per check", "total sales", "table turns", "hours", "avg turn time"]
    for col in numeric_fields:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.reset_index(drop=True)

# Main Streamlit app placeholder
st.write("✅ Dashboard loaded with strip-safe parsing.")
