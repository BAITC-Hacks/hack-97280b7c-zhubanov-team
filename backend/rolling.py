"""Daily rolling forecast orchestration."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from backend.config import Settings
from backend.schemas import ForecastResponse, RollingRequest, RollingResponse, RunRequest
from backend.service import DomainValidationError, ForecastServiceError, run_forecast


class RollingRangeError(DomainValidationError, ValueError):
    """Raised when a rolling request would create an unsafe number of runs."""


def expand_issue_dates(request: RollingRequest) -> list[datetime]:
    days = (request.last_issue_date - request.first_issue_date).days + 1
    if days > 31:
        raise RollingRangeError("rolling request may contain at most 31 issue dates")
    return [
        datetime.combine(
            request.first_issue_date + timedelta(days=offset),
            datetime.min.time().replace(hour=request.issue_hour_utc),
            tzinfo=timezone.utc,
        )
        for offset in range(days)
    ]


def run_rolling(
    request: RollingRequest,
    settings: Settings,
    *,
    forecast_runner: Callable[..., ForecastResponse] = run_forecast,
) -> RollingResponse:
    issue_times = expand_issue_dates(request)
    requested_dates = [issue.date().isoformat() for issue in issue_times]
    runs: list[ForecastResponse] = []
    completed_dates: list[str] = []
    failed_dates: list[dict[str, str]] = []

    for issue in issue_times:
        issue_date = issue.date().isoformat()
        issue_value = issue.isoformat().replace("+00:00", "Z")
        run_request = RunRequest(
            issue_time_utc=issue_value,
            horizon_hours=request.horizon_hours,
        )
        try:
            result = forecast_runner(run_request, settings)
        except ForecastServiceError as exc:
            failed_dates.append({"issue_date": issue_date, "detail": exc.detail})
        except Exception as exc:
            failed_dates.append({"issue_date": issue_date, "detail": str(exc)})
        else:
            runs.append(result)
            completed_dates.append(issue_date)

    return RollingResponse(
        runs=runs,
        requested_dates=requested_dates,
        completed_dates=completed_dates,
        failed_dates=failed_dates,
    )
