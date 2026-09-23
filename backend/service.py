"""Domain orchestration for one forecast run."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import ValidationError

from backend.config import Settings
from backend.schemas import ForecastResponse, RunRequest
from backend.weather import LOCATIONS, fetch_archived_forecast, parse_utc
from forecast.power_curve import predict


class ForecastServiceError(Exception):
    """Base class for errors that can be presented by the HTTP API."""

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class DomainValidationError(ForecastServiceError):
    pass


class MissingDataError(ForecastServiceError):
    pass


class WeatherUnavailableError(ForecastServiceError):
    pass


class ModelDataError(ForecastServiceError):
    pass


def parse_issue_time(value: str) -> datetime:
    try:
        issue = parse_utc(value)
    except (TypeError, ValueError) as exc:
        raise DomainValidationError("issue_time_utc must be an ISO-8601 UTC timestamp") from exc
    if issue.minute or issue.second or issue.microsecond:
        raise DomainValidationError("issue_time_utc must fall on an exact UTC hour")
    return issue


def training_cutoff(issue_time: datetime) -> str:
    if issue_time.tzinfo is None or issue_time.utcoffset() != timedelta(0):
        raise DomainValidationError("training cutoff requires a UTC issue time")
    cutoff = issue_time - timedelta(minutes=10)
    return cutoff.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def run_id(issue_time: datetime, horizon_hours: int) -> str:
    if horizon_hours not in (24, 48):
        raise DomainValidationError("horizon_hours must be 24 or 48")
    return f"{issue_time:%Y%m%dT%H%MZ}-{horizon_hours}h"


def _csv_path(settings: Settings, turbine_id: str) -> Path:
    path = settings.data_dir / f"{turbine_id}.csv"
    if not path.is_file():
        raise MissingDataError(f"Required turbine data file is missing: {path}")
    return path


def run_forecast(
    request: RunRequest,
    settings: Settings,
    *,
    weather_fetcher: Callable[..., dict[str, Any]] = fetch_archived_forecast,
    predictor: Callable[..., dict[str, Any]] = predict,
) -> ForecastResponse:
    """Run a complete forecast for both turbines or fail without partial output."""
    issue = parse_issue_time(request.issue_time_utc)
    cutoff = training_cutoff(issue)
    identifier = run_id(issue, request.horizon_hours)

    # Validate the complete input set before any external calls so a missing
    # second turbine cannot leave behind a misleading partial run.
    for turbine_id in LOCATIONS:
        _csv_path(settings, turbine_id)

    weather_results: list[dict[str, Any]] = []
    turbine_results: list[dict[str, Any]] = []
    for turbine_id in LOCATIONS:
        try:
            weather = weather_fetcher(
                issue.isoformat().replace("+00:00", "Z"),
                turbine_id,
                request.horizon_hours,
                settings.weather_cache_dir,
            )
        except ForecastServiceError:
            raise
        except Exception as exc:
            raise WeatherUnavailableError(
                f"Weather forecast unavailable for {turbine_id} at {request.issue_time_utc}: {exc}"
            ) from exc
        weather_results.append(weather)

        try:
            forecast = predictor(
                turbine_id,
                weather["hourly"],
                cutoff,
                source_timezone=settings.source_timezone,
                data_dir=settings.data_dir,
                wind_feature=settings.wind_feature,
            )
        except FileNotFoundError as exc:
            raise MissingDataError(f"Required turbine data file is missing: {exc}") from exc
        except ForecastServiceError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelDataError(f"Could not build forecast for {turbine_id}: {exc}") from exc
        if len(forecast.get("hourly", ())) != request.horizon_hours:
            raise ModelDataError(
                f"Expected {request.horizon_hours} hourly predictions for {turbine_id}"
            )
        turbine_results.append(forecast)

    first_weather = weather_results[0]
    source, model, weather_run = (
        first_weather.get("weather_source", "unknown"),
        first_weather.get("weather_model", "unknown"),
        first_weather.get("weather_run_utc", "unknown"),
    )
    provenance = {
        "source": source,
        "model": model,
        "run_time_utc": weather_run,
    }
    warnings = [
        f"CSV timezone is configured as {settings.source_timezone} and has not been confirmed by the organizer.",
        f"Wind feature {settings.wind_feature} is an assumption because the source measurement height is unknown.",
    ]
    analysis = [f"Forecast relies on archived weather run {weather_run}."]

    normalized_turbines = []
    for turbine_id, result in zip(LOCATIONS, turbine_results):
        latitude, longitude = LOCATIONS[turbine_id]
        normalized_turbines.append(
            {
                **result,
                "id": turbine_id,
                "latitude": result.get("latitude", latitude),
                "longitude": result.get("longitude", longitude),
            }
        )

    try:
        return ForecastResponse(
            run_id=identifier,
            issue_time_utc=issue.isoformat().replace("+00:00", "Z"),
            training_cutoff_utc=cutoff,
            weather=provenance,
            turbines=normalized_turbines,
            analysis=analysis,
            warnings=warnings,
        )
    except ValidationError as exc:
        raise ModelDataError(f"Forecast result failed contract validation: {exc}") from exc
