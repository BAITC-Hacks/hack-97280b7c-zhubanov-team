from datetime import date

import pytest
from pydantic import ValidationError

from backend.schemas import ForecastResponse, RollingRequest, RunRequest


def test_run_request_rejects_non_supported_horizon():
    with pytest.raises(ValidationError):
        RunRequest(issue_time_utc="2026-01-31T12:00:00Z", horizon_hours=12)


def test_rolling_request_rejects_hour_outside_utc_day():
    with pytest.raises(ValidationError):
        RollingRequest(
            first_issue_date=date(2026, 1, 1),
            last_issue_date=date(2026, 1, 1),
            issue_hour_utc=24,
            horizon_hours=24,
        )


def test_rolling_request_rejects_reversed_dates():
    with pytest.raises(ValidationError):
        RollingRequest(
            first_issue_date=date(2026, 2, 1),
            last_issue_date=date(2026, 1, 1),
            issue_hour_utc=12,
            horizon_hours=24,
        )


def test_forecast_response_rejects_prediction_outside_normalized_range():
    with pytest.raises(ValidationError):
        ForecastResponse(
            run_id="run",
            issue_time_utc="2026-01-31T12:00:00Z",
            training_cutoff_utc="2026-01-31T11:50:00Z",
            weather={
                "source": "test",
                "model": "test",
                "run_time_utc": "2026-01-31T00:00:00Z",
            },
            turbines=[
                {"id": "turbine-1", "hourly": [{"valid_time_utc": "x", "predicted_normalized_power": 1.1}]},
                {"id": "turbine-2", "hourly": []},
            ],
            analysis=[],
            warnings=[],
        )
