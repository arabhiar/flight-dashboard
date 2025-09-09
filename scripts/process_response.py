#!/usr/bin/env python3
"""
process_response.py
Reads data/raw/response.json and produces:
 - data/processed/summary.json
 - data/history/price_log.csv
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

ROOT = Path(__file__).resolve().parent.parent
RAW_FILE = ROOT / "data" / "raw" / "response.json"
PROC_DIR = ROOT / "data" / "processed"
HIST_DIR = ROOT / "data" / "history"
PROC_DIR.mkdir(parents=True, exist_ok=True)
HIST_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_FILE = PROC_DIR / "summary.json"
HISTORY_CSV = HIST_DIR / "price_log.csv"


def safe_get(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, default)
    return d


def extract_airline(seg):
    try:
        carriers = seg.get("legs", [])[0].get("carriersData", [])
        if not carriers:
            return None
        carrier = carriers[0]
        return (
            carrier.get("marketingCarrier", {}).get("name")
            or carrier.get("name")
            or carrier.get("displayName")
        )
    except Exception:
        return None


def extract_summary(raw):
    resp = raw.get("response", raw)
    data = resp.get("data", {})
    agg = data.get("aggregation", {})

    summary = {
        "totalFlights": agg.get("totalCount", 0),
        "filteredFlights": agg.get("filteredTotalCount", 0),
        "minPrice": safe_get(agg, "minPrice", "units"),
        "durationMin": agg.get("durationMin"),
        "durationMax": agg.get("durationMax"),
        "stops": [],
        "airlines": [],
        "departureSlots": [],
        "offersByStops": {"nonstop": [], "1stop": [], "multistop": []},
    }

    # stops breakdown (from aggregation)
    for s in agg.get("stops", []):
        summary["stops"].append(
            {
                "numberOfStops": s.get("numberOfStops"),
                "count": s.get("count"),
                "cheapestAirline": safe_get(s, "cheapestAirline", "name"),
                "minPrice": safe_get(s, "minPrice", "units"),
            }
        )

    # airlines breakdown
    for a in agg.get("airlines", []):
        summary["airlines"].append(
            {
                "name": a.get("name"),
                "count": a.get("count"),
                "minPrice": safe_get(a, "minPrice", "units"),
                "minPricePerAdult": safe_get(a, "minPricePerAdult", "units"),
            }
        )

    # departure slots
    ft = agg.get("flightTimes", [])
    if ft:
        for dslot in ft[0].get("departure", []):
            summary["departureSlots"].append(
                {"start": dslot.get("start"), "count": dslot.get("count")}
            )

    # offers
    flight_offers = data.get("flightOffers", [])[:50]  # look at first 50
    offers_all = []
    for offer in flight_offers:
        try:
            price = safe_get(offer, "priceBreakdown", "total", "units")
            segs = offer.get("segments", [])
            if not segs:
                continue

            dep_air = safe_get(segs[0], "departureAirport", "cityName")
            arr_air = safe_get(segs[-1], "arrivalAirport", "cityName")
            dep_code = safe_get(segs[0], "departureAirport", "code")
            arr_code = safe_get(segs[-1], "arrivalAirport", "code")
            dep_time = safe_get(segs[0], "departureTime")
            arr_time = safe_get(segs[-1], "arrivalTime")

            total_time_sec = sum(s.get("totalTime", 0) for s in segs)
            duration_minutes = (
                total_time_sec // 60 if isinstance(total_time_sec, int) else None
            )

            airline = extract_airline(segs[0])
            legs = segs[0].get("legs", [])
            num_legs = len(legs)
            if num_legs == 1:
                stop_type = "nonstop"
            elif num_legs == 2:
                stop_type = "1stop"
            else:
                stop_type = "multistop"

            entry = {
                "price": price,
                "airline": airline,
                "from": dep_air,
                "to": arr_air,
                "from_code": dep_code,
                "to_code": arr_code,
                "departure_time": dep_time,
                "arrival_time": arr_time,
                "duration_minutes": duration_minutes,
                "stops": num_legs - 1,  # stops = legs-1
            }
            offers_all.append(entry)
            summary["offersByStops"][stop_type].append(entry)
        except Exception:
            continue

    # sort and keep top 5 cheapest for each stop type
    for k, arr in summary["offersByStops"].items():
        summary["offersByStops"][k] = sorted(arr, key=lambda x: x["price"] or 1e9)[:5]

    summary["topOffers"] = sorted(offers_all, key=lambda x: x["price"] or 1e9)[:10]
    return summary


def write_summary(summary):
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote summary to {SUMMARY_FILE}")


def append_history(min_price):
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
    min_price = summary.get("minPrice")
    try:
        if min_price is not None:
            append_history(min_price)
    except Exception as e:
        print("Failed to append history:", e)


if __name__ == "__main__":
    main()