from datetime import date

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from backend.schemas import ForecastResponse
from backend.service import (
    DomainValidationError,
    MissingDataError,
    WeatherUnavailableError,
)


def _response(horizon: int = 24) -> ForecastResponse:
    hourly = [
        {
            "valid_time_utc": f"2026-01-31T{13 + index:02d}:00:00Z",
            "predicted_normalized_power": 0.5,
        }
        for index in range(horizon)
    ]
    return ForecastResponse(
        run_id="20260131T1200Z-24h",
        issue_time_utc="2026-01-31T12:00:00Z",
        training_cutoff_utc="2026-01-31T11:50:00Z",
        weather={
            "source": "test-weather",
            "model": "test-model",
            "run_time_utc": "2026-01-31T00:00:00Z",
        },
        turbines=[
            {"id": "turbine-1", "hourly": hourly},
            {"id": "turbine-2", "hourly": hourly},
        ],
        analysis=[],
        warnings=[],
    )


def test_health_endpoint_returns_ok():
    client = TestClient(create_app(Settings()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_run_endpoint_returns_two_turbines_and_requested_points():
    def fake_runner(request, settings):
        return _response(request.horizon_hours)

    client = TestClient(create_app(Settings(), forecast_runner=fake_runner))
    response = client.post(
        "/api/forecast/run",
        json={"issue_time_utc": "2026-01-31T12:00:00Z", "horizon_hours": 24},
    )
    assert response.status_code == 200
    body = response.json()
    assert {t["id"] for t in body["turbines"]} == {"turbine-1", "turbine-2"}
    assert all(len(t["hourly"]) == 24 for t in body["turbines"])


def test_run_endpoint_rejects_invalid_horizon():
    client = TestClient(create_app(Settings(), forecast_runner=lambda *_: _response()))
    response = client.post(
        "/api/forecast/run",
        json={"issue_time_utc": "2026-01-31T12:00:00Z", "horizon_hours": 12},
    )
    assert response.status_code == 422


def test_run_endpoint_maps_non_hour_to_bad_request():
    def invalid_runner(request, settings):
        raise DomainValidationError("issue_time_utc must fall on an exact UTC hour")

    client = TestClient(create_app(Settings(), forecast_runner=invalid_runner))
    response = client.post(
        "/api/forecast/run",
        json={"issue_time_utc": "2026-01-31T12:30:00Z", "horizon_hours": 24},
    )
    assert response.status_code == 400
    assert "exact UTC hour" in response.json()["detail"]


def test_run_endpoint_maps_missing_data_to_not_found():
    def missing_runner(request, settings):
        raise MissingDataError("Required turbine data file is missing: turbine-2.csv")

    client = TestClient(create_app(Settings(), forecast_runner=missing_runner))
    response = client.post(
        "/api/forecast/run",
        json={"issue_time_utc": "2026-01-31T12:00:00Z", "horizon_hours": 24},
    )
    assert response.status_code == 404


def test_run_endpoint_maps_weather_failure_to_service_unavailable():
    def unavailable_runner(request, settings):
        raise WeatherUnavailableError("Weather forecast unavailable for turbine-1")

    client = TestClient(create_app(Settings(), forecast_runner=unavailable_runner))
    response = client.post(
        "/api/forecast/run",
        json={"issue_time_utc": "2026-01-31T12:00:00Z", "horizon_hours": 24},
    )
    assert response.status_code == 503
