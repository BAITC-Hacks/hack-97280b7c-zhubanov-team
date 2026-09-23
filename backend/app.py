"""FastAPI application for wind-farm generation forecasts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.config import Settings
from backend.schemas import ForecastResponse, RollingRequest, RollingResponse, RunRequest
from backend.service import (
    DomainValidationError,
    ForecastServiceError,
    MissingDataError,
    ModelDataError,
    WeatherUnavailableError,
    run_forecast,
)


def create_app(
    settings: Settings | None = None,
    *,
    forecast_runner: Callable[..., ForecastResponse] = run_forecast,
    rolling_runner: Callable[..., Any] | None = None,
) -> FastAPI:
    app = FastAPI(title="Wind Farm Forecast API", version="1.0.0")
    runtime_settings = settings or Settings.from_env()
    if rolling_runner is None:
        from backend.rolling import run_rolling

        rolling_runner = run_rolling

    @app.exception_handler(DomainValidationError)
    async def domain_validation_handler(request: Request, exc: DomainValidationError):
        return JSONResponse(status_code=400, content={"detail": exc.detail})

    @app.exception_handler(MissingDataError)
    async def missing_data_handler(request: Request, exc: MissingDataError):
        return JSONResponse(status_code=404, content={"detail": exc.detail})

    @app.exception_handler(WeatherUnavailableError)
    async def weather_unavailable_handler(request: Request, exc: WeatherUnavailableError):
        return JSONResponse(status_code=503, content={"detail": exc.detail})

    @app.exception_handler(ModelDataError)
    async def model_data_handler(request: Request, exc: ModelDataError):
        return JSONResponse(status_code=422, content={"detail": exc.detail})

    @app.exception_handler(ForecastServiceError)
    async def forecast_service_handler(request: Request, exc: ForecastServiceError):
        return JSONResponse(status_code=422, content={"detail": exc.detail})

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/forecast/run", response_model=ForecastResponse)
    async def forecast_run(payload: RunRequest) -> ForecastResponse:
        return forecast_runner(payload, runtime_settings)

    @app.post("/api/forecast/rolling", response_model=RollingResponse)
    async def forecast_rolling(payload: RollingRequest) -> RollingResponse:
        return rolling_runner(payload, runtime_settings)

    return app


app = create_app()
