"""Learn a small weather-to-power bias correction from earlier issued forecasts."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from backend.weather import fetch_archived_forecast, parse_utc
from forecast.power_curve import predict
from forecast.validation import hourly_actual_power, validate_issue

CALIBRATION_ISSUES = ("2026-01-20T12:00:00Z", "2026-01-23T12:00:00Z")
LAST_CALIBRATION_VALID_TIME = "2026-01-25T12:00:00Z"
HOLDOUT_ISSUES = ("2026-01-26T12:00:00Z", "2026-01-29T12:00:00Z")


@lru_cache(maxsize=16)
def fit_weather_bias(
    turbine_id: str,
    source_timezone: str,
    data_dir: str = "data/input",
) -> dict:
    """Fit mean(actual - forecast) using only Jan 20/23 archived issues."""
    actual = hourly_actual_power(turbine_id, source_timezone=source_timezone,
                                 data_dir=Path(data_dir))
    residuals = []
    for issue_time in CALIBRATION_ISSUES:
        weather = fetch_archived_forecast(issue_time, turbine_id, 48)
        baseline = predict(turbine_id, weather["hourly"], issue_time,
                           source_timezone=source_timezone, data_dir=Path(data_dir))
        for row in baseline["hourly"]:
            valid = pd.Timestamp(parse_utc(row["valid_time_utc"]))
            observed = actual.get(valid)
            if pd.notna(observed):
                residuals.append(float(observed) - row["predicted_normalized_power"])
    if len(residuals) < 48:
        raise ValueError("Not enough historical issued forecasts to calibrate")
    return {
        "method": "mean_residual_from_archived_forecasts",
        "issue_times_utc": list(CALIBRATION_ISSUES),
        "latest_actual_time_utc": LAST_CALIBRATION_VALID_TIME,
        "aligned_hours": len(residuals),
        "additive_bias_normalized_power": sum(residuals) / len(residuals),
    }


def validate_calibrated_holdout(
    *, source_timezone: str, data_dir: Path | str = Path("data/input")
) -> dict:
    """Evaluate Jan 26/29 after fitting bias only on Jan 20/23."""
    records = []
    for turbine_id in ("turbine-1", "turbine-2"):
        calibration = fit_weather_bias(turbine_id, source_timezone, str(data_dir))
        for issue in HOLDOUT_ISSUES:
            records.append(validate_issue(
                issue, turbine_id, source_timezone=source_timezone, data_dir=data_dir,
                additive_bias_normalized_power=calibration["additive_bias_normalized_power"],
            ))
    total_hours = sum(row["evaluated_hours"] for row in records)
    return {
        "source_timezone_assumption": source_timezone,
        "calibration_issues": list(CALIBRATION_ISSUES),
        "holdout_issues": list(HOLDOUT_ISSUES),
        "evaluated_hours": total_hours,
        "mae_normalized_power": sum(row["absolute_error_sum"] for row in records) / total_hours,
        "records": records,
    }
