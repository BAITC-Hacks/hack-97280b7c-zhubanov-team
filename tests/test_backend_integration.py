"""Synthetic CSV + synthetic weather; real API, model and rolling service."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from backend.weather import available_run, parse_utc


def test_full_29_issue_flow_with_synthetic_inputs(tmp_path):
    lines = ["ID,time,wind,power,temp"]
    start = datetime(2026, 1, 1)
    for i in range(180):
        speed = (2, 4, 6)[i % 3]
        power = (0.1, 0.4, 0.8)[i % 3]
        lines.append(f"{i},{start + timedelta(minutes=i*10)},{speed},{power},5")
    for name in ("turbine-1", "turbine-2"):
        (tmp_path / f"{name}.csv").write_text("\n".join(lines), encoding="utf-8")

    def weather(issue_value, turbine_id, horizon):
        issue = parse_utc(issue_value)
        return {"weather_run_utc": available_run(issue).isoformat().replace("+00:00", "Z"),
                "hourly": [{"valid_time_utc": (issue + timedelta(hours=i)).isoformat().replace("+00:00", "Z"),
                            "wind_speed_100m": 6.0, "temperature_2m": 5.0}
                           for i in range(1, horizon + 1)]}

    with patch("forecast.service.fetch_archived_forecast", side_effect=weather):
        client = TestClient(create_app(Settings(source_timezone="UTC", data_dir=str(tmp_path))))
        response = client.post("/api/forecast/rolling", json={
            "first_issue_date": "2026-01-31", "last_issue_date": "2026-02-28",
            "issue_hour_utc": 12, "horizon_hours": 48})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["issue_count"] == 29
    assert len(result["recalculations"]) == 28
    total = 0
    for run in result["runs"]:
        issue = parse_utc(run["issue_time_utc"])
        assert parse_utc(run["weather"]["run_time_utc"]) <= issue - timedelta(hours=12)
        assert len(run["turbines"]) == 2
        for turbine in run["turbines"]:
            assert len(turbine["hourly"]) == 48
            assert "operator_insight" in turbine
            for i, row in enumerate(turbine["hourly"], 1):
                assert parse_utc(row["valid_time_utc"]) == issue + timedelta(hours=i)
                assert 0 <= row["predicted_normalized_power"] <= 1
                assert "forecast_wind_speed_ms" in row
                total += 1
    assert total == 2784
