import json
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Param Ganga — Daily Ops Dashboard", layout="wide")

THRESHOLD_FILE = Path(__file__).parent / "thresholds.json"

DEFAULT_THRESHOLDS = {
    "server_temp_max": 22.0,
    "ups_temp_max": 22.0,
    "pue_max": 1.3,
    "pue_min": 0.9,  # below this is treated as bad data, not a real alert
    "dry_cooler_inlet_max": 40.0,
    "dg_oil_min_ltr": 470.0,
    "ups_load_max_kw": 60.0,
    "lt_panel_amp_max": 340.0,
}

NUMERIC_COLS = {
    "Server Room Temp": "°C",
    "UPS Room Temp": "°C",
    "PUE Value": "",
    "Dry Cooler Inlet Temp": "°C",
    "Dry Cooler Outlet Temp": "°C",
    "Pump Flow": "",
    "PH Value": "",
    "DPT Value": "",
    "TDS Value": "",
    "LT Panel Load Amp.": "A",
    "UPS-1 Load kW": "kW",
    "UPS-2 Load kW": "kW",
    "UPS-3 Load kW": "kW",
    "UPS-4 Load kw": "kW",
    "UPS-5 Load kW": "kW",
    "DG Oil Status": "Ltr",
}

STATUS_COLS = [
    "FIRE System", "VESDA System", "WLD System", "GSS System",
    "Rodent System", "Access System", "CCTV System", "IBMS System",
]


def load_thresholds():
    if THRESHOLD_FILE.exists():
        try:
            return {**DEFAULT_THRESHOLDS, **json.loads(THRESHOLD_FILE.read_text())}
        except Exception:
            pass
    return DEFAULT_THRESHOLDS.copy()


def save_thresholds(t):
    THRESHOLD_FILE.write_text(json.dumps(t, indent=2))


def to_float(val):
    if pd.isna(val):
        return None
    s = str(val)
    m = re.search(r"-?\d+\.?\d*", s)
    return float(m.group()) if m else None


def parse_excel(file):
    raw = pd.read_excel(file, header=None)
    # find header row — the row that contains "DATE" and "TIME"
    header_idx = None
    for i in range(min(10, len(raw))):
        row_vals = [str(v).strip().upper() for v in raw.iloc[i].tolist()]
        if "DATE" in row_vals and "TIME" in row_vals:
            header_idx = i
            break
    if header_idx is None:
        header_idx = 0
    df = pd.read_excel(file, header=header_idx)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")
    df = df[df["DATE"].notna()] if "DATE" in df.columns else df

    # parse datetime
    if "DATE" in df.columns and "TIME" in df.columns:
        df["Timestamp"] = pd.to_datetime(
            df["DATE"].astype(str) + " " + df["TIME"].astype(str),
            errors="coerce",
        )

    # numeric columns
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col + " (num)"] = df[col].apply(to_float)

    return df


def find_alerts(df, t):
    alerts = []
    quality = []
    for _, row in df.iterrows():
        ts = row.get("Timestamp")
        ts_str = ts.strftime("%Y-%m-%d %H:%M") if pd.notna(ts) else f"{row.get('DATE')} {row.get('TIME')}"

        srt = row.get("Server Room Temp (num)")
        if srt is not None:
            if srt < 5:
                quality.append((ts_str, "Server Room Temp", srt, "Likely sensor error (too low)"))
            elif srt > t["server_temp_max"]:
                alerts.append((ts_str, "Server Room Temp", f"{srt}°C", f">{t['server_temp_max']}°C"))

        urt = row.get("UPS Room Temp (num)")
        if urt is not None and urt > t["ups_temp_max"]:
            alerts.append((ts_str, "UPS Room Temp", f"{urt}°C", f">{t['ups_temp_max']}°C"))

        pue = row.get("PUE Value (num)")
        if pue is not None:
            if pue < t["pue_min"]:
                quality.append((ts_str, "PUE Value", pue, "Likely data entry error"))
            elif pue > t["pue_max"]:
                alerts.append((ts_str, "PUE Value", pue, f">{t['pue_max']}"))

        dci = row.get("Dry Cooler Inlet Temp (num)")
        if dci is not None and dci > t["dry_cooler_inlet_max"]:
            alerts.append((ts_str, "Dry Cooler Inlet", f"{dci}°C", f">{t['dry_cooler_inlet_max']}°C"))

        dg = row.get("DG Oil Status (num)")
        if dg is not None and dg < t["dg_oil_min_ltr"]:
            alerts.append((ts_str, "DG Oil", f"{dg} Ltr", f"<{t['dg_oil_min_ltr']} Ltr"))

        for ups_col in ["UPS-1 Load kW", "UPS-2 Load kW", "UPS-3 Load kW", "UPS-4 Load kw", "UPS-5 Load kW"]:
            v = row.get(ups_col + " (num)")
            if v is not None and v > t["ups_load_max_kw"]:
                alerts.append((ts_str, ups_col, f"{v} kW", f">{t['ups_load_max_kw']} kW"))

        amp = row.get("LT Panel Load Amp. (num)")
        if amp is not None and amp > t["lt_panel_amp_max"]:
            alerts.append((ts_str, "LT Panel Load", f"{amp} A", f">{t['lt_panel_amp_max']} A"))

        for c in STATUS_COLS:
            v = row.get(c)
            if v is not None and pd.notna(v) and str(v).strip().lower() != "normal":
                alerts.append((ts_str, c, str(v), "expected: Normal"))

    return (
        pd.DataFrame(alerts, columns=["Time", "Parameter", "Value", "Rule"]),
        pd.DataFrame(quality, columns=["Time", "Parameter", "Value", "Note"]),
    )


# ---------------- UI ----------------

st.title("Param Ganga — Daily Ops Dashboard")

with st.sidebar:
    st.header("1. Upload daily report")
    uploaded = st.file_uploader("Excel file (.xlsx)", type=["xlsx", "xls"])

    st.header("2. Thresholds")
    t = load_thresholds()
    t["server_temp_max"] = st.number_input("Server Room Temp max (°C)", value=float(t["server_temp_max"]), step=0.5)
    t["ups_temp_max"] = st.number_input("UPS Room Temp max (°C)", value=float(t["ups_temp_max"]), step=0.5)
    t["pue_max"] = st.number_input("PUE max", value=float(t["pue_max"]), step=0.05, format="%.2f")
    t["pue_min"] = st.number_input("PUE min (data quality floor)", value=float(t["pue_min"]), step=0.05, format="%.2f")
    t["dry_cooler_inlet_max"] = st.number_input("Dry Cooler Inlet max (°C)", value=float(t["dry_cooler_inlet_max"]), step=0.5)
    t["dg_oil_min_ltr"] = st.number_input("DG Oil min (Ltr)", value=float(t["dg_oil_min_ltr"]), step=5.0)
    t["ups_load_max_kw"] = st.number_input("UPS Load max (kW)", value=float(t["ups_load_max_kw"]), step=1.0)
    t["lt_panel_amp_max"] = st.number_input("LT Panel Load max (A)", value=float(t["lt_panel_amp_max"]), step=5.0)
    if st.button("Save thresholds"):
        save_thresholds(t)
        st.success("Saved.")

if uploaded is None:
    st.info("Upload the daily Excel report from the sidebar to begin.")
    st.stop()

try:
    df = parse_excel(uploaded)
except Exception as e:
    st.error(f"Could not parse file: {e}")
    st.stop()

if df.empty:
    st.warning("No rows found in file.")
    st.stop()

alerts_df, quality_df = find_alerts(df, t)

# KPI row
c1, c2, c3, c4, c5 = st.columns(5)
pue_vals = df["PUE Value (num)"].dropna()
pue_clean = pue_vals[pue_vals >= t["pue_min"]]
c1.metric("Avg PUE (clean)", f"{pue_clean.mean():.2f}" if len(pue_clean) else "—")
c2.metric("Max Server Temp", f"{df['Server Room Temp (num)'].max():.1f}°C" if "Server Room Temp (num)" in df else "—")
c3.metric("Min DG Oil", f"{df['DG Oil Status (num)'].min():.0f} Ltr" if "DG Oil Status (num)" in df else "—")
c4.metric("Threshold breaches", len(alerts_df))
c5.metric("Data quality issues", len(quality_df))

tab_overview, tab_trends, tab_alerts, tab_raw = st.tabs(["Overview", "Trends", "Alerts", "Raw data"])

with tab_overview:
    st.subheader("Server Room Temperature by hour")
    if "Timestamp" in df.columns and df["Timestamp"].notna().any():
        heat = df.copy()
        heat["Hour"] = heat["Timestamp"].dt.hour
        heat["Day"] = heat["Timestamp"].dt.date.astype(str)
        pivot = heat.pivot_table(values="Server Room Temp (num)", index="Day", columns="Hour", aggfunc="mean")
        if not pivot.empty:
            fig = px.imshow(
                pivot, color_continuous_scale="RdYlGn_r", aspect="auto",
                labels=dict(x="Hour", y="Date", color="°C"),
            )
            fig.update_layout(height=max(220, 60 * len(pivot)))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("System status")
    if any(c in df.columns for c in STATUS_COLS):
        last = df.iloc[-1]
        cols = st.columns(len(STATUS_COLS))
        for col, name in zip(cols, STATUS_COLS):
            v = last.get(name, "—")
            ok = str(v).strip().lower() == "normal"
            col.markdown(
                f"<div style='padding:10px;border-radius:8px;text-align:center;"
                f"background:{'#d4edda' if ok else '#f8d7da'};color:#000'>"
                f"<b>{name.replace(' System','')}</b><br>{v}</div>",
                unsafe_allow_html=True,
            )

with tab_trends:
    plot_cols = [
        ("PUE Value (num)", "PUE"),
        ("Server Room Temp (num)", "Server Room Temp (°C)"),
        ("UPS Room Temp (num)", "UPS Room Temp (°C)"),
        ("Dry Cooler Inlet Temp (num)", "Dry Cooler Inlet (°C)"),
        ("Dry Cooler Outlet Temp (num)", "Dry Cooler Outlet (°C)"),
        ("Pump Flow (num)", "Pump Flow"),
        ("LT Panel Load Amp. (num)", "LT Panel Load (A)"),
    ]
    x = df["Timestamp"] if "Timestamp" in df.columns else df.index
    for col, label in plot_cols:
        if col in df.columns and df[col].notna().any():
            fig = px.line(df, x=x, y=col, title=label, markers=True)
            fig.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("UPS Loads")
    ups_cols = [c for c in ["UPS-1 Load kW (num)", "UPS-2 Load kW (num)", "UPS-3 Load kW (num)",
                            "UPS-4 Load kw (num)", "UPS-5 Load kW (num)"] if c in df.columns]
    if ups_cols:
        long = df[["Timestamp"] + ups_cols].melt("Timestamp", var_name="UPS", value_name="kW")
        long["UPS"] = long["UPS"].str.replace(" Load kW (num)", "", regex=False).str.replace(" Load kw (num)", "", regex=False)
        fig = px.line(long, x="Timestamp", y="kW", color="UPS", markers=True)
        fig.update_layout(height=320)
        st.plotly_chart(fig, use_container_width=True)

with tab_alerts:
    st.subheader(f"Threshold breaches ({len(alerts_df)})")
    if alerts_df.empty:
        st.success("No threshold breaches.")
    else:
        st.dataframe(alerts_df, use_container_width=True, hide_index=True)

    st.subheader(f"Data quality issues ({len(quality_df)})")
    if quality_df.empty:
        st.info("No data quality issues detected.")
    else:
        st.dataframe(quality_df, use_container_width=True, hide_index=True)
        st.caption("These are likely typos or sensor glitches in the source file (e.g., '02.3°C' instead of '20.3°C'). They are excluded from KPI averages.")

with tab_raw:
    st.dataframe(df, use_container_width=True, hide_index=True)
