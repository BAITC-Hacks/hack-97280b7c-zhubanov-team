# HackAlem — Wind Farm Forecast Agent

Official case: [Agentic AI for wind farm generation forecasting](https://docs.google.com/document/d/1Fn5IJoj87Fx7IAknG26zkfX8c0eq7feCujd0m66PCgY/edit). Our goal is hourly normalized-power forecasts for two wind turbines over a 24–48-hour horizon, issued repeatedly during February 2026 using weather forecasts available at each issue time.

The organizer supplied two 10-minute CSV histories ending January 31, 2026. They contain no February actual power, so February forecast error cannot yet be measured. See [data audit](docs/data-audit.md), [case map](docs/case-map.md), [API contract](docs/api-contract.md), and [team tasks](docs/team-tasks.md).

The team reports that organizers did not define a timezone for CSV timestamps. All power-validation metrics are conditional on the chosen `source_timezone` scenario; see the two-scenario comparison in [model validation](docs/model-validation.md).

The API and dashboard are integrated. Start from the instructions below or the Russian [installation guide](INSTALL.md). Team ownership is defined in `AGENTS.md`.

## Run the application on Windows

Requires Python 3.12 and Node.js 22.12 or newer in the Node 22 series. From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm --prefix frontend ci
```

Place the organizer CSVs in `data/input/` as described below, then run:

```powershell
.\start_hackalem.ps1 -SourceTimezone UTC
```

Open `http://127.0.0.1:5173`, choose **Backend API**, and click **Пересчитать прогноз**. The dashboard starts with clearly labeled synthetic demo data until an API forecast succeeds. Use **Следующий** to compare successive daily issues. The launcher checks local prerequisites, starts FastAPI, waits for its health endpoint, and runs Vite with its API proxy. Stop with Ctrl+C. Backend logs are under ignored `outputs/`.

`UTC` is an explicit scenario, not an organizer-confirmed timezone. To use the other documented scenario, pass `-SourceTimezone Asia/Almaty`. Use `-DataDir <directory>` for CSVs outside the checkout or `-CheckOnly` to check prerequisites without starting services. No OpenAI or NVIDIA key is required for forecasting.

Optional exploratory notebooks are archived under `notebooks/legacy/`; see `requirements-notebooks.txt` and `start_notebook.ps1`. Their generic baselines are disabled and are not the wind-forecast evaluation.

After a successful API calculation, the dashboard offers **Скачать CSV** for the current issue and **Паспорт JSON** for its forecast, provenance, limitations and available recalculation comparison. Demo, pending, failed and stale selections cannot be exported. If the browser blocks saving, expand **Показать содержимое файла** to copy the generated text. The **Как получен прогноз** section summarizes returned metadata; it is not a live execution log. Recognized backend explanations are shown in Russian; unknown warnings remain visible unchanged. Run `npm --prefix frontend test` for the export and localization checks.

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

The archived weather client, rolling forecast module, API and dashboard are integrated.

The trained per-turbine power model, conditional January diagnostic, and verified 29-issue rolling run are described in [model validation](docs/model-validation.md).
Backend integration instructions are in [ML handoff](docs/ml-handoff.md).
The [judge-facing demo loop](docs/demo-differentiator.md) explains the advisory low-generation windows and auditable recalculation comparison.

## Backend API

Install dependencies and start the API from the repository root:

```powershell
python -m pip install -r requirements.txt
$env:SOURCE_TIMEZONE = "Asia/Almaty"
$env:DATA_DIR = "data/input"
python -m uvicorn backend.app:app --reload
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

## Export a reproducible monthly result

With the virtual environment active and the CSVs under `data/input/`, generate the daily sequence and export it:

```powershell
python -m forecast.service --source-timezone UTC --output outputs/rolling-utc.json
python -m forecast.export --input outputs/rolling-utc.json --output-dir outputs/monthly-utc
```

The default period is January 31–February 28, 2026: 29 issues, 48 hours and two turbines per issue, totaling 2,784 forecast rows. These include overlapping horizons; they are not 2,784 distinct calendar hours. The first generation needs internet access for missing archived weather runs; cached runs are reused. Export itself performs no training or network requests.

The bundle contains `forecasts.csv` and `manifest.json` with source/model, issue and valid times, training cutoff, latest training observation, timezone scenario and SHA-256 hashes. The exporter checks daily coverage, hourly continuity, numeric bounds and declared temporal provenance before publishing the bundle. Choose a new output directory for each export. `exporter_git_revision` identifies the exporter checkout, not the model that originally generated the input.

For timezone sensitivity, repeat with `--source-timezone Asia/Almaty` and separate input/output names. These are scenario forecasts, not verified February accuracy. The weather availability buffer remains an assumption, not proof of actual publication time. Generated bundles stay in ignored `outputs/`; share them explicitly when submitting the project.

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

The GitHub workflow runs these synthetic tests and the frontend lint/build without organizer CSVs or API keys. Local checks with real CSVs and cached archived weather complement this workflow; they are not a measurement of February accuracy.
