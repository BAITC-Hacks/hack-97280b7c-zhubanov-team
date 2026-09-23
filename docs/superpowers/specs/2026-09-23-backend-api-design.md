# Wind Farm Forecast Backend Design

## Goal

Provide a small FastAPI backend that turns a simulated issue time into a reproducible 24 or 48 hour normalized-power forecast for both wind turbines. The backend must preserve the official API contract, use only weather runs available at the issue time, and train each turbine model only from observations at or before the training cutoff.

## Scope

### In scope

- `GET /health` for an inexpensive readiness check.
- `POST /api/forecast/run` for one issue time and one 24/48 hour horizon.
- `POST /api/forecast/rolling` for one daily issue at a fixed UTC hour over an inclusive date range.
- Validation of ISO-8601 UTC issue times, exact-hour issue times, and supported horizons.
- Loading the existing archived weather client and per-turbine power-curve model.
- Reading turbine CSV files from a configured data directory.
- Returning weather provenance, model metadata, warnings, and hourly predictions in the fields described by `docs/api-contract.md`.
- Clear HTTP errors for invalid requests, missing input files, unavailable weather data, and invalid model inputs.

### Out of scope

- Authentication, persistence database, background job queue, or automatic scheduler.
- Live execution of operational actions. Forecasts remain recommendations pending human approval.
- February accuracy claims; February actual turbine output is not present in the supplied data.
- Frontend implementation.

## Configuration

The service reads these environment variables, with deterministic local defaults:

- `SOURCE_TIMEZONE=UTC`: timezone used to interpret naive timestamps in organizer CSV files. It is surfaced in warnings until organizer confirmation.
- `DATA_DIR=data/input`: directory containing `turbine-1.csv` and `turbine-2.csv`.
- `WEATHER_CACHE_DIR=data/cache/weather`: directory for archived weather responses.
- `WIND_FEATURE=wind_speed_100m`: selected weather wind feature, limited to the two features supported by the forecast model.

The API does not add `source_timezone` to request payloads; deployment configuration owns this assumption so all runs in one service use the same auditable setting.

## Components and data flow

### Schemas (`backend/schemas.py`)

Pydantic models represent the request and response contract. Request models reject horizons other than 24 or 48, non-UTC timestamps, timestamps with minutes/seconds, reversed rolling date ranges, and invalid issue hours. Response models constrain normalized predictions to `[0, 1]` and require exactly the requested number of hourly points per turbine.

### Forecast service (`backend/service.py`)

`run_forecast(request, settings)` performs the following steps:

1. Parse and validate the issue time.
2. Compute `training_cutoff_utc` from the explicit configured policy (`issue_time - 10 minutes`), matching the existing 10-minute source cadence.
3. Call `fetch_archived_forecast` once per turbine with the configured cache directory and requested horizon.
4. Call `predict` once per turbine with that turbine's weather series, cutoff, timezone, data directory, and configured wind feature.
5. Build one response containing the common weather provenance and two turbine series.
6. Add warnings for the unconfirmed CSV timezone and model assumptions. Do not hide a failed turbine; fail the whole run with an actionable error.

The service never reads observed rows after `training_cutoff_utc`. The existing model enforces that cutoff and the weather client enforces its 12 hour publication buffer.

### Rolling service (`backend/rolling.py`)

For each inclusive UTC date in `first_issue_date..last_issue_date`, construct an issue timestamp at `issue_hour_utc` and call the same single-run service. Return the ordered runs plus coverage metadata. A failure includes the date and underlying reason so a caller can identify which daily issue needs attention.

### FastAPI app (`backend/app.py`)

Create the application with dependency-injected settings and service functions so tests can use temporary CSV/cache directories and a deterministic weather provider. Translate expected domain errors to `400` for request/input validation, `404` for missing configured data files, and `503` for unavailable external weather data or insufficient training data. Unexpected errors remain `500` and are logged by FastAPI.

## API behavior

`POST /api/forecast/run` accepts:

```json
{"issue_time_utc":"2026-01-31T12:00:00Z","horizon_hours":48}
```

It returns the fields in `docs/api-contract.md`: `run_id`, issue and training cutoff timestamps, weather source/model/run metadata, both turbine objects, analysis, and warnings. `run_id` is deterministic from the issue timestamp and horizon so repeated calls can be compared.

`POST /api/forecast/rolling` accepts:

```json
{"first_issue_date":"2026-01-31","last_issue_date":"2026-02-28","issue_hour_utc":12,"horizon_hours":48}
```

It returns one run per day in ascending date order and coverage metadata containing requested dates, completed dates, and any failed dates. A rolling request is bounded to at most 31 issue dates to avoid accidental unbounded external calls.

## Error handling

- Invalid JSON or schema values: FastAPI validation response `422`.
- Domain validation after parsing (for example a non-hour UTC string): `400` with a stable `detail` message.
- Missing CSV file: `404` with the expected path.
- Weather provider timeout, incomplete forecast, or no eligible archived run: `503` with the issue time and turbine id.
- Training data too short or invalid: `422` with the model validation reason.

No endpoint returns placeholder numeric predictions. If either turbine cannot be forecast, the single run fails instead of returning a partial result.

## Testing strategy

- Unit tests for request validation, deterministic run IDs, training cutoff calculation, and rolling date expansion.
- API tests with FastAPI `TestClient` and temporary directories containing minimal valid five-column CSV fixtures.
- Provider tests replace the weather service at the service boundary with deterministic hourly weather rows; no network call is made in tests.
- Regression tests assert exact horizon length, UTC timestamps, `[0,1]` predictions, warning text, and clear status codes for missing files and invalid requests.

## Known assumptions and limitations

- Organizer CSV columns are currently positional as implemented by `forecast.power_curve`; header names are not yet guaranteed.
- The CSV timezone and wind measurement height are assumptions and are exposed in the response warnings.
- The current weather client depends on archived Open-Meteo Single Runs availability and network/cache state.
- No February measured output is available, so the backend exposes forecasts and provenance but does not claim February MAE.
