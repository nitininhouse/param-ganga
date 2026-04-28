import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Param Ganga — Daily Report",
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

# ---------- styles ----------

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif;
    color: #1f2937;
}

.stApp { background: #fafbfc; }

.block-container { padding-top: 2rem; max-width: 1300px; }

h1, h2, h3 {
    font-family: 'Inter', sans-serif;
    color: #111827;
    letter-spacing: -0.015em;
}
h1 { font-size: 1.9rem !important; font-weight: 700; }
h2 { font-size: 1.3rem !important; font-weight: 600; }
h3 { font-size: 1.05rem !important; font-weight: 600; }

/* page header */
.page-head {
    margin-bottom: 22px;
}
.page-head .eyebrow {
    color: #6b7280; font-size: 0.85rem; font-weight: 500;
    text-transform: uppercase; letter-spacing: 0.08em;
    margin-bottom: 4px;
}
.page-head h1 { margin: 0; }
.page-head .sub { color: #6b7280; margin-top: 4px; }

/* status banner */
.banner {
    border-radius: 14px;
    padding: 22px 26px;
    margin-bottom: 24px;
    border: 1px solid;
    display: flex; align-items: center; gap: 18px;
}
.banner .icon {
    width: 48px; height: 48px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem; font-weight: 700; flex-shrink: 0;
}
.banner h2 { margin: 0 0 2px 0 !important; font-size: 1.25rem !important; }
.banner p  { margin: 0; color: #6b7280; font-size: 0.95rem; }

.banner-good     { background: #f0faf3; border-color: #c8ebd0; }
.banner-good h2  { color: #2f7a45 !important; }
.banner-good .icon { background: #d4edda; color: #2f7a45; }

.banner-warn     { background: #fff8ec; border-color: #ffe2b3; }
.banner-warn h2  { color: #9a6406 !important; }
.banner-warn .icon { background: #ffe9c2; color: #9a6406; }

.banner-critical { background: #fef2f3; border-color: #fbcacf; }
.banner-critical h2 { color: #b53241 !important; }
.banner-critical .icon { background: #fbd6db; color: #b53241; }

/* section heading */
.section {
    font-size: 0.78rem; font-weight: 600;
    color: #6b7280; text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 28px 0 14px 0;
}

/* KPI cards */
.kpi {
    background: #ffffff;
    border: 1px solid #eef0f4;
    border-radius: 14px;
    padding: 18px 20px;
    height: 100%;
    transition: all 0.2s ease;
}
.kpi:hover {
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
    transform: translateY(-1px);
}
.kpi .lbl {
    color: #6b7280; font-size: 0.82rem; font-weight: 500;
    margin-bottom: 8px;
}
.kpi .val {
    font-size: 1.85rem; font-weight: 700; line-height: 1.1;
    color: #111827;
}
.kpi .unit { font-size: 0.95rem; color: #9ca3af; margin-left: 4px; font-weight: 500; }
.kpi .sub  { font-size: 0.82rem; color: #9ca3af; margin-top: 6px; }
.kpi .pill {
    display: inline-block; font-size: 0.7rem; font-weight: 600;
    padding: 3px 9px; border-radius: 999px; margin-bottom: 10px;
    letter-spacing: 0.02em;
}
.pill-good { background: #ecf7ee; color: #3a8050; }
.pill-warn { background: #fff3df; color: #a07211; }
.pill-bad  { background: #fde8eb; color: #b53241; }

/* status tiles */
.tile {
    background: #ffffff;
    border: 1px solid #eef0f4;
    border-radius: 12px;
    padding: 14px 16px;
    height: 100%;
    display: flex; align-items: center; gap: 12px;
}
.tile .dot {
    width: 10px; height: 10px; border-radius: 50%;
    flex-shrink: 0;
}
.tile .name { font-weight: 600; color: #1f2937; font-size: 0.95rem; }
.tile .stat { font-size: 0.78rem; color: #9ca3af; }
.tile-ok .dot  { background: #67b574; box-shadow: 0 0 0 4px rgba(103,181,116,0.15); }
.tile-bad     { background: #fef6f7; border-color: #fbcacf; }
.tile-bad .dot { background: #f06a6a; box-shadow: 0 0 0 4px rgba(240,106,106,0.18); }
.tile-bad .name { color: #b53241; }

/* alert cards */
.alert-card {
    background: #ffffff;
    border: 1px solid #eef0f4;
    border-left: 4px solid #f5b53d;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
    transition: all 0.15s;
}
.alert-card:hover { box-shadow: 0 2px 10px rgba(15,23,42,0.04); }
.alert-card.crit { border-left-color: #f06a6a; background: #fef9f9; }
.alert-card .head {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 4px;
}
.alert-card .when { color: #6b7280; font-size: 0.82rem; }
.alert-card .sev {
    font-size: 0.7rem; font-weight: 600;
    padding: 2px 8px; border-radius: 999px;
    background: #fff3df; color: #9a6406;
}
.alert-card.crit .sev { background: #fde8eb; color: #b53241; }
.alert-card .what { font-weight: 600; color: #1f2937; font-size: 1rem; margin-bottom: 2px; }
.alert-card .desc { color: #4b5563; font-size: 0.92rem; }

/* helper */
.help {
    background: #f4f7fb;
    border: 1px solid #e5ebf2;
    border-radius: 10px;
    padding: 10px 14px;
    color: #4b5563;
    font-size: 0.9rem;
    margin-bottom: 14px;
}
.help b { color: #1f2937; }

/* sidebar */
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #eef0f4;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {
    color: #1f2937 !important;
    font-size: 0.85rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}
[data-testid="stSidebar"] .stButton > button {
    background: #4f8cff;
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.15s;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #3b73e0;
    box-shadow: 0 4px 12px rgba(79,140,255,0.25);
}

/* file uploader */
[data-testid="stFileUploader"] section {
    background: #f4f7fb;
    border: 1px dashed #c8d3e3;
    border-radius: 10px;
}

hr { border-color: #eef0f4 !important; }
</style>
"""

PLOTLY_TEMPLATE = "plotly_white"
LINE_COLOR = "#4f8cff"
LIMIT_COLOR = "#f06a6a"
SAFE_FILL = "rgba(103,181,116,0.10)"
GRID_COLOR = "#eef0f4"
UPS_COLORS = ["#4f8cff", "#67b574", "#f5b53d", "#9b7ed1", "#f06a6a"]


def style_fig(fig, height=320, title=None):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        height=height,
        margin=dict(l=20, r=20, t=46 if title else 16, b=20),
        font=dict(family="Inter, sans-serif", size=12, color="#374151"),
        title=dict(text=title, font=dict(size=14, color="#111827", family="Inter"),
                   x=0.01, y=0.96) if title else None,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#374151")),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor="#eef0f4",
                        font_size=12, font_family="Inter", font_color="#1f2937"),
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False,
                     linecolor=GRID_COLOR, tickfont=dict(color="#6b7280"))
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False,
                     linecolor=GRID_COLOR, tickfont=dict(color="#6b7280"))
    return fig


# ---------- helpers ----------

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
        when = ts.strftime("%I:%M %p").lstrip("0") if pd.notna(ts) else f"{row.get('TIME')}"

        srt = row.get("Server Room Temp (num)")
        if srt is not None:
            if srt < 5:
                quality.append((when, "Server Room Temperature", srt,
                                "Looks like a typo (way too low). Please check the source sheet."))
            elif srt > t["server_temp_max"]:
                alerts.append(("warn", when, "Server Room Temperature",
                               f"reached {srt}°C (safe limit is {t['server_temp_max']}°C)"))

        urt = row.get("UPS Room Temp (num)")
        if urt is not None and urt > t["ups_temp_max"]:
            alerts.append(("warn", when, "UPS Room Temperature",
                           f"reached {urt}°C (safe limit is {t['ups_temp_max']}°C)"))

        pue = row.get("PUE Value (num)")
        if pue is not None:
            if pue < t["pue_min"]:
                quality.append((when, "PUE", pue, "Unusually low — likely a data entry error."))
            elif pue > t["pue_max"]:
                alerts.append(("warn", when, "Power Usage Efficiency",
                               f"reached {pue} (target is below {t['pue_max']})"))

        dci = row.get("Dry Cooler Inlet Temp (num)")
        if dci is not None and dci > t["dry_cooler_inlet_max"]:
            alerts.append(("warn", when, "Dry Cooler Inlet Temperature",
                           f"reached {dci}°C (limit is {t['dry_cooler_inlet_max']}°C)"))

        dg = row.get("DG Oil Status (num)")
        if dg is not None and dg < t["dg_oil_min_ltr"]:
            alerts.append(("crit", when, "Generator Oil",
                           f"only {dg} Litres (minimum is {t['dg_oil_min_ltr']} Litres). Refill needed."))

        for ups_col in ["UPS-1 Load kW", "UPS-2 Load kW", "UPS-3 Load kW",
                        "UPS-4 Load kw", "UPS-5 Load kW"]:
            v = row.get(ups_col + " (num)")
            if v is not None and v > t["ups_load_max_kw"]:
                short = ups_col.replace(" Load kW", "").replace(" Load kw", "")
                alerts.append(("warn", when, f"{short} load",
                               f"reached {v} kW (limit is {t['ups_load_max_kw']} kW)"))

        amp = row.get("LT Panel Load Amp. (num)")
        if amp is not None and amp > t["lt_panel_amp_max"]:
            alerts.append(("warn", when, "LT Panel Load",
                           f"reached {amp} Amps (limit is {t['lt_panel_amp_max']} Amps)"))

        for c in STATUS_COLS:
            v = row.get(c)
            if v is not None and pd.notna(v) and str(v).strip().lower() != "normal":
                alerts.append(("crit", when, c.replace(" System", " System"),
                               f"reported '{v}' (should be Normal)"))

    return alerts, quality


def kpi_card(label, value, unit="", sub="", tone="good"):
    pill_label = {"good": "On Target", "warn": "Watch", "bad": "Action Needed"}[tone]
    pill_cls = f"pill-{tone}"
    return (
        f"<div class='kpi'>"
        f"<div class='pill {pill_cls}'>{pill_label}</div>"
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


# ---------- app ----------

if hasattr(st, "html"):
    st.html(CSS)
else:
    st.markdown(CSS, unsafe_allow_html=True)

with st.sidebar:
    st.header("Upload Daily Report")
    uploaded = st.file_uploader("Excel file", type=["xlsx", "xls"], label_visibility="collapsed")

    st.markdown("---")
    st.header("Operating Limits")
    st.caption("Adjust if the engineering team agrees on new safe limits.")
    t = load_thresholds()
    with st.expander("Edit safe limits"):
        for key, label in PLAIN_LABELS.items():
            step = 0.05 if "pue" in key else (5.0 if "ltr" in key or "amp" in key else 0.5)
            fmt = "%.2f" if "pue" in key else "%.1f"
            t[key] = st.number_input(label, value=float(t[key]), step=step, format=fmt, key=key)
        if st.button("Save Limits", use_container_width=True):
            save_thresholds(t)
            st.success("Saved.")

# header
today_str = datetime.now().strftime("%A, %d %B %Y")
st.markdown(
    f"<div class='page-head'>"
    f"<div class='eyebrow'>Daily Operations Report</div>"
    f"<h1>Param Ganga Data Centre</h1>"
    f"<div class='sub'>{today_str}</div>"
    f"</div>",
    unsafe_allow_html=True,
)

if uploaded is None:
    st.markdown(
        "<div class='help'>Please upload today's Excel report from the left panel to begin.</div>",
        unsafe_allow_html=True,
    )
    st.stop()

try:
    df = parse_excel(uploaded)
except Exception as e:
    st.error(f"Could not read this file. Error: {e}")
    st.stop()

if df.empty:
    st.warning("This file does not contain any readings.")
    st.stop()

alerts, quality = find_alerts(df, t)
crit_count = sum(1 for a in alerts if a[0] == "crit")
warn_count = sum(1 for a in alerts if a[0] == "warn")
total_readings = len(df)
report_date = df["Timestamp"].dt.date.iloc[0] if "Timestamp" in df.columns and df["Timestamp"].notna().any() else "—"

# banner
if crit_count > 0:
    cls, icon, head, msg = "banner-critical", "!", "Action needed", \
        f"{crit_count} critical {'issue' if crit_count == 1 else 'issues'} and {warn_count} {'warning' if warn_count == 1 else 'warnings'} found across {total_readings} readings on {report_date}."
elif warn_count > 0:
    cls, icon, head, msg = "banner-warn", "!", "A few things to check", \
        f"{warn_count} {'reading' if warn_count == 1 else 'readings'} crossed the safe limit on {report_date}. No critical issues."
else:
    cls, icon, head, msg = "banner-good", "✓", "Everything looks good", \
        f"All {total_readings} readings on {report_date} are within safe limits."

st.markdown(
    f"<div class='banner {cls}'>"
    f"<div class='icon'>{icon}</div>"
    f"<div><h2>{head}</h2><p>{msg}</p></div>"
    f"</div>",
    unsafe_allow_html=True,
)

# KPI grid
st.markdown("<div class='section'>Today at a glance</div>", unsafe_allow_html=True)

pue_vals = df.get("PUE Value (num)", pd.Series(dtype=float)).dropna()
pue_clean = pue_vals[pue_vals >= t["pue_min"]]
avg_pue = pue_clean.mean() if len(pue_clean) else None

srt_series = df.get("Server Room Temp (num)", pd.Series(dtype=float))
srt_max = srt_series[srt_series >= 5].max() if len(srt_series.dropna()) else None

dg_min = df.get("DG Oil Status (num)", pd.Series(dtype=float)).min()

ups_cols = ["UPS-1 Load kW (num)", "UPS-2 Load kW (num)", "UPS-3 Load kW (num)",
            "UPS-4 Load kw (num)", "UPS-5 Load kW (num)"]
total_kw = sum(df[c].max() for c in ups_cols if c in df.columns and df[c].notna().any())

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(kpi_card(
        "Average Power Usage", f"{avg_pue:.2f}" if avg_pue is not None else "—", "",
        f"Lower is better · Target ≤ {t['pue_max']}",
        tone_for(avg_pue, t["pue_max"]-0.1, t["pue_max"]),
    ), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card(
        "Highest Server Room Temp",
        f"{srt_max:.1f}" if srt_max is not None else "—", "°C",
        f"Should stay below {t['server_temp_max']}°C",
        tone_for(srt_max, t["server_temp_max"]-1, t["server_temp_max"]),
    ), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card(
        "Lowest Generator Oil",
        f"{dg_min:.0f}" if pd.notna(dg_min) else "—", " Ltr",
        f"Should stay above {t['dg_oil_min_ltr']:.0f} Ltr",
        tone_for(dg_min, t["dg_oil_min_ltr"], 9999, reverse=True),
    ), unsafe_allow_html=True)
with c4:
    tone = "bad" if crit_count else ("warn" if warn_count else "good")
    st.markdown(kpi_card(
        "Issues Found Today",
        str(len(alerts)), "",
        f"{crit_count} critical · {warn_count} warning",
        tone,
    ), unsafe_allow_html=True)

# system tiles
st.markdown("<div class='section'>Safety &amp; Security Systems</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='help'>These eight systems should always show <b>Normal</b>. "
    "A red dot means that system reported a problem at some point today.</div>",
    unsafe_allow_html=True,
)

if any(c in df.columns for c in STATUS_COLS):
    cols = st.columns(4)
    for i, name in enumerate(STATUS_COLS):
        if name not in df.columns:
            continue
        bad_rows = df[df[name].astype(str).str.strip().str.lower() != "normal"]
        ok = len(bad_rows) == 0
        short = name.replace(" System", "")
        with cols[i % 4]:
            st.markdown(
                f"<div class='tile {'tile-ok' if ok else 'tile-bad'}'>"
                f"<div class='dot'></div>"
                f"<div><div class='name'>{short}</div>"
                f"<div class='stat'>{'Normal all day' if ok else f'{len(bad_rows)} issue(s) today'}</div></div>"
                f"</div>",
                unsafe_allow_html=True,
            )

# alerts
st.markdown("<div class='section'>Things that need attention</div>", unsafe_allow_html=True)

if not alerts:
    st.markdown(
        "<div class='banner banner-good' style='margin-bottom:0'>"
        "<div class='icon'>✓</div>"
        "<div><h2>Nothing to worry about</h2><p>Every reading was within the safe range today.</p></div>"
        "</div>",
        unsafe_allow_html=True,
    )
else:
    crit_alerts = [a for a in alerts if a[0] == "crit"]
    warn_alerts = [a for a in alerts if a[0] == "warn"]
    for sev, when, what, desc in crit_alerts + warn_alerts:
        cls = "crit" if sev == "crit" else ""
        sev_label = "Critical" if sev == "crit" else "Warning"
        st.markdown(
            f"<div class='alert-card {cls}'>"
            f"<div class='head'><span class='sev'>{sev_label}</span>"
            f"<span class='when'>at {when}</span></div>"
            f"<div class='what'>{what}</div>"
            f"<div class='desc'>{desc}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

if quality:
    with st.expander(f"Possible data entry mistakes in the file ({len(quality)})"):
        st.caption("These look like typos in the source sheet rather than real problems. They are excluded from the alerts above.")
        st.dataframe(
            pd.DataFrame(quality, columns=["Time", "Reading", "Value", "Why we flagged it"]),
            use_container_width=True, hide_index=True,
        )

# charts
st.markdown("<div class='section'>How things changed through the day</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='help'>The shaded green band is the safe range. When the line stays inside the green band, all is well.</div>",
    unsafe_allow_html=True,
)

x = df["Timestamp"] if "Timestamp" in df.columns else df.index

def line_with_band(col, title, low=None, high=None, unit=""):
    if col not in df.columns or not df[col].notna().any():
        return None
    fig = go.Figure()
    if low is not None and high is not None:
        fig.add_hrect(y0=low, y1=high, fillcolor=SAFE_FILL, line_width=0)
    fig.add_trace(go.Scatter(
        x=x, y=df[col], mode="lines+markers",
        line=dict(color=LINE_COLOR, width=2.5, shape="spline", smoothing=0.6),
        marker=dict(size=5, color=LINE_COLOR, line=dict(color="white", width=1)),
        name=title, showlegend=False,
        fill="tozeroy", fillcolor="rgba(79,140,255,0.06)",
    ))
    if high is not None:
        fig.add_hline(y=high, line_dash="dash", line_color=LIMIT_COLOR, line_width=1.5,
                      annotation_text=f"Limit: {high}{unit}",
                      annotation_position="top right",
                      annotation_font=dict(color=LIMIT_COLOR, size=11, family="Inter"))
    return style_fig(fig, height=280, title=title)

charts = [
    ("Server Room Temp (num)",      "Server Room Temperature",     18,  t["server_temp_max"],     "°C"),
    ("UPS Room Temp (num)",         "UPS Room Temperature",        18,  t["ups_temp_max"],        "°C"),
    ("PUE Value (num)",             "Power Usage Efficiency (PUE)", 1.0, t["pue_max"],            ""),
    ("Dry Cooler Inlet Temp (num)", "Dry Cooler Inlet",            30,  t["dry_cooler_inlet_max"], "°C"),
    ("LT Panel Load Amp. (num)",    "LT Panel Load",               200, t["lt_panel_amp_max"],    " A"),
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
    fig.update_traces(line=dict(width=2.2, shape="spline", smoothing=0.6),
                      marker=dict(size=5))
    fig.add_hline(y=t["ups_load_max_kw"], line_dash="dash", line_color=LIMIT_COLOR, line_width=1.5,
                  annotation_text=f"Limit: {t['ups_load_max_kw']} kW",
                  annotation_position="top right",
                  annotation_font=dict(color=LIMIT_COLOR, size=11, family="Inter"))
    style_fig(fig, height=350, title="UPS Loads (each unit)")
    st.plotly_chart(fig, use_container_width=True)

# heatmap
if "Server Room Temp (num)" in df.columns and "Timestamp" in df.columns and df["Timestamp"].notna().any():
    st.markdown("<div class='section'>Hour-by-hour temperature map</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='help'>Each square is one hour. Cooler hours are blue, warmer hours are orange/red.</div>",
        unsafe_allow_html=True,
    )
    heat = df.copy()
    heat["Hour"] = heat["Timestamp"].dt.hour
    heat["Day"] = heat["Timestamp"].dt.date.astype(str)
    pivot = heat.pivot_table(values="Server Room Temp (num)", index="Day", columns="Hour", aggfunc="mean")
    if not pivot.empty:
        fig = px.imshow(
            pivot, color_continuous_scale=[
                (0.0, "#dbeafe"), (0.4, "#a8d0ff"), (0.65, "#f5b53d"), (1.0, "#f06a6a"),
            ],
            aspect="auto",
            labels=dict(x="Hour of day", y="Date", color="°C"),
            text_auto=".1f",
        )
        style_fig(fig, height=max(220, 80 * len(pivot)))
        st.plotly_chart(fig, use_container_width=True)

# raw data
with st.expander("See the full data table from the file"):
    st.dataframe(df, use_container_width=True, hide_index=True)
