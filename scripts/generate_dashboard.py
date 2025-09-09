#!/usr/bin/env python3
"""
generate_dashboard.py
Reads:
 - config/query_params.json
 - data/processed/summary.json
 - data/history/price_log.csv

Generates dashboard/index.html with embedded Plotly charts.
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd
import plotly.express as px
from jinja2 import Template

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "query_params.json"
SUMMARY_FILE = ROOT / "data" / "processed" / "summary.json"
HISTORY_CSV = ROOT / "data" / "history" / "price_log.csv"
OUT_DIR = ROOT / "dashboard"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_HTML = OUT_DIR / "index.html"

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_stops_chart(stops):
    if not stops:
        return "<p>No stops data</p>"
    df = pd.DataFrame(stops)
    # normalize column names
    df = df.rename(columns={"numberOfStops": "stops", "count": "flights", "minPrice": "min_price"})
    fig = px.bar(df, x="stops", y="flights", hover_data=["cheapestAirline", "min_price"], title="Flights by # of stops")
    return fig.to_html(full_html=False, include_plotlyjs="cdn")

def build_departure_chart(slots):
    if not slots:
        return "<p>No departure slot data</p>"
    df = pd.DataFrame(slots)
    df = df.rename(columns={"start": "slot", "count": "count"})
    fig = px.bar(df, x="slot", y="count", title="Departure time slots")
    return fig.to_html(full_html=False, include_plotlyjs=False)  # Plotly JS already included above

def build_history_chart(csv_path):
    if not csv_path.exists():
        return "<p>No history available</p>"
    df = pd.read_csv(csv_path)
    if df.empty:
        return "<p>No history data</p>"
    
    # Handle both old UTC and new IST column names for backward compatibility
    date_col = "date_ist" if "date_ist" in df.columns else "date_utc"
    df[date_col] = pd.to_datetime(df[date_col])
    
    fig = px.line(df, x=date_col, y="min_price", title="Cheapest price over time (IST)")
    return fig.to_html(full_html=False, include_plotlyjs=False)

TEMPLATE = Template("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Flight Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body { font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; margin: 24px; }
    .card { border-radius: 8px; padding: 16px; margin-bottom: 20px; box-shadow: 0 1px 6px rgba(0,0,0,0.06); }
    pre { background:#f6f8fa; padding:12px; border-radius:6px; overflow:auto; }
    table { border-collapse: collapse; width: 100%; }
    th, td { text-align:left; padding:8px; border-bottom:1px solid #eee; }
    .top-metrics { display:flex; gap:16px; }
    .metric { background:#fff; padding:12px; border-radius:8px; min-width:160px; box-shadow:0 1px 4px rgba(0,0,0,0.04);}
  </style>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
</head>
<body>
  <h1>✈️ Flight Dashboard</h1>
  <div class="card">
    <strong>Query (editable in repo at <code>config/query_params.json</code>)</strong>
    <pre>{{ query_str }}</pre>
    <small>Last generated: {{ ts }}</small>
  </div>

  <div class="card top-metrics">
    <div class="metric">
      <h4>Cheapest price</h4>
      <div><strong>₹{{ summary.minPrice }}</strong></div>
    </div>
    <div class="metric">
      <h4>Total flights</h4>
      <div>{{ summary.totalFlights }}</div>
    </div>
    <div class="metric">
      <h4>Filtered flights</h4>
      <div>{{ summary.filteredFlights }}</div>
    </div>
    <div class="metric">
      <h4>Duration range</h4>
      <div>{{ summary.durationMin }} – {{ summary.durationMax }} hrs</div>
    </div>
  </div>

  <div class="card">
    <h3>Stops breakdown</h3>
    {{ stops_chart | safe }}
  </div>

  <div class="card">
    <h3>Departure time slots</h3>
    {{ departure_chart | safe }}
  </div>

  <div class="card">
    <h3>Price history</h3>
    {{ history_chart | safe }}
  </div>

  <div class="card">
    <h3>Top Offers (sample)</h3>
    {% if summary.topOffers %}
      <table>
        <thead><tr><th>Airline</th><th>From</th><th>To</th><th>Departure</th><th>Arrival</th><th>Price</th></tr></thead>
        <tbody>
        {% for o in summary.topOffers %}
          <tr>
            <td>{{ o.airline }}</td>
            <td>{{ o.from }} ({{ o.from_code }})</td>
            <td>{{ o.to }} ({{ o.to_code }})</td>
            <td>{{ o.departure_time }}</td>
            <td>{{ o.arrival_time }}</td>
            <td>₹{{ o.price }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    {% else %}
      <p>No offers found.</p>
    {% endif %}
  </div>

  <div class="card">
    <details>
      <summary>Raw summary JSON (expand)</summary>
      <pre>{{ summary_raw }}</pre>
    </details>
  </div>

  <footer style="margin-top:24px;color:#666;">Built: {{ ts }}</footer>
</body>
</html>
""")

def main():
    # Load files
    query = {}
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            query = json.load(f)
    except FileNotFoundError:
        query = {}

    summary = {}
    try:
        with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
            summary = json.load(f)
    except FileNotFoundError:
        summary = {
            "totalFlights": 0,
            "filteredFlights": 0,
            "minPrice": None,
            "durationMin": None,
            "durationMax": None,
            "stops": [],
            "departureSlots": [],
            "topOffers": []
        }

    # Build charts
    stops_chart = build_stops_chart(summary.get("stops", []))
    departure_chart = build_departure_chart(summary.get("departureSlots", []))
    history_chart = build_history_chart(HISTORY_CSV)

    html = TEMPLATE.render(
        query_str=json.dumps(query, indent=2),
        ts=datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        summary=summary,
        stops_chart=stops_chart,
        departure_chart=departure_chart,
        history_chart=history_chart,
        summary_raw=json.dumps(summary, indent=2)[:20000]
    )

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote dashboard to {OUT_HTML}")

if __name__ == "__main__":
    main()