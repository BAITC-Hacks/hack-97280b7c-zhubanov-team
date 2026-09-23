"""FastAPI adapter for the forecast service implemented in ``forecast/``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.config import Settings
from backend.data import audit_inputs
from backend.schemas import ForecastResponse, RollingRequest, RollingResponse, RunRequest
from backend.weather import parse_utc
from forecast.service import generate_forecast, generate_rolling_forecasts


def _validate_issue_time(value: str) -> str:
    try:
        parsed = parse_utc(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("issue_time_utc must be an ISO-8601 UTC timestamp") from exc
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError("issue_time_utc must fall on an exact UTC hour")
    return value


def create_app(
    settings: Settings | None = None,
    *,
    forecast_generator: Callable[..., dict[str, Any]] | None = None,
    rolling_generator: Callable[..., dict[str, Any]] | None = None,
) -> FastAPI:
    app = FastAPI(title="Wind Farm Forecast API", version="2.0.0")
    runtime = settings or Settings.from_env()
    forecast_generator = forecast_generator or generate_forecast
    rolling_generator = rolling_generator or generate_rolling_forecasts

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(FileNotFoundError)
    async def missing_data_handler(request: Request, exc: FileNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(OSError)
    async def upstream_error_handler(request: Request, exc: OSError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/forecast/run", response_model=ForecastResponse)
    def run_forecast(payload: RunRequest) -> dict[str, Any]:
        issue_time = _validate_issue_time(payload.issue_time_utc)
        audit_inputs(runtime.data_dir, issue_time, runtime.source_timezone)
        return forecast_generator(
            issue_time,
            payload.horizon_hours,
            source_timezone=runtime.source_timezone,
            data_dir=runtime.data_dir,
        )

    @app.post("/api/forecast/rolling", response_model=RollingResponse)
    def run_rolling(payload: RollingRequest) -> dict[str, Any]:
        if (payload.last_issue_date - payload.first_issue_date).days > 60:
            raise ValueError("Date range must be ordered and at most 61 days")
        audit_inputs(runtime.data_dir,
                     f"{payload.last_issue_date.isoformat()}T{payload.issue_hour_utc:02d}:00:00Z",
                     runtime.source_timezone)
        return rolling_generator(
            payload.first_issue_date.isoformat(),
            payload.last_issue_date.isoformat(),
            issue_hour_utc=payload.issue_hour_utc,
            horizon_hours=payload.horizon_hours,
            source_timezone=runtime.source_timezone,
            data_dir=runtime.data_dir,
        )

    return app


app = create_app()
