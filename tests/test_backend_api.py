from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import create_app


def forecast_fixture() -> dict:
    hours = [
        {
            "valid_time_utc": f"2026-01-31T{13 + index:02d}:00:00Z",
            "predicted_normalized_power": 0.4,
        }
        for index in range(48)
    ]
    return {
        "run_id": "20260131T1200Z",
        "issue_time_utc": "2026-01-31T12:00:00Z",
        "training_cutoff_utc": "2026-01-31T12:00:00Z",
        "weather": {
            "source": "Open-Meteo Single Runs API",
            "model": "ecmwf_ifs",
            "run_time_utc": "2026-01-31T00:00:00Z",
        },
        "turbines": [
            {"id": "turbine-1", "hourly": hours},
            {"id": "turbine-2", "hourly": hours},
        ],
        "analysis": [],
        "warnings": ["scenario"],
    }


def test_health_endpoint():
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_run_endpoint_delegates_to_forecast_service():
    with patch("backend.app.generate_forecast", return_value=forecast_fixture()) as generate:
        response = TestClient(create_app()).post(
            "/api/forecast/run",
            json={"issue_time_utc": "2026-01-31T12:00:00Z", "horizon_hours": 48},
        )

    assert response.status_code == 200
    assert len(response.json()["turbines"]) == 2
    assert all(len(turbine["hourly"]) == 48 for turbine in response.json()["turbines"])
    generate.assert_called_once_with(
        "2026-01-31T12:00:00Z",
        48,
        source_timezone="UTC",
        data_dir="data/input",
    )


def test_run_rejects_non_hour_utc_time():
    response = TestClient(create_app()).post(
        "/api/forecast/run",
        json={"issue_time_utc": "2026-01-31T12:30:00Z", "horizon_hours": 48},
    )
    assert response.status_code == 400


def test_run_maps_missing_input_to_not_found():
    with patch("backend.app.generate_forecast", side_effect=FileNotFoundError("turbine-1.csv")):
        response = TestClient(create_app()).post(
            "/api/forecast/run",
            json={"issue_time_utc": "2026-01-31T12:00:00Z", "horizon_hours": 48},
        )
    assert response.status_code == 404


def test_run_maps_weather_io_failure_to_service_unavailable():
    with patch("backend.app.generate_forecast", side_effect=OSError("weather API timeout")):
        response = TestClient(create_app()).post(
            "/api/forecast/run",
            json={"issue_time_utc": "2026-01-31T12:00:00Z", "horizon_hours": 48},
        )
    assert response.status_code == 503
    assert "weather API timeout" in response.json()["detail"]


def test_rolling_endpoint_returns_runs_and_recalculations():
    rolling = {
        "first_issue_date": "2026-01-31",
        "last_issue_date": "2026-02-01",
        "issue_count": 2,
        "horizon_hours": 48,
        "runs": [forecast_fixture(), forecast_fixture()],
        "recalculations": [],
    }
    with patch("backend.app.generate_rolling_forecasts", return_value=rolling) as generate:
        response = TestClient(create_app()).post(
            "/api/forecast/rolling",
            json={
                "first_issue_date": "2026-01-31",
                "last_issue_date": "2026-02-01",
                "issue_hour_utc": 12,
                "horizon_hours": 48,
            },
        )
    assert response.status_code == 200
    assert response.json()["issue_count"] == 2
    generate.assert_called_once_with(
        "2026-01-31",
        "2026-02-01",
        issue_hour_utc=12,
        horizon_hours=48,
        source_timezone="UTC",
        data_dir="data/input",
    )


def test_rolling_rejects_reversed_dates():
    response = TestClient(create_app()).post(
        "/api/forecast/rolling",
        json={
            "first_issue_date": "2026-02-01",
            "last_issue_date": "2026-01-31",
            "issue_hour_utc": 12,
            "horizon_hours": 48,
        },
    )
    assert response.status_code == 422
