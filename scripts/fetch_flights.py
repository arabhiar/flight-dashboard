#!/usr/bin/env python3
"""
fetch_flights.py
Fetches raw response from Booking.com Flights API (via RapidAPI) using query params in config/query_params.json
Saves raw response to data/raw/response.json
"""

import os
import json
from pathlib import Path
import requests
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

# Config
API_URL = "https://booking-com15.p.rapidapi.com/api/v1/flights/searchFlights"
ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "query_params.json"
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = RAW_DIR / "response.json"

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")  # set as GitHub Actions secret

def load_query():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"{CONFIG_PATH} not found. Create config/query_params.json")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def build_params(query):
    params = {}
    for k, v in query.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        params[k] = str(v)
    return params

def call_api(params):
    if not RAPIDAPI_KEY:
        raise EnvironmentError("RAPIDAPI_KEY not set in environment")
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "booking-com15.p.rapidapi.com"
    }
    print(API_URL)
    print(headers)
    print(params)
    resp = requests.get(API_URL, headers=headers, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()

def save_raw(resp):
    meta = {
        "fetched_at": datetime.utcnow().isoformat() + "Z"
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "response": resp}, f, indent=2)
    print(f"Saved raw response to {OUT_FILE}")

def main():
    query = load_query()
    params = build_params(query)
    print("Calling API with params:", params)
    resp = call_api(params)
    save_raw(resp)

if __name__ == "__main__":
    main()