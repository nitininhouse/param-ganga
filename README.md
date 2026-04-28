# Param Ganga — Daily Ops Dashboard

A Streamlit dashboard for the daily Param Ganga datacenter report.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 — sir uploads the daily `.xlsx` from the sidebar.

## Deploy

Easiest free option: **Streamlit Community Cloud**

1. Push this folder to a GitHub repo.
2. Go to https://share.streamlit.io → "New app" → pick repo → main file `app.py`.
3. You get a URL like `https://param-ganga.streamlit.app`.
4. Email sir: "Open the dashboard, upload today's Excel."

## Features

- Upload daily Excel → parsed automatically (handles units like `°C`, `kW`, `A`, `Ltr`).
- KPIs: avg PUE, max server temp, min DG oil, breach count.
- Heatmap of server room temp by hour.
- Trend lines for PUE, temps, pump flow, panel load, UPS loads.
- System status tiles (FIRE / VESDA / WLD / etc.) — green if Normal, red otherwise.
- **Alerts tab**: every row that exceeds a configured threshold.
- **Data quality tab**: flags obvious typos (e.g., `02.3°C` Server Temp, `0.1` PUE) separately so they don't trigger false alarms.
- Sidebar: editable thresholds, saved to `thresholds.json`.

## Default thresholds

| Parameter | Default |
|---|---|
| Server Room Temp max | 22 °C |
| UPS Room Temp max | 22 °C |
| PUE max | 1.3 |
| PUE min (data quality) | 0.9 |
| Dry Cooler Inlet max | 40 °C |
| DG Oil min | 470 Ltr |
| UPS Load max | 60 kW |
| LT Panel Load max | 340 A |

Adjust from the sidebar and click "Save thresholds" — they persist across sessions.
