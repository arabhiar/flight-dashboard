# Flight Dashboard (GitHub Pages)

This project fetches flight price data from Booking.com Flights API (via RapidAPI), generates a static dashboard, and publishes it to GitHub Pages.

## How it works
- Edit `config/query_params.json` in the repository (via GitHub web UI) to change search parameters.
- GitHub Actions runs twice daily (cron), calls the API, processes the response, generates `dashboard/index.html`, and deploys to `gh-pages`.
- Dashboard URL: `https://<your-username>.github.io/<repo-name>/` (GitHub Pages).

## Setup
1. Create repo and push this code.
2. Add secret `RAPIDAPI_KEY` in **Settings → Secrets → Actions**.
3. Optionally test locally:
   ```bash
   export RAPIDAPI_KEY="..."
   pip install -r requirements.txt
   python scripts/fetch_flights.py
   python scripts/process_response.py
   python scripts/generate_dashboard.py
   # then open dashboard/index.html
