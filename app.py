import re
import textwrap
from io import BytesIO

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

st.set_page_config(page_title="FOH Performance Dashboard", layout="wide")

st.title("FOH Performance Dashboard")
st.caption("Combined Tablet Use + Turn Time + Dine In Beverage %")

# =========================
# Store Mapping
# =========================
STORE_MAP = {
    "3231": "Prattville",
    "4445": "Montgomery",
    "4456": "Oxford",
    "4463": "Decatur",
}

KNOWN_STORES = set(STORE_MAP.keys())

# =========================
# Upload Section
# =========================
tablet_files = st.file_uploader(
    "Upload Tablet Usage CSV file(s)",
    type=["csv"],
    accept_multiple_files=True,
)

turn_files = st.file_uploader(
    "Upload Turn Time file(s)",
    type=["csv", "xlsx", "xls"],
    accept_multiple_files=True,
)

beverage_files = st.file_uploader(
    "Upload Dine In Beverage file(s)",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True,
)

# =========================
# Helpers
# =========================
def clean_name(name):
    if pd.isna(name):
        return ""
    name = str(name).strip()
    if "," in name:
        parts = name.split(",", 1)
        name = f"{parts[1].strip()} {parts[0].strip()}"
    return " ".join(name.split()).title()


def pick_col(df, keywords):
    for col in df.columns:
        col_l = str(col).lower().strip()
        for key in keywords:
            if key in col_l:
                return col
    return None


def get_store_label(store_num):
    if not store_num:
        return "Unknown"
    return f"{store_num} - {STORE_MAP.get(store_num, 'Unknown')}"


def extract_store_from_text(text):
    matches = re.findall(r"\b\d{4}\b", str(text))
    for match in matches:
        if match in KNOWN_STORES:
            return match
    return None


def extract_store_from_filename(file):
    return extract_store_from_text(file.name)


def extract_store_from_csv_content(file):
    try:
        file.seek(0)
        raw = file.read()
        file.seek(0)

        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="ignore")
        else:
            text = str(raw)

        return extract_store_from_text(text[:5000])
    except Exception:
        file.seek(0)
        return None


def extract_store_from_excel_content(file):
    try:
        file.seek(0)
        content = file.read()
        file.seek(0)

        bio = BytesIO(content)
        preview = pd.read_excel(bio, header=None, nrows=10)

        for value in preview.astype(str).fillna("").values.flatten():
            store = extract_store_from_text(value)
            if store:
                return store
        return None
    except Exception:
        file.seek(0)
        return None


def detect_store(file):
    store = extract_store_from_filename(file)
    if store:
        return store

    name = file.name.lower()
    if name.endswith(".csv"):
        store = extract_store_from_csv_content(file)
    else:
        store = extract_store_from_excel_content(file)

    return store or "Unknown"


def safe_mean(series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return pd.NA
    return s.mean()


def format_single_rank_line(df, column, label, ascending=False):
    working = df[["Server", column]].copy()
    working[column] = pd.to_numeric(working[column], errors="coerce")
    working = working.dropna(subset=[column])

    if working.empty:
        return f"**{label}:** No data"

    best_value = working[column].min() if ascending else working[column].max()
    tied = working[working[column] == best_value].sort_values("Server")

    people = " • ".join(tied["Server"].tolist())
    return f"**{label}:** {people}"


def get_rank_names(df, column, ascending=False):
    working = df[["Server", column]].copy()
    working[column] = pd.to_numeric(working[column], errors="coerce")
    working = working.dropna(subset=[column])

    if working.empty:
        return "No data"

    best_value = working[column].min() if ascending else working[column].max()
    tied = working[working[column] == best_value].sort_values("Server")

    return " • ".join(tied["Server"].tolist())


def wrap_names(text, width=28):
    if not text or text == "No data":
        return text
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False))


def fig_to_png_bytes(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", facecolor="white")
    buf.seek(0)
    plt.close(fig)
    return buf


# =========================
# Tablet Processing
# =========================
def process_tablet_file(file):
    store = detect_store(file)

    file.seek(0)
    df = pd.read_csv(file)
    df.columns = df.columns.str.replace("\n", " ", regex=False).str.strip()

    df = df.rename(columns={
        "Device Orders Report": "Device Orders",
        "Staff Customer": "Server",
        "Base (Including Disc.)": "Base",
    })

    required = ["Device Orders", "Server", "Base"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{file.name}: missing required tablet columns: {', '.join(missing)}")

    df["Device Orders"] = df["Device Orders"].astype(str).str.strip().str.lower()
    df["Device Orders"] = df["Device Orders"].replace({
        "handheld": "handheld",
        "hand held": "handheld",
        "pos": "pos",
        "pos terminal": "pos",
    })
    df["Device Orders"] = df["Device Orders"].str.extract(r"(handheld|pos)", expand=False).fillna("unknown")
    df["Base"] = pd.to_numeric(df["Base"], errors="coerce").fillna(0)
    df["Server"] = df["Server"].apply(clean_name)
    df["Store"] = store

    return df[["Store", "Server", "Device Orders", "Base"]]


def process_all_tablet_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_tablet_file(file))
        except Exception as e:
            st.error(f"Tablet file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Store", "Server", "Tablet %"])

    combined_raw = pd.concat(all_rows, ignore_index=True)

    grouped = (
        combined_raw
        .groupby(["Store", "Server", "Device Orders"])["Base"]
        .sum()
        .unstack(fill_value=0)
    )

    if "handheld" not in grouped.columns:
        grouped["handheld"] = 0
    if "pos" not in grouped.columns:
        grouped["pos"] = 0

    grouped = grouped.rename(columns={
        "handheld": "Tablet Sales",
        "pos": "POS Sales",
    })

    grouped["Tablet %"] = (
        grouped["Tablet Sales"] /
        (grouped["Tablet Sales"] + grouped["POS Sales"])
    ).fillna(0)

    return grouped.reset_index()[["Store", "Server", "Tablet %"]]


# =========================
# Turn Time Processing
# =========================
def process_turn_file(file):
    store = detect_store(file)

    file.seek(0)
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)

    df.columns = df.columns.str.strip()

    col_open = pick_col(df, ["opened", "open", "order start", "start time", "opened at"])
    col_close = pick_col(df, ["closed", "close", "order end", "end time", "closed at"])
    col_service = pick_col(df, ["service", "service type", "order type"])
    col_server = pick_col(df, ["created by", "server", "server name", "employee", "cashier"])

    missing = []
    if not col_open:
        missing.append("Opened")
    if not col_close:
        missing.append("Closed")
    if not col_service:
        missing.append("Service")
    if not col_server:
        missing.append("Server")

    if missing:
        raise ValueError(f"{file.name}: missing required turn columns: {', '.join(missing)}")

    df[col_open] = pd.to_datetime(df[col_open], errors="coerce")
    df[col_close] = pd.to_datetime(df[col_close], errors="coerce")

    eat = df[df[col_service].astype(str).str.contains("eat in", case=False, na=False)].copy()
    eat["Turn Time"] = (eat[col_close] - eat[col_open]).dt.total_seconds() / 60
    eat = eat.dropna(subset=["Turn Time"])
    eat = eat[eat["Turn Time"] >= 0]

    eat[col_server] = eat[col_server].fillna("(Unknown)").replace("", "(Unknown)")
    eat["Server"] = eat[col_server].apply(clean_name)
    eat["Store"] = store

    return eat[["Store", "Server", "Turn Time"]]


def process_all_turn_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_turn_file(file))
        except Exception as e:
            st.error(f"Turn file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Store", "Server", "Turn Time"])

    combined_raw = pd.concat(all_rows, ignore_index=True)
    result = combined_raw.groupby(["Store", "Server"], as_index=False)["Turn Time"].mean()
    result["Turn Time"] = result["Turn Time"].round(2)
    return result


# =========================
# Beverage Processing
# =========================
def process_beverage_file(file):
    file.seek(0)
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file, header=4)

    df.columns = [str(col).strip() for col in df.columns]

    col_store = pick_col(df, ["location"])
    col_server = pick_col(df, ["employee"])
    col_bev = pick_col(df, ["% of net sales"])

    missing = []
    if not col_store:
        missing.append("Location")
    if not col_server:
        missing.append("Employee")
    if not col_bev:
        missing.append("% of Net Sales")

    if missing:
        raise ValueError(f"{file.name}: missing required beverage columns: {', '.join(missing)}")

    df["Store"] = df[col_store].apply(extract_store_from_text)
    df["Server"] = df[col_server].apply(clean_name)
    df["Dine In Bev %"] = pd.to_numeric(df[col_bev], errors="coerce")

    df = df.dropna(subset=["Store", "Dine In Bev %"]).copy()
    df["Store"] = df["Store"].astype(str).str.strip()
    df["Server"] = df["Server"].fillna("").astype(str).str.strip()

    df = df[df["Store"] != ""].copy()
    df = df[df["Server"] != ""].copy()
    df = df[~df["Server"].str.lower().str.contains("total", na=False)].copy()

    non_null = df["Dine In Bev %"].dropna()
    if not non_null.empty and non_null.median() > 1:
        df["Dine In Bev %"] = df["Dine In Bev %"] / 100

    return df[["Store", "Server", "Dine In Bev %"]]


def process_all_beverage_files(files):
    all_rows = []

    for file in files:
        try:
            all_rows.append(process_beverage_file(file))
        except Exception as e:
            st.error(f"Beverage file '{file.name}' failed: {e}")

    if not all_rows:
        return pd.DataFrame(columns=["Store", "Server", "Dine In Bev %"])

    combined = pd.concat(all_rows, ignore_index=True)
    return combined.groupby(["Store", "Server"], as_index=False)["Dine In Bev %"].mean()


# =========================
# Score Helpers
# =========================
def is_tablet_green(x):
    return pd.notna(x) and x >= 0.90


def is_turn_green(x):
    return pd.notna(x) and x <= 40


def is_bev_green(x):
    return pd.notna(x) and x >= 0.19


def tablet_score_icon(x):
    if pd.isna(x):
        return ""
    if x >= 0.90:
        return "🟢"
    elif x >= 0.80:
        return "🟡"
    return "🔴"


def turn_score_icon(x):
    if pd.isna(x):
        return ""
    if x <= 40:
        return "🟢"
    elif x <= 45:
        return "🟡"
    return "🔴"


def beverage_score_icon(x):
    if pd.isna(x):
        return ""
    if x >= 0.19:
        return "🟢"
    elif x >= 0.18:
        return "🟡"
    return "🔴"


def greens_count(row):
    count = 0
    if is_tablet_green(row["Tablet %"]):
        count += 1
    if is_turn_green(row["Turn Time"]):
        count += 1
    if is_bev_green(row["Dine In Bev %"]):
        count += 1
    return count


# =========================
# WhatsApp Card Export
# =========================
def create_whatsapp_store_card(store_label, store_df_sorted):
    avg_tablet = safe_mean(store_df_sorted["Tablet %"])
    avg_turn = safe_mean(store_df_sorted["Turn Time"])
    avg_bev = safe_mean(store_df_sorted["Dine In Bev %"])

    tablet_top = get_rank_names(store_df_sorted, "Tablet %", ascending=False)
    tablet_bottom = get_rank_names(store_df_sorted, "Tablet %", ascending=True)

    turn_best = get_rank_names(store_df_sorted, "Turn Time", ascending=True)
    turn_slowest = get_rank_names(store_df_sorted, "Turn Time", ascending=False)

    bev_top = get_rank_names(store_df_sorted, "Dine In Bev %", ascending=False)
    bev_bottom = get_rank_names(store_df_sorted, "Dine In Bev %", ascending=True)

    export_df = store_df_sorted.copy()

    def tablet_metric_with_dot(x):
        if pd.isna(x):
            return ""
        return f"{tablet_score_icon(x)} {x:.2%}"

    def turn_metric_with_dot(x):
        if pd.isna(x):
            return ""
        return f"{turn_score_icon(x)} {x:.2f}"

    def beverage_metric_with_dot(x):
        if pd.isna(x):
            return ""
        return f"{beverage_score_icon(x)} {x:.2%}"

    export_df["Tablet %"] = export_df["Tablet %"].apply(tablet_metric_with_dot)
    export_df["Turn Time"] = export_df["Turn Time"].apply(turn_metric_with_dot)
    export_df["Dine In Bev %"] = export_df["Dine In Bev %"].apply(beverage_metric_with_dot)

    export_df = export_df[["Server", "Tablet %", "Turn Time", "Dine In Bev %"]].copy()

    row_count = len(export_df)
    fig_height = max(8.8, 4.4 + (row_count * 0.44))
    fig, ax = plt.subplots(figsize=(8.2, fig_height))
    fig.patch.set_facecolor("white")
    ax.set_axis_off()

    # Card background
    ax.add_patch(Rectangle((0.01, 0.01), 0.98, 0.98, transform=ax.transAxes,
                           facecolor="white", edgecolor="#d7dee8", linewidth=1.2, zorder=0))

    # Header band
    ax.add_patch(Rectangle((0.01, 0.91), 0.98, 0.08, transform=ax.transAxes,
                           facecolor="#1d4f91", edgecolor="#1d4f91", zorder=1))
    ax.text(
        0.03, 0.95, store_label,
        transform=ax.transAxes,
        fontsize=17,
        fontweight="bold",
        color="white",
        va="center",
        zorder=2
    )

    # Summary lane boxes
    lane_y = 0.69
    lane_h = 0.17
    lane_w = 0.29
    lane_gap = 0.03
    lane_xs = [0.03, 0.03 + lane_w + lane_gap, 0.03 + (lane_w + lane_gap) * 2]

    lane_data = [
        (
            "TABLET",
            "Avg Tablet %",
            "No data" if pd.isna(avg_tablet) else f"{avg_tablet:.2%}",
            "Top",
            wrap_names(tablet_top, width=24),
            "Bottom",
            wrap_names(tablet_bottom, width=24),
        ),
        (
            "TURN",
            "Avg Turn",
            "No data" if pd.isna(avg_turn) else f"{avg_turn:.2f}",
            "Best",
            wrap_names(turn_best, width=24),
            "Slowest",
            wrap_names(turn_slowest, width=24),
        ),
        (
            "BEVERAGE",
            "Avg Dine In Bev %",
            "No data" if pd.isna(avg_bev) else f"{avg_bev:.2%}",
            "Top",
            wrap_names(bev_top, width=24),
            "Bottom",
            wrap_names(bev_bottom, width=24),
        ),
    ]

    for lane_x, lane in zip(lane_xs, lane_data):
        title, avg_label, avg_value, label1, value1, label2, value2 = lane

        ax.add_patch(Rectangle((lane_x, lane_y), lane_w, lane_h, transform=ax.transAxes,
                               facecolor="#f5f8fc", edgecolor="#cfd9e6", linewidth=1, zorder=1))
        ax.text(lane_x + 0.015, lane_y + lane_h - 0.025, title,
                transform=ax.transAxes, fontsize=11, fontweight="bold",
                color="#1d4f91", va="top", zorder=2)

        ax.text(lane_x + 0.015, lane_y + lane_h - 0.060, avg_label,
                transform=ax.transAxes, fontsize=8.8, color="#5c6773", va="top", zorder=2)
        ax.text(lane_x + 0.015, lane_y + lane_h - 0.090, avg_value,
                transform=ax.transAxes, fontsize=12, fontweight="bold",
                color="#222222", va="top", zorder=2)

        ax.text(lane_x + 0.015, lane_y + lane_h - 0.130, f"{label1}: {value1}",
                transform=ax.transAxes, fontsize=8.6, color="#222222", va="top", zorder=2)
        ax.text(lane_x + 0.015, lane_y + lane_h - 0.185, f"{label2}: {value2}",
                transform=ax.transAxes, fontsize=8.6, color="#222222", va="top", zorder=2)

    # Table
    table_bbox = [0.03, 0.04, 0.94, 0.58]
    table = ax.table(
        cellText=export_df.values,
        colLabels=export_df.columns,
        cellLoc="left",
        loc="center",
        bbox=table_bbox
    )

    table.auto_set_font_size(False)
    table.set_fontsize(9.8)
    table.scale(1, 1.45)

    # Table styling
    ncols = len(export_df.columns)

    for col_idx in range(ncols):
        header_cell = table[0, col_idx]
        header_cell.set_text_props(weight="bold", color="white")
        header_cell.set_facecolor("#2d6cb5")
        header_cell.set_edgecolor("#d7dee8")

    for row_idx in range(1, len(export_df) + 1):
        for col_idx in range(ncols):
            cell = table[row_idx, col_idx]
            cell.set_edgecolor("#dfe5ec")
            if row_idx % 2 == 0:
                cell.set_facecolor("#fbfcfe")
            else:
                cell.set_facecolor("white")

        original_row = store_df_sorted.iloc[row_idx - 1]
        if original_row["_all_green"]:
            for col_idx in range(ncols):
                table[row_idx, col_idx].set_facecolor("#e8f5e9")

    return fig


# =========================
# Main Processing
# =========================
if tablet_files or turn_files or beverage_files:
    tablet_df = process_all_tablet_files(tablet_files or [])
    turn_df = process_all_turn_files(turn_files or [])
    beverage_df = process_all_beverage_files(beverage_files or [])

    combined = pd.DataFrame()

    if not tablet_df.empty:
        combined = tablet_df.copy()

    if not turn_df.empty:
        combined = turn_df.copy() if combined.empty else pd.merge(
            combined, turn_df, on=["Store", "Server"], how="outer"
        )

    if not beverage_df.empty:
        combined = beverage_df.copy() if combined.empty else pd.merge(
            combined, beverage_df, on=["Store", "Server"], how="outer"
        )

    if not combined.empty:
        combined["Store"] = combined["Store"].fillna("Unknown").astype(str).str.strip()
        combined["Server"] = combined["Server"].fillna("").astype(str).str.strip()

        combined = combined[combined["Server"] != ""].copy()
        combined = combined[~combined["Server"].str.lower().str.contains("total", na=False)].copy()

        if "Tablet %" not in combined.columns:
            combined["Tablet %"] = pd.NA
        if "Turn Time" not in combined.columns:
            combined["Turn Time"] = pd.NA
        if "Dine In Bev %" not in combined.columns:
            combined["Dine In Bev %"] = pd.NA

        combined["_all_green"] = combined.apply(
            lambda row: (
                is_tablet_green(row["Tablet %"])
                and is_turn_green(row["Turn Time"])
                and is_bev_green(row["Dine In Bev %"])
            ),
            axis=1,
        )

        combined["_greens_count"] = combined.apply(greens_count, axis=1)

        store_order = sorted(
            combined["Store"].dropna().unique(),
            key=lambda x: (x == "Unknown", x)
        )

        st.subheader("Combined Server Performance")

        for store in store_order:
            store_df = combined[combined["Store"] == store].copy()

            if store_df.empty:
                continue

            store_label = get_store_label(store)
            st.markdown(f"### 📍 {store_label}")

            avg_tablet = safe_mean(store_df["Tablet %"])
            avg_turn = safe_mean(store_df["Turn Time"])
            avg_bev = safe_mean(store_df["Dine In Bev %"])

            tablet_col, turn_col, bev_col = st.columns(3)

            with tablet_col:
                st.metric(
                    "Avg Tablet %",
                    "No data" if pd.isna(avg_tablet) else f"{avg_tablet:.2%}"
                )
                st.markdown(format_single_rank_line(store_df, "Tablet %", "Top", ascending=False))
                st.markdown(format_single_rank_line(store_df, "Tablet %", "Bottom", ascending=True))

            with turn_col:
                st.metric(
                    "Avg Turn",
                    "No data" if pd.isna(avg_turn) else f"{avg_turn:.2f}"
                )
                st.markdown(format_single_rank_line(store_df, "Turn Time", "Best", ascending=True))
                st.markdown(format_single_rank_line(store_df, "Turn Time", "Slowest", ascending=False))

            with bev_col:
                st.metric(
                    "Avg Dine In Bev %",
                    "No data" if pd.isna(avg_bev) else f"{avg_bev:.2%}"
                )
                st.markdown(format_single_rank_line(store_df, "Dine In Bev %", "Top", ascending=False))
                st.markdown(format_single_rank_line(store_df, "Dine In Bev %", "Bottom", ascending=True))

            def tablet_metric_with_dot(x):
                if pd.isna(x):
                    return ""
                return f"{tablet_score_icon(x)} {x:.2%}"

            def turn_metric_with_dot(x):
                if pd.isna(x):
                    return ""
                return f"{turn_score_icon(x)} {x:.2f}"

            def beverage_metric_with_dot(x):
                if pd.isna(x):
                    return ""
                return f"{beverage_score_icon(x)} {x:.2%}"

            store_df_sorted = store_df.copy()
            store_df_sorted["_tablet_sort"] = pd.to_numeric(store_df_sorted["Tablet %"], errors="coerce").fillna(-1)
            store_df_sorted["_turn_sort"] = pd.to_numeric(store_df_sorted["Turn Time"], errors="coerce").fillna(999999)
            store_df_sorted["_bev_sort"] = pd.to_numeric(store_df_sorted["Dine In Bev %"], errors="coerce").fillna(-1)

            store_df_sorted = store_df_sorted.sort_values(
                by=["_greens_count", "_tablet_sort", "_turn_sort", "_bev_sort", "Server"],
                ascending=[False, False, True, False, True]
            ).reset_index(drop=True)

            display_df = store_df_sorted.copy()
            display_df["Tablet %"] = display_df["Tablet %"].apply(tablet_metric_with_dot)
            display_df["Turn Time"] = display_df["Turn Time"].apply(turn_metric_with_dot)
            display_df["Dine In Bev %"] = display_df["Dine In Bev %"].apply(beverage_metric_with_dot)

            display_df = display_df[[
                "Server",
                "Tablet %",
                "Turn Time",
                "Dine In Bev %",
            ]]

            def highlight_all_green(row):
                original_row = store_df_sorted.iloc[row.name]
                if original_row["_all_green"]:
                    return ["background-color: #e8f5e9"] * len(row)
                return [""] * len(row)

            styled_df = display_df.style.apply(highlight_all_green, axis=1)

            st.dataframe(styled_df, use_container_width=True, hide_index=True)

            card_fig = create_whatsapp_store_card(store_label, store_df_sorted)
            card_buf = fig_to_png_bytes(card_fig)
            safe_store_label = store_label.replace(" - ", "_").replace(" ", "_")

            st.download_button(
                label=f"Download {store_label} WhatsApp Card",
                data=card_buf,
                file_name=f"{safe_store_label}_whatsapp_card.png",
                mime="image/png",
            )

            st.divider()
    else:
        st.warning("No valid data could be processed from the uploaded files.")
else:
    st.info("Upload tablet files, turn files, beverage files, or any combination to begin.")
