# HackAlem — Wind Farm Forecast Agent

Official case: [Agentic AI for wind farm generation forecasting](https://docs.google.com/document/d/1Fn5IJoj87Fx7IAknG26zkfX8c0eq7feCujd0m66PCgY/edit). Our goal is hourly normalized-power forecasts for two wind turbines over a 24–48-hour horizon, issued repeatedly during February 2026 using weather forecasts available at each issue time.

The organizer supplied two 10-minute CSV histories ending January 31, 2026. They contain no February actual power, so February forecast error cannot yet be measured. See [data audit](docs/data-audit.md), [case map](docs/case-map.md), [API contract](docs/api-contract.md), and [team tasks](docs/team-tasks.md).

The active team schedule is the [four-hour sprint plan](docs/four-hour-sprint.md), with an individual push at the end of every hour.
Copy-ready instructions for each teammate's Codex are in [Codex assignments](docs/codex-assignments.md).

## Data setup

Download the private organizer files into ignored local paths:

- [Turbine 1](https://drive.google.com/file/d/1hubNF3tgc7DbgXxHLpIF6zIBHtvMyzLX/view) → `data/input/turbine-1.csv`
- [Turbine 2](https://drive.google.com/file/d/1_WTrYhZ3-71A9IpkBb9RHPN7ncVaupBk/view) → `data/input/turbine-2.csv`

Never commit these source files.

## Archived weather starter

The first working component fetches an archived ECMWF IFS forecast for a simulated issue time and one turbine. It uses only a model run initialized at least 12 hours earlier, selects 24 or 48 future hourly values, and saves raw responses in ignored `data/cache/weather/` for reproducibility. The 12-hour buffer is a conservative availability assumption, not verified publication metadata.

```powershell
python -m backend.weather 2026-01-31T12:00:00Z turbine-1 --hours 48
python -m unittest discover -s tests -v
```

The weather client is ready. API, UI, rolling February forecasts, and end-to-end validation remain in progress.

The first trained per-turbine power model and its conditional January diagnostic are described in [model validation](docs/model-validation.md). API, UI and full rolling February forecast are still in progress.

## Backend API

Start the forecast API from the repository root:

```powershell
$env:SOURCE_TIMEZONE = "UTC"
$env:DATA_DIR = "data/input"
$env:WEATHER_CACHE_DIR = "data/cache/weather"
$env:WIND_FEATURE = "wind_speed_100m"
uvicorn backend.app:app --reload
```

The service exposes `GET /health`, `POST /api/forecast/run`, and `POST /api/forecast/rolling`. A single run requires both ignored organizer files in `data/input/` and returns a 24 or 48 hour series for each turbine:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/forecast/run `
  -Method Post -ContentType "application/json" `
  -Body '{"issue_time_utc":"2026-01-31T12:00:00Z","horizon_hours":48}'
```

Rolling requests issue one forecast per UTC day in the inclusive date range, capped at 31 dates:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/forecast/rolling `
  -Method Post -ContentType "application/json" `
  -Body '{"first_issue_date":"2026-01-31","last_issue_date":"2026-02-28","issue_hour_utc":12,"horizon_hours":48}'
```

The API reports the configured CSV timezone and wind-height choice as warnings. It does not claim February error metrics because February actual power was not supplied.
