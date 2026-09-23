from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.config import Settings
from backend.schemas import RunRequest
from backend.service import (
    DomainValidationError,
    MissingDataError,
    parse_issue_time,
    run_forecast,
    run_id,
    training_cutoff,
)


def test_training_cutoff_is_ten_minutes_before_issue():
    issue = parse_issue_time("2026-01-31T12:00:00Z")
    assert training_cutoff(issue) == "2026-01-31T11:50:00Z"


def test_parse_issue_time_rejects_non_utc_offset():
    with pytest.raises(DomainValidationError, match="UTC"):
        parse_issue_time("2026-01-31T12:00:00+05:00")


def test_run_id_is_stable():
    issue = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
    assert run_id(issue, 48) == "20260131T1200Z-48h"


def test_run_forecast_calls_both_turbines_and_preserves_horizon(tmp_path: Path):
    calls: list[str] = []

    for turbine_id in ("turbine-1", "turbine-2"):
        (tmp_path / f"{turbine_id}.csv").write_text("fixture", encoding="utf-8")

    def fake_weather(issue_time, turbine_id, horizon_hours, cache_dir):
        calls.append(f"weather:{turbine_id}")
        return {
            "turbine_id": turbine_id,
            "weather_source": "test-weather",
            "weather_model": "test-model",
            "weather_run_utc": "2026-01-31T00:00:00Z",
            "hourly": [
                {
                    "valid_time_utc": f"2026-01-31T{13 + index:02d}:00:00Z",
                    "wind_speed_100m": 5.0,
                }
                for index in range(horizon_hours)
            ],
        }

    def fake_predict(turbine_id, weather_hourly, cutoff, **kwargs):
        calls.append(f"predict:{turbine_id}")
        return {
            "id": turbine_id,
            "latitude": 43.64,
            "longitude": 78.53,
            "hourly": [
                {
                    "valid_time_utc": row["valid_time_utc"],
                    "predicted_normalized_power": 0.5,
                }
                for row in weather_hourly
            ],
        }

    result = run_forecast(
        RunRequest(issue_time_utc="2026-01-31T12:00:00Z", horizon_hours=24),
        Settings(data_dir=tmp_path),
        weather_fetcher=fake_weather,
        predictor=fake_predict,
    )

    assert calls == ["weather:turbine-1", "predict:turbine-1", "weather:turbine-2", "predict:turbine-2"]
    assert result.run_id == "20260131T1200Z-24h"
    assert result.training_cutoff_utc == "2026-01-31T11:50:00Z"
    assert len(result.turbines) == 2
    assert all(len(turbine.hourly) == 24 for turbine in result.turbines)
    assert result.warnings


def test_run_forecast_fails_before_partial_response_when_csv_missing(tmp_path: Path):
    (tmp_path / "turbine-1.csv").write_text("fixture", encoding="utf-8")

    with pytest.raises(MissingDataError, match="turbine-2.csv"):
        run_forecast(
            RunRequest(issue_time_utc="2026-01-31T12:00:00Z", horizon_hours=24),
            Settings(data_dir=tmp_path),
            weather_fetcher=lambda *args: {},
            predictor=lambda *args, **kwargs: {},
        )
