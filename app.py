import json
import re
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

# ---------------- styles ----------------

CSS = """
<style>
html, body, [class*="css"] {
    font-size: 17px;
}
h1 { font-size: 2.4rem !important; }
h2 { font-size: 1.8rem !important; }
h3 { font-size: 1.4rem !important; }

.banner {
    padding: 28px 32px;
    border-radius: 14px;
    color: white;
    margin-bottom: 24px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.08);
}
.banner h2 { color: white; margin: 0 0 6px 0; font-size: 2rem !important; }
.banner p { color: white; margin: 0; font-size: 1.15rem; opacity: 0.95; }

.banner-good     { background: linear-gradient(135deg, #2e7d32 0%, #43a047 100%); }
.banner-warn     { background: linear-gradient(135deg, #ef6c00 0%, #fb8c00 100%); }
.banner-critical { background: linear-gradient(135deg, #b71c1c 0%, #e53935 100%); }

.kpi {
    background: white;
    border-radius: 12px;
    padding: 18px 22px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border-left: 6px solid #1976d2;
    height: 100%;
}
.kpi .lbl   { font-size: 1.05rem; color: #555; margin-bottom: 6px; }
.kpi .val   { font-size: 2.1rem;  font-weight: 700; color: #1a1a1a; line-height: 1.1; }
.kpi .sub   { font-size: 0.95rem; color: #777; margin-top: 6px; }
.kpi-good  { border-left-color: #2e7d32; }
.kpi-warn  { border-left-color: #ef6c00; }
.kpi-bad   { border-left-color: #c62828; }

.tile {
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    height: 100%;
}
.tile b { font-size: 1.05rem; }
.tile .v { font-size: 1.1rem; margin-top: 6px; }
.tile-ok  { background: #e8f5e9; color: #1b5e20; border: 1px solid #c8e6c9; }
.tile-bad { background: #ffebee; color: #b71c1c; border: 1px solid #ffcdd2; }

.alert-card {
    background: #fff3e0;
    border-left: 5px solid #ef6c00;
    padding: 14px 18px;
    border-radius: 10px;
    margin-bottom: 10px;
    font-size: 1.05rem;
}
.alert-card.crit { background: #ffebee; border-left-color: #c62828; }
.alert-card .when { color: #555; font-size: 0.95rem; }
.alert-card .what { font-weight: 600; margin-top: 4px; }

.section-help {
    background: #e3f2fd;
    padding: 12px 16px;
    border-radius: 8px;
    color: #0d47a1;
    margin-bottom: 14px;
    font-size: 1rem;
}
</style>
"""

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
        when = ts.strftime("%I:%M %p") if pd.notna(ts) else f"{row.get('TIME')}"

        srt = row.get("Server Room Temp (num)")
        if srt is not None:
            if srt < 5:
                quality.append((when, "Server Room Temperature", srt,
                                "Reading looks like a typo (way too low). Please check the source sheet."))
            elif srt > t["server_temp_max"]:
                alerts.append(("warn", when, "Server Room Temperature",
                               f"{srt}°C — above safe limit of {t['server_temp_max']}°C"))

        urt = row.get("UPS Room Temp (num)")
        if urt is not None and urt > t["ups_temp_max"]:
            alerts.append(("warn", when, "UPS Room Temperature",
                           f"{urt}°C — above safe limit of {t['ups_temp_max']}°C"))

        pue = row.get("PUE Value (num)")
        if pue is not None:
            if pue < t["pue_min"]:
                quality.append((when, "PUE", pue,
                                "Reading is unusually low — likely a data entry error."))
            elif pue > t["pue_max"]:
                alerts.append(("warn", when, "Power Usage (PUE)",
                               f"{pue} — above target of {t['pue_max']}"))

        dci = row.get("Dry Cooler Inlet Temp (num)")
        if dci is not None and dci > t["dry_cooler_inlet_max"]:
            alerts.append(("warn", when, "Dry Cooler Inlet Temperature",
                           f"{dci}°C — above limit of {t['dry_cooler_inlet_max']}°C"))

        dg = row.get("DG Oil Status (num)")
        if dg is not None and dg < t["dg_oil_min_ltr"]:
            alerts.append(("crit", when, "Generator Oil",
                           f"only {dg} Litres — should be at least {t['dg_oil_min_ltr']} Litres. Refill needed."))

        for ups_col in ["UPS-1 Load kW", "UPS-2 Load kW", "UPS-3 Load kW",
                        "UPS-4 Load kw", "UPS-5 Load kW"]:
            v = row.get(ups_col + " (num)")
            if v is not None and v > t["ups_load_max_kw"]:
                alerts.append(("warn", when, ups_col.replace(" Load kW", "").replace(" Load kw", ""),
                               f"load is {v} kW — above {t['ups_load_max_kw']} kW"))

        amp = row.get("LT Panel Load Amp. (num)")
        if amp is not None and amp > t["lt_panel_amp_max"]:
            alerts.append(("warn", when, "LT Panel Load",
                           f"{amp} Amps — above {t['lt_panel_amp_max']} Amps"))

        for c in STATUS_COLS:
            v = row.get(c)
            if v is not None and pd.notna(v) and str(v).strip().lower() != "normal":
                alerts.append(("crit", when, c.replace(" System", " system"),
                               f"status is '{v}' — should be Normal."))

    return alerts, quality


def kpi_card(label, value, sub="", tone="good"):
    cls = {"good": "kpi-good", "warn": "kpi-warn", "bad": "kpi-bad"}[tone]
    return (
        f"<div class='kpi {cls}'>"
        f"<div class='lbl'>{label}</div>"
        f"<div class='val'>{value}</div>"
        f"<div class='sub'>{sub}</div>"
        f"</div>"
    )


# ---------------- app ----------------

st.markdown(CSS, unsafe_allow_html=True)
st.title("Param Ganga — Daily Operations Report")
st.caption("Upload today's report from the side panel to view the summary.")

with st.sidebar:
    st.header("Step 1 — Upload today's file")
    uploaded = st.file_uploader("Choose the daily Excel file", type=["xlsx", "xls"])

    st.markdown("---")
    st.header("Step 2 — Safe limits")
    st.caption("Adjust these if the engineering team agrees on new safe limits.")
    t = load_thresholds()
    with st.expander("Edit safe limits", expanded=False):
        for key, label in PLAIN_LABELS.items():
            step = 0.05 if "pue" in key else (5.0 if "ltr" in key or "amp" in key else 0.5)
            fmt = "%.2f" if "pue" in key else "%.1f"
            t[key] = st.number_input(label, value=float(t[key]), step=step, format=fmt, key=key)
        if st.button("Save these limits", use_container_width=True):
            save_thresholds(t)
            st.success("Saved. They will be remembered next time.")

if uploaded is None:
    st.info("Please upload the daily Excel file from the left panel to begin.")
    st.stop()

try:
    df = parse_excel(uploaded)
except Exception as e:
    st.error(f"Sorry, could not read this file. Error: {e}")
    st.stop()

if df.empty:
    st.warning("This file does not contain any readings.")
    st.stop()

alerts, quality = find_alerts(df, t)
crit_count = sum(1 for a in alerts if a[0] == "crit")
warn_count = sum(1 for a in alerts if a[0] == "warn")

# ---------- BIG status banner ----------
report_date = df["Timestamp"].dt.date.iloc[0] if "Timestamp" in df.columns and df["Timestamp"].notna().any() else "today"
if crit_count > 0:
    cls, head, msg = "banner-critical", "Action Needed", \
        f"{crit_count} critical issue(s) and {warn_count} warning(s) found in today's report."
elif warn_count > 0:
    cls, head, msg = "banner-warn", "Some Things to Check", \
        f"{warn_count} reading(s) crossed the safe limit today. No critical issues."
else:
    cls, head, msg = "banner-good", "All Good Today", \
        "Every reading is within the safe limits. No issues to report."

st.markdown(
    f"<div class='banner {cls}'>"
    f"<h2>{head}</h2>"
    f"<p>Report date: <b>{report_date}</b> &nbsp;•&nbsp; {msg}</p>"
    f"</div>",
    unsafe_allow_html=True,
)

# ---------- 4 big KPI cards ----------
st.subheader("Today at a glance")

pue_vals = df.get("PUE Value (num)", pd.Series(dtype=float)).dropna()
pue_clean = pue_vals[pue_vals >= t["pue_min"]]
avg_pue = pue_clean.mean() if len(pue_clean) else None

srt_max = df.get("Server Room Temp (num)", pd.Series(dtype=float))
srt_max = srt_max[srt_max >= 5].max() if len(srt_max.dropna()) else None

dg_min = df.get("DG Oil Status (num)", pd.Series(dtype=float)).min()

def tone_for(value, low, high, reverse=False):
    """tone based on whether value is OK/warn/bad given low and high bounds."""
    if value is None or pd.isna(value):
        return "good"
    if reverse:  # higher is better (e.g. DG oil)
        if value < low: return "bad"
        return "good"
    if value > high: return "bad"
    if value > low: return "warn"
    return "good"

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(kpi_card(
        "Average Power Usage (PUE)",
        f"{avg_pue:.2f}" if avg_pue is not None else "—",
        "Lower is better. Target: below " + str(t["pue_max"]),
        tone_for(avg_pue, t["pue_max"] - 0.1, t["pue_max"]),
    ), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card(
        "Highest Server Room Temp",
        f"{srt_max:.1f}°C" if srt_max is not None else "—",
        f"Should stay below {t['server_temp_max']}°C",
        tone_for(srt_max, t["server_temp_max"] - 1, t["server_temp_max"]),
    ), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card(
        "Lowest Generator Oil",
        f"{dg_min:.0f} Ltr" if pd.notna(dg_min) else "—",
        f"Should stay above {t['dg_oil_min_ltr']:.0f} Ltr",
        tone_for(dg_min, t["dg_oil_min_ltr"], 9999, reverse=True),
    ), unsafe_allow_html=True)
with c4:
    total_issues = len(alerts)
    tone = "bad" if crit_count else ("warn" if warn_count else "good")
    st.markdown(kpi_card(
        "Issues Found",
        str(total_issues),
        f"{crit_count} critical, {warn_count} warning",
        tone,
    ), unsafe_allow_html=True)

st.markdown("&nbsp;")

# ---------- system status tiles ----------
st.subheader("Safety & Security Systems")
st.markdown(
    "<div class='section-help'>These eight systems should always show <b>Normal</b>. "
    "A red tile means that system reported a problem at some point today.</div>",
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
                f"<b>{short}</b><div class='v'>{'✓ Normal all day' if ok else f'✗ {len(bad_rows)} issue(s)'}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

st.markdown("&nbsp;")

# ---------- alerts in plain English ----------
st.subheader("Things that need your attention")

if not alerts:
    st.success("Nothing to worry about. Every reading was within the safe range today.")
else:
    st.markdown(
        f"<div class='section-help'>The list below shows every reading that went outside the safe range, "
        f"in the order they happened. Red items are critical and need action. Orange items are warnings to monitor.</div>",
        unsafe_allow_html=True,
    )
    crit_alerts = [a for a in alerts if a[0] == "crit"]
    warn_alerts = [a for a in alerts if a[0] == "warn"]
    for sev, when, what, desc in crit_alerts + warn_alerts:
        cls = "crit" if sev == "crit" else ""
        st.markdown(
            f"<div class='alert-card {cls}'>"
            f"<div class='when'>at {when}</div>"
            f"<div class='what'>{what}: {desc}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

if quality:
    with st.expander(f"Possible data entry mistakes in the file ({len(quality)})"):
        st.caption("These look like typing errors in the source sheet rather than real problems. They are not counted in the issue list above.")
        st.dataframe(
            pd.DataFrame(quality, columns=["Time", "Reading", "Value", "Why we think it's a typo"]),
            use_container_width=True, hide_index=True,
        )

st.markdown("&nbsp;")

# ---------- charts ----------
st.subheader("How things changed through the day")
st.markdown(
    "<div class='section-help'>These charts show the readings hour by hour. "
    "The shaded green band is the safe range — when the line stays inside the green band, all is well.</div>",
    unsafe_allow_html=True,
)

x = df["Timestamp"] if "Timestamp" in df.columns else df.index

def line_with_band(col, title, low=None, high=None, unit=""):
    if col not in df.columns or not df[col].notna().any():
        return None
    fig = go.Figure()
    if low is not None and high is not None:
        fig.add_hrect(y0=low, y1=high, fillcolor="rgba(76,175,80,0.12)", line_width=0)
    fig.add_trace(go.Scatter(
        x=x, y=df[col], mode="lines+markers",
        line=dict(color="#1976d2", width=3),
        marker=dict(size=7),
        name=title,
    ))
    if high is not None:
        fig.add_hline(y=high, line_dash="dash", line_color="#e53935",
                      annotation_text=f"Limit: {high}{unit}", annotation_position="top right")
    fig.update_layout(
        title=dict(text=title, font=dict(size=18)),
        height=320, margin=dict(l=20, r=20, t=50, b=20),
        xaxis_title="Time", yaxis_title=unit if unit else None,
        plot_bgcolor="white",
        font=dict(size=14),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#eee")
    fig.update_yaxes(showgrid=True, gridcolor="#eee")
    return fig

charts = [
    ("Server Room Temp (num)", "Server Room Temperature", 18, t["server_temp_max"], "°C"),
    ("UPS Room Temp (num)",    "UPS Room Temperature",    18, t["ups_temp_max"],    "°C"),
    ("PUE Value (num)",        "Power Usage Efficiency",  1.0, t["pue_max"],         ""),
    ("Dry Cooler Inlet Temp (num)", "Dry Cooler Inlet Temperature", 30, t["dry_cooler_inlet_max"], "°C"),
    ("LT Panel Load Amp. (num)", "LT Panel Load",         200, t["lt_panel_amp_max"], " A"),
    ("Pump Flow (num)",        "Pump Flow",               None, None, ""),
]

for i in range(0, len(charts), 2):
    cols = st.columns(2)
    for j, chart_args in enumerate(charts[i:i+2]):
        fig = line_with_band(*chart_args)
        if fig is not None:
            cols[j].plotly_chart(fig, use_container_width=True)

# UPS combined
ups_cols_present = [c for c in ["UPS-1 Load kW (num)", "UPS-2 Load kW (num)", "UPS-3 Load kW (num)",
                                "UPS-4 Load kw (num)", "UPS-5 Load kW (num)"] if c in df.columns]
if ups_cols_present:
    long = df[["Timestamp"] + ups_cols_present].melt("Timestamp", var_name="UPS", value_name="kW")
    long["UPS"] = (long["UPS"]
                   .str.replace(" Load kW (num)", "", regex=False)
                   .str.replace(" Load kw (num)", "", regex=False))
    fig = px.line(long, x="Timestamp", y="kW", color="UPS", markers=True,
                  title="UPS Loads (each unit, in kW)")
    fig.update_traces(line=dict(width=3), marker=dict(size=7))
    fig.update_layout(height=380, font=dict(size=14), plot_bgcolor="white",
                      title=dict(font=dict(size=18)))
    fig.update_xaxes(showgrid=True, gridcolor="#eee")
    fig.update_yaxes(showgrid=True, gridcolor="#eee")
    fig.add_hline(y=t["ups_load_max_kw"], line_dash="dash", line_color="#e53935",
                  annotation_text=f"Limit: {t['ups_load_max_kw']} kW", annotation_position="top right")
    st.plotly_chart(fig, use_container_width=True)

# heatmap
if "Server Room Temp (num)" in df.columns and "Timestamp" in df.columns and df["Timestamp"].notna().any():
    st.subheader("Hour-by-hour temperature map")
    st.markdown(
        "<div class='section-help'>Each square is one hour. Greener = cooler, redder = warmer.</div>",
        unsafe_allow_html=True,
    )
    heat = df.copy()
    heat["Hour"] = heat["Timestamp"].dt.hour
    heat["Day"] = heat["Timestamp"].dt.date.astype(str)
    pivot = heat.pivot_table(values="Server Room Temp (num)", index="Day", columns="Hour", aggfunc="mean")
    if not pivot.empty:
        fig = px.imshow(
            pivot, color_continuous_scale="RdYlGn_r", aspect="auto",
            labels=dict(x="Hour of day", y="Date", color="°C"), text_auto=".1f",
        )
        fig.update_layout(height=max(220, 80 * len(pivot)), font=dict(size=14))
        st.plotly_chart(fig, use_container_width=True)

# raw data, hidden
with st.expander("See the full data table from the file"):
    st.dataframe(df, use_container_width=True, hide_index=True)
