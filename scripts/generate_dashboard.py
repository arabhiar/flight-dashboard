#!/usr/bin/env python3
"""
generate_dashboard.py
Builds dashboard with:
- Summary metrics
- Tables by stop type
- Charts (stops breakdown, departure slots, price history)
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv
from jinja2 import Template

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "query_params.json"
SUMMARY_FILE = ROOT / "data" / "processed" / "summary.json"
HISTORY_CSV = ROOT / "data" / "history" / "price_log.csv"
OUT_DIR = ROOT / "dashboard"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_HTML = OUT_DIR / "index.html"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history():
    dates, prices = [], []
    if HISTORY_CSV.exists():
        with open(HISTORY_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Support both old (date_utc) and new (date_ist) column names
                date_col = row.get("date_ist") or row.get("date_utc")
                if date_col:
                    dates.append(date_col)
                    prices.append(int(row["min_price"]))
    return dates, prices


def build_offers_table(offers, title):
    if not offers:
        return f"<div class='card'><h3>{title}</h3><p>No flights available</p></div>"
    rows = "".join(
        f"<tr><td>{o.get('airline')}</td><td>{o.get('from')} ({o.get('from_code')})</td><td>{o.get('to')} ({o.get('to_code')})</td><td>{o.get('departure_time')}</td><td>{o.get('arrival_time')}</td><td>₹{o.get('price')}</td><td>{o.get('stops')} stops</td></tr>"
        for o in offers
    )
    return f"""
    <div class="card">
      <h3>{title}</h3>
      <table>
        <thead><tr><th>Airline</th><th>From</th><th>To</th><th>Departure</th><th>Arrival</th><th>Price</th><th>Stops</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """


TEMPLATE = Template("""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Flight Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body { font-family: Inter, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial; margin: 24px; background:#fafafa; }
    h1 { margin-bottom:8px; }
    .card { border-radius: 8px; padding: 16px; margin-bottom: 20px; background:white; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
    pre { background:#f6f8fa; padding:12px; border-radius:6px; overflow:auto; }
    table { border-collapse: collapse; width: 100%; }
    th, td { text-align:left; padding:8px; border-bottom:1px solid #eee; }
    .top-metrics { display:flex; flex-wrap:wrap; gap:16px; }
    .metric { background:#fff; padding:12px; border-radius:8px; min-width:160px; box-shadow:0 1px 4px rgba(0,0,0,0.04);}
    .metric strong { font-size:1.2em; color:#2c3e50;}
    canvas { max-width: 100%; margin-top: 12px; }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
  <h1>✈️ Flight Dashboard</h1>
  <div class="card">
    <strong>Query</strong>
    <pre>{{ query_str }}</pre>
    <small>Last generated: {{ ts }}</small>
  </div>

  <div class="card top-metrics">
    <div class="metric"><h4>Cheapest overall</h4><strong>₹{{ summary.minPrice or "N/A" }}</strong></div>
    <div class="metric"><h4>Cheapest non-stop</h4><strong>₹{{ cheapest_nonstop or "N/A" }}</strong></div>
    <div class="metric"><h4>Cheapest 1-stop</h4><strong>₹{{ cheapest_onestop or "N/A" }}</strong></div>
    <div class="metric"><h4>Cheapest multi-stop</h4><strong>₹{{ cheapest_multistop or "N/A" }}</strong></div>
  </div>

  {{ non_stop_table | safe }}
  {{ one_stop_table | safe }}
  {{ multi_stop_table | safe }}

  <div class="card">
    <h2>Stops breakdown</h2>
    <canvas id="stopsChart"></canvas>
  </div>

  <div class="card">
    <h2>Departure time slots</h2>
    <canvas id="slotsChart"></canvas>
  </div>

  <div class="card">
    <h2>Price history</h2>
    <canvas id="historyChart"></canvas>
  </div>

  <footer style="margin-top:24px;color:#666;">Built: {{ ts }}</footer>

<script>
const stopsCtx = document.getElementById('stopsChart');
new Chart(stopsCtx, {
    type: 'bar',
    data: {
        labels: {{ stops_labels | safe }},
        datasets: [{
            label: 'Flights',
            data: {{ stops_counts | safe }},
            backgroundColor: 'rgba(54, 162, 235, 0.7)'
        }]
    }
});

const slotsCtx = document.getElementById('slotsChart');
new Chart(slotsCtx, {
    type: 'bar',
    data: {
        labels: {{ slots_labels | safe }},
        datasets: [{
            label: 'Flights',
            data: {{ slots_counts | safe }},
            backgroundColor: 'rgba(255, 159, 64, 0.7)'
        }]
    }
});

const historyCtx = document.getElementById('historyChart');
new Chart(historyCtx, {
    type: 'line',
    data: {
        labels: {{ history_dates | safe }},
        datasets: [{
            label: 'Min Price (₹)',
            data: {{ history_prices | safe }},
            borderColor: 'rgba(75, 192, 192, 1)',
            fill: false
        }]
    }
});
</script>

</body>
</html>
""")


def main():
    try:
        with open(CONFIG, "r", encoding="utf-8") as f:
            query = json.load(f)
    except FileNotFoundError:
        query = {}

    try:
        with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
            summary = json.load(f)
    except FileNotFoundError:
        summary = {"offersByStops": {"nonstop": [], "1stop": [], "multistop": []}}

    # Tables by stop type
    non_stop_table = build_offers_table(summary["offersByStops"].get("nonstop", []), "Top 5 Non-stop Flights")
    one_stop_table = build_offers_table(summary["offersByStops"].get("1stop", []), "Top 5 One-stop Flights")
    multi_stop_table = build_offers_table(summary["offersByStops"].get("multistop", []), "Top 5 Multi-stop Flights")

    # Cheapest metrics
    cheapest_nonstop = summary.get("offersByStops", {}).get("nonstop", [{}])[0].get("price") if summary.get("offersByStops", {}).get("nonstop") else None
    cheapest_onestop = summary.get("offersByStops", {}).get("1stop", [{}])[0].get("price") if summary.get("offersByStops", {}).get("1stop") else None
    cheapest_multistop = summary.get("offersByStops", {}).get("multistop", [{}])[0].get("price") if summary.get("offersByStops", {}).get("multistop") else None

    # Chart data
    stops_labels = [str(s["numberOfStops"]) for s in summary.get("stops", [])]
    stops_counts = [s["count"] for s in summary.get("stops", [])]

    slots_labels = [s["start"] for s in summary.get("departureSlots", [])]
    slots_counts = [s["count"] for s in summary.get("departureSlots", [])]

    history_dates, history_prices = load_history()

    html = TEMPLATE.render(
        query_str=json.dumps(query, indent=2),
        ts=datetime.now(IST).strftime("%Y-%m-%d %H:%M IST"),
        summary=summary,
        non_stop_table=non_stop_table,
        one_stop_table=one_stop_table,
        multi_stop_table=multi_stop_table,
        cheapest_nonstop=cheapest_nonstop,
        cheapest_onestop=cheapest_onestop,
        cheapest_multistop=cheapest_multistop,
        stops_labels=stops_labels,
        stops_counts=stops_counts,
        slots_labels=slots_labels,
        slots_counts=slots_counts,
        history_dates=history_dates,
        history_prices=history_prices,
    )

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote dashboard to {OUT_HTML}")


if __name__ == "__main__":
    main()