# HackAlem — Wind Farm Forecast Agent

Official case: [Agentic AI for wind farm generation forecasting](https://docs.google.com/document/d/1Fn5IJoj87Fx7IAknG26zkfX8c0eq7feCujd0m66PCgY/edit). Our goal is hourly normalized-power forecasts for two wind turbines over a 24–48-hour horizon, issued repeatedly during February 2026 using weather forecasts available at each issue time.

The organizer supplied two 10-minute CSV histories ending January 31, 2026. They contain no February actual power, so February forecast error cannot yet be measured. See [data audit](docs/data-audit.md), [case map](docs/case-map.md), [API contract](docs/api-contract.md), and [team tasks](docs/team-tasks.md).

The team reports that organizers did not define a timezone for CSV timestamps. All power-validation metrics are conditional on the chosen `source_timezone` scenario; see the two-scenario comparison in [model validation](docs/model-validation.md).

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

The archived weather client and the rolling forecast module are ready. API and UI integration remain in progress.

The trained per-turbine power model, conditional January diagnostic, and verified 29-issue rolling run are described in [model validation](docs/model-validation.md).
Backend integration instructions are in [ML handoff](docs/ml-handoff.md).
The [judge-facing demo loop](docs/demo-differentiator.md) explains the advisory low-generation windows and auditable recalculation comparison.

## Backend API

Install dependencies and start the API from the repository root:

```powershell
python -m pip install -r requirements.txt
$env:SOURCE_TIMEZONE = "Asia/Almaty"
$env:DATA_DIR = "data/input"
uvicorn backend.app:app --reload
```

Check readiness:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Run a 48-hour forecast for both turbines:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/forecast/run `
  -Method Post -ContentType "application/json" `
  -Body '{"issue_time_utc":"2026-01-31T12:00:00Z","horizon_hours":48}'
```

Run the daily sequence and recalculation comparisons:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/forecast/rolling `
  -Method Post -ContentType "application/json" `
  -Body '{"first_issue_date":"2026-01-31","last_issue_date":"2026-02-28","issue_hour_utc":12,"horizon_hours":48}'
```

The API keeps the selected CSV timezone visible as a scenario warning. February actual power was not supplied, so the rolling response reports forecasts and recalculation evidence, not February MAE.

Before forecasting, the API checks both input files for invalid timestamps,
duplicate pre-cutoff rows, ten-minute cadence and invalid measurements.
Hourly aggregation keeps incomplete hours as missing (six samples are required);
it never fills gaps. The ML module continues to train on its original ten-minute
observations. Inspect data coverage with:

```powershell
python -m backend.data --cutoff 2026-01-31T12:00:00Z --source-timezone Asia/Almaty
```

Run all tests with `python -m pip install -r requirements-dev.txt` followed by
`python -m pytest`. The integration test exercises 29 issues through the actual
API and model using explicitly synthetic CSV and weather inputs. It does not
measure real forecast accuracy or verify external weather availability.
