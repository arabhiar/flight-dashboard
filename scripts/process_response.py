#!/usr/bin/env python3
"""
process_response.py
Reads data/raw/response.json and produces:
 - data/processed/summary.json (min price, counts, airlines, stops breakdown, top offers)
 - data/history/price_log.csv (date, min_price)
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv

ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = ROOT / "data" / "raw" / "response.json"
PROC_DIR = ROOT / "data" / "processed"
HIST_DIR = ROOT / "data" / "history"
PROC_DIR.mkdir(parents=True, exist_ok=True)
HIST_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_FILE = PROC_DIR / "summary.json"
HISTORY_CSV = HIST_DIR / "price_log.csv"

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def extract_airline(seg):
    try:
        carriers = seg.get("legs", [])[0].get("carriersData", [])
        if not carriers:
            return None
        carrier = carriers[0]
        # Try different possible fields
        return (
            carrier.get("marketingCarrier", {}).get("name")
            or carrier.get("name")
            or carrier.get("displayName")
        )
    except Exception:
        return None

def safe_get(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d

def extract_summary(raw):
    resp = raw.get("response", raw)  # support both wrapped and raw
    data = resp.get("data", {})
    agg = data.get("aggregation", {})

    summary = {
        "totalFlights": agg.get("totalCount", 0),
        "filteredFlights": agg.get("filteredTotalCount", 0),
        "minPrice": safe_get(agg, "minPrice", "units", default=None),
        "durationMin": agg.get("durationMin"),
        "durationMax": agg.get("durationMax"),
        "stops": [],
        "airlines": [],
        "departureSlots": []
    }

    # stops breakdown
    for s in agg.get("stops", []):
        summary["stops"].append({
            "numberOfStops": s.get("numberOfStops"),
            "count": s.get("count"),
            "cheapestAirline": safe_get(s, "cheapestAirline", "name"),
            "minPrice": safe_get(s, "minPrice", "units")
        })

    # airlines
    for a in agg.get("airlines", []):
        summary["airlines"].append({
            "name": a.get("name"),
            "count": a.get("count"),
            "minPrice": safe_get(a, "minPrice", "units"),
            "minPricePerAdult": safe_get(a, "minPricePerAdult", "units")
        })

    # departure times
    ft = agg.get("flightTimes", [])
    if ft:
        dt = ft[0].get("departure", [])
        for dslot in dt:
            summary["departureSlots"].append({
                "start": dslot.get("start"),
                "count": dslot.get("count")
            })

    # top offers (cheapest N)
    flight_offers = data.get("flightOffers", [])[:10]
    offers = []
    for offer in flight_offers:
        try:
            price = safe_get(offer, "priceBreakdown", "total", "units")
            # pick first segment for quick info
            seg = offer.get("segments", [{}])[0]
            dep_air = safe_get(seg, "departureAirport", "cityName")
            arr_air = safe_get(seg, "arrivalAirport", "cityName")
            dep_code = safe_get(seg, "departureAirport", "code")
            arr_code = safe_get(seg, "arrivalAirport", "code")
            dep_time = safe_get(seg, "departureTime")
            arr_time = safe_get(seg, "arrivalTime")
            total_time_sec = seg.get("totalTime", 0)
            duration_minutes = (total_time_sec // 60) if isinstance(total_time_sec, int) else None
            airline = extract_airline(seg)
            offers.append({
                "price": price,
                "airline": airline,
                "from": dep_air,
                "to": arr_air,
                "from_code": dep_code,
                "to_code": arr_code,
                "departure_time": dep_time,
                "arrival_time": arr_time,
                "duration_minutes": duration_minutes
            })
        except Exception:
            continue

    summary["topOffers"] = offers
    return summary

def write_summary(summary):
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote summary to {SUMMARY_FILE}")

def append_history(min_price):
    # Append date + min_price to CSV (create header if missing)
    write_header = not HISTORY_CSV.exists()
    with open(HISTORY_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["date_ist", "min_price"])
        writer.writerow([datetime.now(IST).strftime("%Y-%m-%dT%H:%M:%S%z"), min_price])
    print(f"Appended history to {HISTORY_CSV}")

def main():
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"{RAW_FILE} missing. Run fetch_flights.py first.")
    with open(RAW_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    summary = extract_summary(raw)
    write_summary(summary)
    # append only when minPrice is present and numeric
    min_price = summary.get("minPrice")
    try:
        if min_price is not None:
            append_history(min_price)
    except Exception as e:
        print("Failed to append history:", e)

if __name__ == "__main__":
    main()