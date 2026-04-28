import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="PARAM GANGA // NOC",
    layout="wide",
    initial_sidebar_state="expanded",
)

THRESHOLD_FILE = Path(__file__).parent / "thresholds.json"

DEFAULT_THRESHOLDS = {
    "server_temp_max": 22.0,
    "ups_temp_max": 22.0,
    "pue_max": 1.3,
    "pue_min": 0.9,
    "dry_cooler_inlet_max": 40.0,
    "dg_oil_min_ltr": 470.0,
    "ups_load_max_kw": 60.0,
    "lt_panel_amp_max": 340.0,
}

PLAIN_LABELS = {
    "server_temp_max": "Server Room Temperature should stay below",
    "ups_temp_max": "UPS Room Temperature should stay below",
    "pue_max": "Power Usage Efficiency (PUE) should stay below",
    "pue_min": "Treat PUE values below this as bad data",
    "dry_cooler_inlet_max": "Dry Cooler Inlet Temperature should stay below",
    "dg_oil_min_ltr": "Generator (DG) Oil should stay above",
    "ups_load_max_kw": "Each UPS load should stay below",
    "lt_panel_amp_max": "LT Panel Load (Amp) should stay below",
}

NUMERIC_COLS = [
    "Server Room Temp", "UPS Room Temp", "PUE Value",
    "Dry Cooler Inlet Temp", "Dry Cooler Outlet Temp", "Pump Flow",
    "PH Value", "DPT Value", "TDS Value", "LT Panel Load Amp.",
    "UPS-1 Load kW", "UPS-2 Load kW", "UPS-3 Load kW",
    "UPS-4 Load kw", "UPS-5 Load kW", "DG Oil Status",
]

STATUS_COLS = [
    "FIRE System", "VESDA System", "WLD System", "GSS System",
    "Rodent System", "Access System", "CCTV System", "IBMS System",
]

# ---------------- styles ----------------

CSS = """
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
    --bg-0: #0a0e1a;
    --bg-1: #131829;
    --bg-2: #1a2138;
    --line: #243049;
    --txt: #e6edf3;
    --mut: #8b97a8;
    --cy: #00e5ff;
    --gn: #00ff9c;
    --am: #ffb547;
    --rd: #ff3d6e;
    --pu: #b388ff;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: var(--txt);
    font-size: 16px;
}

.stApp {
    background:
        radial-gradient(ellipse at top left, rgba(0,229,255,0.06), transparent 50%),
        radial-gradient(ellipse at bottom right, rgba(179,136,255,0.05), transparent 50%),
        var(--bg-0);
}

h1, h2, h3 { font-family: 'Inter', sans-serif; letter-spacing: -0.01em; }
h1 { font-size: 1.9rem !important; font-weight: 700; }
h2 { font-size: 1.35rem !important; font-weight: 600; color: var(--txt) !important; }
h3 { font-size: 1.1rem !important; font-weight: 600; color: var(--txt) !important; }

.mono { font-family: 'JetBrains Mono', monospace; }

/* top header bar */
.topbar {
    display: flex; align-items: center; justify-content: space-between;
    background: linear-gradient(90deg, var(--bg-1) 0%, var(--bg-2) 100%);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 14px 22px;
    margin-bottom: 18px;
    box-shadow: 0 0 0 1px rgba(0,229,255,0.05), 0 8px 24px rgba(0,0,0,0.35);
}
.topbar .title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.4rem; font-weight: 700;
    color: var(--cy);
    letter-spacing: 0.05em;
    text-shadow: 0 0 18px rgba(0,229,255,0.45);
}
.topbar .meta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem; color: var(--mut);
    text-align: right;
}
.topbar .meta b { color: var(--txt); }

.live-dot {
    display: inline-block; width: 9px; height: 9px; border-radius: 50%;
    background: var(--gn); margin-right: 6px;
    box-shadow: 0 0 10px var(--gn);
    animation: pulse 1.6s infinite;
}
@keyframes pulse {
    0%   { opacity: 1; transform: scale(1); }
    50%  { opacity: 0.55; transform: scale(1.25); }
    100% { opacity: 1; transform: scale(1); }
}

/* big banner */
.banner {
    position: relative;
    padding: 22px 26px;
    border-radius: 12px;
    margin-bottom: 22px;
    background: var(--bg-1);
    border: 1px solid var(--line);
    overflow: hidden;
}
.banner::before {
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
}
.banner h2 { margin: 0 0 4px 0 !important; font-size: 1.5rem !important; }
.banner p  { margin: 0; color: var(--mut); font-size: 1rem; }
.banner .tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem; letter-spacing: 0.15em;
    padding: 3px 8px; border-radius: 4px;
    display: inline-block; margin-bottom: 8px;
}
.banner-good     { box-shadow: 0 0 0 1px rgba(0,255,156,0.3), 0 0 30px rgba(0,255,156,0.06); }
.banner-good::before { background: var(--gn); box-shadow: 0 0 18px var(--gn); }
.banner-good h2  { color: var(--gn) !important; }
.banner-good .tag { background: rgba(0,255,156,0.12); color: var(--gn); border: 1px solid rgba(0,255,156,0.3); }

.banner-warn     { box-shadow: 0 0 0 1px rgba(255,181,71,0.3), 0 0 30px rgba(255,181,71,0.07); }
.banner-warn::before { background: var(--am); box-shadow: 0 0 18px var(--am); }
.banner-warn h2  { color: var(--am) !important; }
.banner-warn .tag { background: rgba(255,181,71,0.12); color: var(--am); border: 1px solid rgba(255,181,71,0.3); }

.banner-critical { box-shadow: 0 0 0 1px rgba(255,61,110,0.4), 0 0 30px rgba(255,61,110,0.1); }
.banner-critical::before { background: var(--rd); box-shadow: 0 0 18px var(--rd); }
.banner-critical h2 { color: var(--rd) !important; }
.banner-critical .tag { background: rgba(255,61,110,0.12); color: var(--rd); border: 1px solid rgba(255,61,110,0.3); }

/* KPI metric cards */
.kpi {
    background: linear-gradient(160deg, var(--bg-1), var(--bg-2));
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 16px 18px;
    height: 100%;
    position: relative;
    transition: all 0.2s;
}
.kpi:hover { border-color: var(--cy); box-shadow: 0 0 24px rgba(0,229,255,0.1); }
.kpi .lbl {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem; letter-spacing: 0.12em;
    color: var(--mut); text-transform: uppercase;
    margin-bottom: 10px;
}
.kpi .val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2.3rem; font-weight: 700;
    line-height: 1; color: var(--txt);
}
.kpi .unit { font-size: 1rem; color: var(--mut); margin-left: 4px; }
.kpi .sub { font-size: 0.85rem; color: var(--mut); margin-top: 8px; }
.kpi-good .val  { color: var(--gn); text-shadow: 0 0 18px rgba(0,255,156,0.35); }
.kpi-warn .val  { color: var(--am); text-shadow: 0 0 18px rgba(255,181,71,0.35); }
.kpi-bad  .val  { color: var(--rd); text-shadow: 0 0 18px rgba(255,61,110,0.4); }

/* status tiles */
.tile {
    border-radius: 10px;
    padding: 14px 12px;
    text-align: center;
    background: var(--bg-1);
    border: 1px solid var(--line);
    height: 100%;
    transition: all 0.2s;
}
.tile b { font-size: 0.95rem; letter-spacing: 0.05em; }
.tile .v {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem; margin-top: 8px;
}
.tile .led {
    display: inline-block; width: 10px; height: 10px; border-radius: 50%;
    margin-right: 6px;
}
.tile-ok  { border-color: rgba(0,255,156,0.35); }
.tile-ok  .led { background: var(--gn); box-shadow: 0 0 12px var(--gn); }
.tile-ok  b { color: var(--gn); }
.tile-bad { border-color: rgba(255,61,110,0.4); background: rgba(255,61,110,0.04); }
.tile-bad .led { background: var(--rd); box-shadow: 0 0 12px var(--rd); animation: pulse 1.2s infinite; }
.tile-bad b { color: var(--rd); }

/* alert cards */
.alert-card {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-left: 4px solid var(--am);
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.92rem;
    transition: all 0.15s;
}
.alert-card:hover { background: var(--bg-2); }
.alert-card.crit { border-left-color: var(--rd); }
.alert-card.crit .what { color: var(--rd); }
.alert-card .when { color: var(--mut); font-size: 0.78rem; letter-spacing: 0.1em; }
.alert-card .what { color: var(--am); font-weight: 600; margin-top: 3px; font-size: 1rem; }
.alert-card .desc { color: var(--txt); margin-top: 4px; }

/* helper info bar */
.section-help {
    background: rgba(0,229,255,0.05);
    border: 1px solid rgba(0,229,255,0.18);
    border-radius: 8px;
    padding: 10px 14px;
    color: var(--mut);
    font-size: 0.9rem;
    margin-bottom: 14px;
}
.section-help b { color: var(--cy); }

/* sidebar polish */
[data-testid="stSidebar"] {
    background: var(--bg-1);
    border-right: 1px solid var(--line);
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {
    color: var(--cy) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.9rem !important;
    letter-spacing: 0.15em;
    text-transform: uppercase;
}
[data-testid="stSidebar"] .stButton > button {
    background: linear-gradient(90deg, rgba(0,229,255,0.15), rgba(0,255,156,0.1));
    color: var(--cy);
    border: 1px solid rgba(0,229,255,0.3);
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.1em;
    font-weight: 600;
}
[data-testid="stSidebar"] .stButton > button:hover {
    border-color: var(--cy);
    box-shadow: 0 0 16px rgba(0,229,255,0.3);
    color: var(--txt);
}

/* file uploader */
[data-testid="stFileUploader"] section {
    background: var(--bg-2);
    border: 1px dashed rgba(0,229,255,0.3);
    border-radius: 8px;
}

/* expander */
.streamlit-expanderHeader {
    background: var(--bg-1) !important;
    border-radius: 8px !important;
    border: 1px solid var(--line) !important;
}

hr { border-color: var(--line) !important; }

/* section headers with terminal prefix */
.term-h {
    font-family: 'JetBrains Mono', monospace;
    color: var(--cy);
    font-size: 0.85rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin: 22px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--line);
}
.term-h::before { content: "▌ "; color: var(--cy); }
</style>
"""

# Plotly theme used everywhere
PLOTLY_TEMPLATE = "plotly_dark"
CHART_BG = "#131829"
GRID_COLOR = "rgba(36,48,73,0.6)"
LINE_COLOR = "#00e5ff"
LINE_GLOW = "rgba(0,229,255,0.15)"
LIMIT_COLOR = "#ff3d6e"
SAFE_FILL = "rgba(0,255,156,0.07)"

UPS_COLORS = ["#00e5ff", "#00ff9c", "#ffb547", "#b388ff", "#ff3d6e"]


def style_fig(fig, height=320, title=None):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        height=height,
        margin=dict(l=20, r=20, t=50 if title else 20, b=20),
        font=dict(family="JetBrains Mono, monospace", size=12, color="#e6edf3"),
        title=dict(text=title, font=dict(size=15, color="#00e5ff"), x=0.01) if title else None,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#e6edf3")),
        hoverlabel=dict(bgcolor="#1a2138", font_size=12, font_family="JetBrains Mono"),
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False, linecolor=GRID_COLOR)
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False, linecolor=GRID_COLOR)
    return fig


# ---------------- helpers ----------------

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
    m = re.search(r"-?\d+\.?\d*", str(val))
    return float(m.group()) if m else None


def parse_excel(file):
    raw = pd.read_excel(file, header=None)
    header_idx = 0
    for i in range(min(10, len(raw))):
        row_vals = [str(v).strip().upper() for v in raw.iloc[i].tolist()]
        if "DATE" in row_vals and "TIME" in row_vals:
            header_idx = i
            break
    df = pd.read_excel(file, header=header_idx)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")
    if "DATE" in df.columns:
        df = df[df["DATE"].notna()]
    if "DATE" in df.columns and "TIME" in df.columns:
        df["Timestamp"] = pd.to_datetime(
            df["DATE"].astype(str) + " " + df["TIME"].astype(str),
            errors="coerce",
        )
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col + " (num)"] = df[col].apply(to_float)
    return df


def find_alerts(df, t):
    alerts, quality = [], []
    for _, row in df.iterrows():
        ts = row.get("Timestamp")
        when = ts.strftime("%H:%M") if pd.notna(ts) else f"{row.get('TIME')}"

        srt = row.get("Server Room Temp (num)")
        if srt is not None:
            if srt < 5:
                quality.append((when, "Server Room Temperature", srt,
                                "Looks like a typo (way too low). Please check the source sheet."))
            elif srt > t["server_temp_max"]:
                alerts.append(("warn", when, "SERVER ROOM TEMP",
                               f"{srt}°C — above safe limit {t['server_temp_max']}°C"))

        urt = row.get("UPS Room Temp (num)")
        if urt is not None and urt > t["ups_temp_max"]:
            alerts.append(("warn", when, "UPS ROOM TEMP",
                           f"{urt}°C — above safe limit {t['ups_temp_max']}°C"))

        pue = row.get("PUE Value (num)")
        if pue is not None:
            if pue < t["pue_min"]:
                quality.append((when, "PUE", pue, "Unusually low — likely data entry error."))
            elif pue > t["pue_max"]:
                alerts.append(("warn", when, "PUE", f"{pue} — above target {t['pue_max']}"))

        dci = row.get("Dry Cooler Inlet Temp (num)")
        if dci is not None and dci > t["dry_cooler_inlet_max"]:
            alerts.append(("warn", when, "DRY COOLER INLET",
                           f"{dci}°C — above limit {t['dry_cooler_inlet_max']}°C"))

        dg = row.get("DG Oil Status (num)")
        if dg is not None and dg < t["dg_oil_min_ltr"]:
            alerts.append(("crit", when, "GENERATOR OIL",
                           f"only {dg} Litres — minimum {t['dg_oil_min_ltr']} Litres. Refill needed."))

        for ups_col in ["UPS-1 Load kW", "UPS-2 Load kW", "UPS-3 Load kW",
                        "UPS-4 Load kw", "UPS-5 Load kW"]:
            v = row.get(ups_col + " (num)")
            if v is not None and v > t["ups_load_max_kw"]:
                short = ups_col.replace(" Load kW", "").replace(" Load kw", "").upper()
                alerts.append(("warn", when, short,
                               f"load {v} kW — above {t['ups_load_max_kw']} kW"))

        amp = row.get("LT Panel Load Amp. (num)")
        if amp is not None and amp > t["lt_panel_amp_max"]:
            alerts.append(("warn", when, "LT PANEL LOAD",
                           f"{amp} Amps — above {t['lt_panel_amp_max']} Amps"))

        for c in STATUS_COLS:
            v = row.get(c)
            if v is not None and pd.notna(v) and str(v).strip().lower() != "normal":
                alerts.append(("crit", when, c.upper(), f"status '{v}' — should be NORMAL."))

    return alerts, quality


def kpi_card(label, value, unit="", sub="", tone="good"):
    cls = {"good": "kpi-good", "warn": "kpi-warn", "bad": "kpi-bad"}[tone]
    return (
        f"<div class='kpi {cls}'>"
        f"<div class='lbl'>{label}</div>"
        f"<div class='val'>{value}<span class='unit'>{unit}</span></div>"
        f"<div class='sub'>{sub}</div>"
        f"</div>"
    )


def tone_for(value, low, high, reverse=False):
    if value is None or pd.isna(value):
        return "good"
    if reverse:
        return "bad" if value < low else "good"
    if value > high: return "bad"
    if value > low:  return "warn"
    return "good"


# ---------------- app ----------------

st.markdown(CSS, unsafe_allow_html=True)

with st.sidebar:
    st.header("◆ Upload Daily Report")
    uploaded = st.file_uploader("Excel file", type=["xlsx", "xls"], label_visibility="collapsed")

    st.markdown("---")
    st.header("◆ Operating Limits")
    t = load_thresholds()
    with st.expander("Edit safe limits"):
        for key, label in PLAIN_LABELS.items():
            step = 0.05 if "pue" in key else (5.0 if "ltr" in key or "amp" in key else 0.5)
            fmt = "%.2f" if "pue" in key else "%.1f"
            t[key] = st.number_input(label, value=float(t[key]), step=step, format=fmt, key=key)
        if st.button("SAVE LIMITS", use_container_width=True):
            save_thresholds(t)
            st.success("Limits saved.")

# topbar
now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.markdown(
    f"<div class='topbar'>"
    f"<div class='title'>▣ PARAM&nbsp;GANGA // NOC</div>"
    f"<div class='meta'><span class='live-dot'></span><b>LIVE</b> &nbsp;|&nbsp; {now_str} IST</div>"
    f"</div>",
    unsafe_allow_html=True,
)

if uploaded is None:
    st.markdown(
        "<div class='section-help'>▸ Upload today's Excel report from the sidebar to begin.</div>",
        unsafe_allow_html=True,
    )
    st.stop()

try:
    df = parse_excel(uploaded)
except Exception as e:
    st.error(f"Could not read file: {e}")
    st.stop()

if df.empty:
    st.warning("This file contains no readings.")
    st.stop()

alerts, quality = find_alerts(df, t)
crit_count = sum(1 for a in alerts if a[0] == "crit")
warn_count = sum(1 for a in alerts if a[0] == "warn")

# ---------- status banner ----------
report_date = df["Timestamp"].dt.date.iloc[0] if "Timestamp" in df.columns and df["Timestamp"].notna().any() else "—"
total_readings = len(df)

if crit_count > 0:
    cls, tag, head, msg = ("banner-critical", "STATUS // CRITICAL", "Action Required",
        f"{crit_count} critical event(s) and {warn_count} warning(s) detected across {total_readings} readings.")
elif warn_count > 0:
    cls, tag, head, msg = ("banner-warn", "STATUS // DEGRADED", "Monitor Closely",
        f"{warn_count} reading(s) crossed safe limits across {total_readings} readings. No critical events.")
else:
    cls, tag, head, msg = ("banner-good", "STATUS // NOMINAL", "All Systems Healthy",
        f"All {total_readings} readings are within safe operating limits.")

st.markdown(
    f"<div class='banner {cls}'>"
    f"<div class='tag'>{tag}</div>"
    f"<h2>{head}</h2>"
    f"<p>Report date: <b style='color:#e6edf3'>{report_date}</b> &nbsp;·&nbsp; {msg}</p>"
    f"</div>",
    unsafe_allow_html=True,
)

# ---------- KPI grid ----------
st.markdown("<div class='term-h'>KEY METRICS</div>", unsafe_allow_html=True)

pue_vals = df.get("PUE Value (num)", pd.Series(dtype=float)).dropna()
pue_clean = pue_vals[pue_vals >= t["pue_min"]]
avg_pue = pue_clean.mean() if len(pue_clean) else None

srt_series = df.get("Server Room Temp (num)", pd.Series(dtype=float))
srt_max = srt_series[srt_series >= 5].max() if len(srt_series.dropna()) else None

dg_min = df.get("DG Oil Status (num)", pd.Series(dtype=float)).min()

ups_cols = ["UPS-1 Load kW (num)", "UPS-2 Load kW (num)", "UPS-3 Load kW (num)",
            "UPS-4 Load kw (num)", "UPS-5 Load kW (num)"]
total_kw = sum(df[c].max() for c in ups_cols if c in df.columns and df[c].notna().any())

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(kpi_card(
        "AVG PUE", f"{avg_pue:.2f}" if avg_pue is not None else "—", "",
        f"target ≤ {t['pue_max']}", tone_for(avg_pue, t["pue_max"]-0.1, t["pue_max"]),
    ), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card(
        "PEAK SERVER TEMP", f"{srt_max:.1f}" if srt_max is not None else "—", "°C",
        f"limit {t['server_temp_max']}°C", tone_for(srt_max, t["server_temp_max"]-1, t["server_temp_max"]),
    ), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card(
        "DG OIL MIN", f"{dg_min:.0f}" if pd.notna(dg_min) else "—", " L",
        f"min {t['dg_oil_min_ltr']:.0f} L", tone_for(dg_min, t["dg_oil_min_ltr"], 9999, reverse=True),
    ), unsafe_allow_html=True)
with c4:
    st.markdown(kpi_card(
        "PEAK TOTAL UPS LOAD", f"{total_kw:.0f}" if total_kw else "—", " kW",
        "all 5 UPS combined", "good",
    ), unsafe_allow_html=True)
with c5:
    total_issues = len(alerts)
    tone = "bad" if crit_count else ("warn" if warn_count else "good")
    st.markdown(kpi_card(
        "INCIDENTS", str(total_issues), "",
        f"{crit_count} crit · {warn_count} warn", tone,
    ), unsafe_allow_html=True)

# ---------- system tiles ----------
st.markdown("<div class='term-h'>SAFETY &amp; SECURITY SUBSYSTEMS</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='section-help'>Each tile is a subsystem. Pulsing red dot = at least one abnormal reading today. "
    "All <b>green</b> = nominal across the day.</div>",
    unsafe_allow_html=True,
)

if any(c in df.columns for c in STATUS_COLS):
    cols = st.columns(4)
    for i, name in enumerate(STATUS_COLS):
        if name not in df.columns:
            continue
        bad_rows = df[df[name].astype(str).str.strip().str.lower() != "normal"]
        ok = len(bad_rows) == 0
        short = name.replace(" System", "").upper()
        with cols[i % 4]:
            st.markdown(
                f"<div class='tile {'tile-ok' if ok else 'tile-bad'}'>"
                f"<b><span class='led'></span>{short}</b>"
                f"<div class='v'>{'NOMINAL · 24/24' if ok else f'ALARM · {len(bad_rows)} hits'}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

# ---------- alerts ----------
st.markdown("<div class='term-h'>EVENT LOG</div>", unsafe_allow_html=True)

if not alerts:
    st.markdown(
        "<div class='section-help' style='border-color:rgba(0,255,156,0.3);background:rgba(0,255,156,0.05)'>"
        "<b>✓ No events.</b> Every reading stayed within safe operating limits.</div>",
        unsafe_allow_html=True,
    )
else:
    crit_alerts = [a for a in alerts if a[0] == "crit"]
    warn_alerts = [a for a in alerts if a[0] == "warn"]
    for sev, when, what, desc in crit_alerts + warn_alerts:
        cls = "crit" if sev == "crit" else ""
        sev_label = "CRITICAL" if sev == "crit" else "WARNING"
        st.markdown(
            f"<div class='alert-card {cls}'>"
            f"<div class='when'>[{when}] · {sev_label}</div>"
            f"<div class='what'>{what}</div>"
            f"<div class='desc'>{desc}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

if quality:
    with st.expander(f"Possible data entry errors in source file ({len(quality)})"):
        st.caption("Flagged as likely typos in the original sheet, not real incidents. Excluded from KPIs and event log.")
        st.dataframe(
            pd.DataFrame(quality, columns=["Time", "Reading", "Value", "Why we flagged it"]),
            use_container_width=True, hide_index=True,
        )

# ---------- charts ----------
st.markdown("<div class='term-h'>TELEMETRY · 24H</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='section-help'>Green band = safe operating zone. Red dashed line = limit. "
    "Hover any point to read the exact value.</div>",
    unsafe_allow_html=True,
)

x = df["Timestamp"] if "Timestamp" in df.columns else df.index

def line_with_band(col, title, low=None, high=None, unit=""):
    if col not in df.columns or not df[col].notna().any():
        return None
    fig = go.Figure()
    if low is not None and high is not None:
        fig.add_hrect(y0=low, y1=high, fillcolor=SAFE_FILL, line_width=0)
    # glow layer
    fig.add_trace(go.Scatter(
        x=x, y=df[col], mode="lines",
        line=dict(color=LINE_GLOW, width=10),
        hoverinfo="skip", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=x, y=df[col], mode="lines+markers",
        line=dict(color=LINE_COLOR, width=2.5),
        marker=dict(size=6, color=LINE_COLOR, line=dict(color="#0a0e1a", width=1)),
        name=title, showlegend=False,
    ))
    if high is not None:
        fig.add_hline(y=high, line_dash="dash", line_color=LIMIT_COLOR, line_width=1.5,
                      annotation_text=f" LIMIT {high}{unit}",
                      annotation_position="top right",
                      annotation_font=dict(color=LIMIT_COLOR, size=10, family="JetBrains Mono"))
    return style_fig(fig, height=300, title=title.upper())

charts = [
    ("Server Room Temp (num)",      "Server Room Temperature",     18,  t["server_temp_max"],     "°C"),
    ("UPS Room Temp (num)",         "UPS Room Temperature",        18,  t["ups_temp_max"],        "°C"),
    ("PUE Value (num)",             "Power Usage Efficiency",      1.0, t["pue_max"],             ""),
    ("Dry Cooler Inlet Temp (num)", "Dry Cooler Inlet",            30,  t["dry_cooler_inlet_max"], "°C"),
    ("LT Panel Load Amp. (num)",    "LT Panel Load",               200, t["lt_panel_amp_max"],    "A"),
    ("Pump Flow (num)",             "Pump Flow",                   None, None,                    ""),
]

for i in range(0, len(charts), 2):
    cols = st.columns(2)
    for j, args in enumerate(charts[i:i+2]):
        fig = line_with_band(*args)
        if fig is not None:
            cols[j].plotly_chart(fig, use_container_width=True)

# UPS combined
ups_cols_present = [c for c in ups_cols if c in df.columns]
if ups_cols_present:
    long = df[["Timestamp"] + ups_cols_present].melt("Timestamp", var_name="UPS", value_name="kW")
    long["UPS"] = (long["UPS"]
                   .str.replace(" Load kW (num)", "", regex=False)
                   .str.replace(" Load kw (num)", "", regex=False))
    fig = px.line(long, x="Timestamp", y="kW", color="UPS", markers=True,
                  color_discrete_sequence=UPS_COLORS)
    fig.update_traces(line=dict(width=2.5), marker=dict(size=6))
    fig.add_hline(y=t["ups_load_max_kw"], line_dash="dash", line_color=LIMIT_COLOR, line_width=1.5,
                  annotation_text=f" LIMIT {t['ups_load_max_kw']} kW",
                  annotation_position="top right",
                  annotation_font=dict(color=LIMIT_COLOR, size=10, family="JetBrains Mono"))
    style_fig(fig, height=380, title="UPS LOAD · ALL UNITS")
    st.plotly_chart(fig, use_container_width=True)

# heatmap
if "Server Room Temp (num)" in df.columns and "Timestamp" in df.columns and df["Timestamp"].notna().any():
    st.markdown("<div class='term-h'>THERMAL MAP</div>", unsafe_allow_html=True)
    heat = df.copy()
    heat["Hour"] = heat["Timestamp"].dt.hour
    heat["Day"] = heat["Timestamp"].dt.date.astype(str)
    pivot = heat.pivot_table(values="Server Room Temp (num)", index="Day", columns="Hour", aggfunc="mean")
    if not pivot.empty:
        fig = px.imshow(
            pivot, color_continuous_scale=[
                (0.0, "#003a5c"), (0.4, "#00e5ff"), (0.65, "#ffb547"), (1.0, "#ff3d6e"),
            ],
            aspect="auto",
            labels=dict(x="Hour of day", y="Date", color="°C"),
            text_auto=".1f",
        )
        style_fig(fig, height=max(220, 80 * len(pivot)))
        st.plotly_chart(fig, use_container_width=True)

# raw data (collapsed)
with st.expander("◆ RAW TELEMETRY · full data table"):
    st.dataframe(df, use_container_width=True, hide_index=True)
