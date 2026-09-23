from datetime import date, datetime, timezone

import pytest

from backend.config import Settings
from backend.rolling import expand_issue_dates, run_rolling
from backend.schemas import ForecastResponse, RollingRequest


def test_expand_issue_dates_is_inclusive_and_ordered():
    request = RollingRequest(
        first_issue_date=date(2026, 1, 31),
        last_issue_date=date(2026, 2, 2),
        issue_hour_utc=12,
        horizon_hours=24,
    )
    assert expand_issue_dates(request) == [
        datetime(2026, 1, 31, 12, tzinfo=timezone.utc),
        datetime(2026, 2, 1, 12, tzinfo=timezone.utc),
        datetime(2026, 2, 2, 12, tzinfo=timezone.utc),
    ]


def test_expand_issue_dates_rejects_more_than_31_dates():
    request = RollingRequest(
        first_issue_date=date(2026, 1, 1),
        last_issue_date=date(2026, 2, 1),
        issue_hour_utc=12,
        horizon_hours=24,
    )
    with pytest.raises(ValueError, match="31"):
        expand_issue_dates(request)


def _run(issue_time_utc: str, horizon_hours: int) -> ForecastResponse:
    return ForecastResponse(
        run_id=issue_time_utc.replace("-", "").replace(":", "") + f"-{horizon_hours}h",
        issue_time_utc=issue_time_utc,
        training_cutoff_utc=issue_time_utc,
        weather={"source": "test", "model": "test", "run_time_utc": issue_time_utc},
        turbines=[{"id": "turbine-1", "hourly": []}, {"id": "turbine-2", "hourly": []}],
        analysis=[],
        warnings=[],
    )


def test_run_rolling_returns_ordered_runs_and_failed_dates(tmp_path):
    seen: list[str] = []

    def fake_runner(request, settings):
        seen.append(request.issue_time_utc)
        if request.issue_time_utc.startswith("2026-02-01"):
            raise RuntimeError("weather outage")
        return _run(request.issue_time_utc, request.horizon_hours)

    request = RollingRequest(
        first_issue_date=date(2026, 1, 31),
        last_issue_date=date(2026, 2, 2),
        issue_hour_utc=12,
        horizon_hours=24,
    )
    result = run_rolling(request, Settings(data_dir=tmp_path), forecast_runner=fake_runner)

    assert seen == [
        "2026-01-31T12:00:00Z",
        "2026-02-01T12:00:00Z",
        "2026-02-02T12:00:00Z",
    ]
    assert result.requested_dates == ["2026-01-31", "2026-02-01", "2026-02-02"]
    assert result.completed_dates == ["2026-01-31", "2026-02-02"]
    assert result.failed_dates == [{"issue_date": "2026-02-01", "detail": "weather outage"}]
