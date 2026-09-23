# Wind Farm Forecast Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested FastAPI backend for single and rolling 24/48-hour forecasts for both wind turbines.

**Architecture:** Keep the existing weather client and per-turbine power curve as the calculation core. Add typed request/response schemas, a settings object, an orchestration service for one run, a rolling date service, and thin FastAPI routes that map domain failures to HTTP responses. Inject weather and model functions at service boundaries in tests so the suite is deterministic and offline.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pandas/numpy, pytest, FastAPI TestClient.

**Spec:** `docs/superpowers/specs/2026-09-23-backend-api-design.md`

## Global Constraints

- Preserve `docs/api-contract.md` field names and UTC timestamp format.
- Accept only exact-hour UTC issue times and horizons of 24 or 48 hours.
- Train only from observations at or before `issue_time - 10 minutes`.
- Use only archived weather runs available with the existing 12-hour buffer.
- Never return placeholder predictions or a partial two-turbine result.
- Keep `SOURCE_TIMEZONE`, `DATA_DIR`, `WEATHER_CACHE_DIR`, and `WIND_FEATURE` configurable.
- Do not commit organizer CSV files, secrets, caches, or generated model artifacts.

## Review Focus

- A timestamp with a non-UTC offset or non-zero minutes must receive a clear client error; test in Task 1.
- A 24-hour request must produce exactly 24 continuous points for each turbine; test in Task 3.
- Missing one turbine CSV must fail the complete run with an actionable status; test in Task 3.
- An external weather failure must be reported as service unavailable and must not produce a partial response; test in Task 4.
- A rolling date range must be inclusive, ordered, and capped at 31 dates; test in Task 5.

---

### Task 1: Typed configuration and contract schemas

**Files:**
- Create: `backend/config.py`
- Create: `backend/schemas.py`
- Create: `tests/test_backend_schemas.py`

**Interfaces:**
- `Settings.from_env() -> Settings` exposes `source_timezone: str`, `data_dir: Path`, `weather_cache_dir: Path`, and `wind_feature: str`.
- `RunRequest.issue_time_utc: str`, `RunRequest.horizon_hours: Literal[24, 48]`.
- `RollingRequest.first_issue_date: date`, `last_issue_date: date`, `issue_hour_utc: int`, `horizon_hours: Literal[24, 48]`.
- `ForecastResponse` serializes `run_id`, `issue_time_utc`, `training_cutoff_utc`, `weather`, `turbines`, `analysis`, and `warnings`.

- [ ] **Step 1: Write failing schema tests**

```python
def test_run_request_rejects_non_supported_horizon():
    with pytest.raises(ValidationError):
        RunRequest(issue_time_utc="2026-01-31T12:00:00Z", horizon_hours=12)

def test_rolling_request_rejects_hour_outside_utc_day():
    with pytest.raises(ValidationError):
        RollingRequest(first_issue_date=date(2026, 1, 1), last_issue_date=date(2026, 1, 1), issue_hour_utc=24, horizon_hours=24)
```

- [ ] **Step 2: Run `pytest tests/test_backend_schemas.py -v` and verify it fails because the schemas do not exist.**

- [ ] **Step 3: Implement settings and Pydantic models**

  Parse environment variables without mutating global state. Keep request models responsible for shape/range validation; exact UTC/hour validation will be a service helper because it must produce the stable domain error used by routes.

- [ ] **Step 4: Run the focused tests and verify they pass.**

- [ ] **Step 5: Run `pytest tests/test_backend_schemas.py -v` again after adding tests for response prediction bounds and reversed rolling dates.**

### Task 2: Forecast service helpers and deterministic run metadata

**Files:**
- Create: `backend/service.py`
- Create: `tests/test_backend_service.py`

**Interfaces:**
- `parse_issue_time(value: str) -> datetime` returns timezone-aware UTC exact-hour datetime or raises `DomainValidationError`.
- `training_cutoff(issue_time: datetime) -> str` returns ISO UTC for issue time minus 10 minutes.
- `run_id(issue_time: datetime, horizon_hours: int) -> str` returns a stable identifier such as `20260131T1200Z-48h`.
- `run_forecast(request: RunRequest, settings: Settings, *, weather_fetcher=fetch_archived_forecast, predictor=predict) -> ForecastResponse`.
- `DomainValidationError`, `MissingDataError`, and `WeatherUnavailableError` carry user-facing `detail` strings and optional turbine/issue context.

- [ ] **Step 1: Write failing tests for UTC parsing, cutoff, and deterministic run ID.**

```python
def test_training_cutoff_is_ten_minutes_before_issue():
    issue = parse_issue_time("2026-01-31T12:00:00Z")
    assert training_cutoff(issue) == "2026-01-31T11:50:00Z"

def test_parse_issue_time_rejects_non_utc_offset():
    with pytest.raises(DomainValidationError, match="UTC"):
        parse_issue_time("2026-01-31T12:00:00+05:00")
```

- [ ] **Step 2: Run the focused tests and verify the expected missing-symbol failures.**

- [ ] **Step 3: Implement validation and metadata helpers, then the service orchestration.**

  For each turbine, check the CSV exists before invoking `predict`; call `weather_fetcher(issue_time, turbine_id, horizon, cache_dir)` and `predict(turbine_id, weather["hourly"], cutoff, source_timezone=..., data_dir=..., wind_feature=...)`. Map `FileNotFoundError` to `MissingDataError` and weather/network/value failures to their domain error classes. Build common weather provenance from the first result and add the timezone and wind-height assumption warnings.

- [ ] **Step 4: Add service tests with deterministic fetcher/predictor functions and verify exactly two turbine calls, requested horizon, warnings, and no partial result on the second-turbine failure.**

- [ ] **Step 5: Run `pytest tests/test_backend_service.py -v`.**

### Task 3: FastAPI single-run endpoint

**Files:**
- Create: `backend/app.py`
- Create: `tests/test_backend_api.py`
- Modify: `backend/__init__.py` only if an app export is useful for imports.

**Interfaces:**
- `app = create_app(settings: Settings | None = None, *, forecast_runner=run_forecast, rolling_runner=run_rolling)`.
- `POST /api/forecast/run` accepts `RunRequest` and returns `ForecastResponse` JSON.
- `GET /health` returns `{"status": "ok"}`.

- [ ] **Step 1: Write failing TestClient tests for health and a valid run response.**

```python
def test_run_endpoint_returns_two_turbines_and_requested_points(client):
    response = client.post("/api/forecast/run", json={"issue_time_utc": "2026-01-31T12:00:00Z", "horizon_hours": 24})
    assert response.status_code == 200
    body = response.json()
    assert {t["id"] for t in body["turbines"]} == {"turbine-1", "turbine-2"}
    assert all(len(t["hourly"]) == 24 for t in body["turbines"])
```

- [ ] **Step 2: Run the focused API tests and verify they fail because `backend.app` is absent.**

- [ ] **Step 3: Implement `create_app`, dependency injection, and exception handlers.**

  Use a runner dependency that tests can replace. Return `400` for `DomainValidationError`, `404` for `MissingDataError`, `503` for `WeatherUnavailableError`, and `422` for model/data validation errors. Let FastAPI handle malformed JSON/schema errors as `422`.

- [ ] **Step 4: Add tests for invalid horizon (`422`), non-hour UTC (`400`), missing data (`404`), and weather outage (`503`).**

- [ ] **Step 5: Run `pytest tests/test_backend_api.py -v`.**

### Task 4: Rolling forecast service and endpoint

**Files:**
- Create: `backend/rolling.py`
- Modify: `backend/app.py`
- Modify: `backend/schemas.py` if rolling response types need to be added.
- Create: `tests/test_backend_rolling.py`

**Interfaces:**
- `expand_issue_dates(request: RollingRequest) -> list[datetime]` returns inclusive UTC issue times and rejects ranges longer than 31 dates.
- `run_rolling(request: RollingRequest, settings: Settings, *, forecast_runner=run_forecast) -> RollingResponse` returns ordered `runs`, `requested_dates`, `completed_dates`, and `failed_dates`.
- `POST /api/forecast/rolling` returns `RollingResponse` JSON.

- [ ] **Step 1: Write failing tests for inclusive expansion and the 31-date limit.**

```python
def test_expand_issue_dates_is_inclusive_and_ordered():
    request = RollingRequest(first_issue_date=date(2026, 1, 31), last_issue_date=date(2026, 2, 2), issue_hour_utc=12, horizon_hours=24)
    assert expand_issue_dates(request) == [
        datetime(2026, 1, 31, 12, tzinfo=timezone.utc),
        datetime(2026, 2, 1, 12, tzinfo=timezone.utc),
        datetime(2026, 2, 2, 12, tzinfo=timezone.utc),
    ]
```

- [ ] **Step 2: Run the focused tests and verify the expected missing-symbol failures.**

- [ ] **Step 3: Implement rolling orchestration by constructing `RunRequest` values and calling the injected single-run runner in date order.**

  Preserve successful runs, record a failed date with its reason, and expose the failure metadata. A full rolling request with any failure returns `200` with `failed_dates` so the caller can inspect coverage; the single-run endpoint remains fail-fast.

- [ ] **Step 4: Add the route and API tests for a three-day range and an oversized range.**

- [ ] **Step 5: Run `pytest tests/test_backend_rolling.py tests/test_backend_api.py -v`.**

### Task 5: Documentation, integration checks, and verification

**Files:**
- Modify: `README.md`
- Modify: `docs/api-contract.md` only for fields added by the rolling response or clarified status codes.
- Modify: `tests/test_backend_api.py` if full-suite regression coverage needs a final contract assertion.

- [ ] **Step 1: Add a backend run section to README with `uvicorn backend.app:app --reload`, environment variables, and example curl requests.**

- [ ] **Step 2: Run `pytest` for the entire project and fix only regressions caused by the backend integration.**

- [ ] **Step 3: Run an import smoke check: `python -c "from backend.app import app; print(app.title)"`.**

- [ ] **Step 4: Inspect `git diff --check`, confirm no data/cache files are tracked, and report exact verification output and known limitation that real API runs require organizer CSVs and weather access/cache.**

