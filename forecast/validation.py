"""January rolling-origin validation using archived, issue-time weather runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from backend.weather import LOCATIONS, fetch_archived_forecast, parse_utc
from forecast.power_curve import predict

DEFAULT_ISSUES = (
    "2026-01-20T12:00:00Z",
    "2026-01-23T12:00:00Z",
    "2026-01-26T12:00:00Z",
    "2026-01-29T12:00:00Z",
)


def hourly_actual_power(
    turbine_id: str,
    *,
    source_timezone: str,
    data_dir: Path | str = Path("data/input"),
    minimum_records: int = 4,
) -> pd.Series:
    """Hourly target; suppress hours with fewer than four 10-minute samples."""
    if turbine_id not in LOCATIONS:
        raise ValueError(f"Unknown turbine ID: {turbine_id}")
    ZoneInfo(source_timezone)
    raw = pd.read_csv(Path(data_dir) / f"{turbine_id}.csv", encoding="utf-8")
    times = pd.to_datetime(raw.iloc[:, 1], errors="coerce")
    times = times.dt.tz_localize(source_timezone, ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    power = pd.to_numeric(raw.iloc[:, 3], errors="coerce")
    frame = pd.DataFrame({"time": times, "power": power})
    frame = frame.loc[frame["time"].notna() & frame["power"].between(0, 1)]
    hourly = frame.set_index("time")["power"].resample("h").agg(["mean", "count"])
    return hourly["mean"].where(hourly["count"] >= minimum_records)


def validate_issue(
    issue_time_utc: str,
    turbine_id: str,
    *,
    source_timezone: str,
    data_dir: Path | str = Path("data/input"),
    wind_feature: str = "wind_speed_100m",
) -> dict:
    """Fit before issue; compare issued 48-hour forecast with later observed power."""
    issue = parse_utc(issue_time_utc)
    weather = fetch_archived_forecast(issue_time_utc, turbine_id, 48)
    result = predict(
        turbine_id,
        weather["hourly"],
        issue_time_utc,
        source_timezone=source_timezone,
        data_dir=data_dir,
        wind_feature=wind_feature,
    )
    actual = hourly_actual_power(turbine_id, source_timezone=source_timezone, data_dir=data_dir)
    predictions = pd.Series(
        [row["predicted_normalized_power"] for row in result["hourly"]],
        index=pd.DatetimeIndex([parse_utc(row["valid_time_utc"]) for row in result["hourly"]]),
    )
    aligned = pd.DataFrame({"prediction": predictions, "actual": actual.reindex(predictions.index)}).dropna()
    if aligned.empty:
        raise ValueError("No measured power hours align with this forecast; check source timezone")
    errors = np.abs(aligned["prediction"] - aligned["actual"])
    return {
        "issue_time_utc": issue.isoformat().replace("+00:00", "Z"),
        "turbine_id": turbine_id,
        "source_timezone_assumption": source_timezone,
        "weather_run_utc": weather["weather_run_utc"],
        "weather_wind_feature": wind_feature,
        "forecast_hours": 48,
        "evaluated_hours": int(len(aligned)),
        "mae_normalized_power": float(errors.mean()),
        "absolute_error_sum": float(errors.sum()),
        "training_rows": result["training_rows"],
        "latest_training_time_utc": result["latest_training_time_utc"],
    }


def validate_january(
    *,
    source_timezone: str,
    issue_times: tuple[str, ...] = DEFAULT_ISSUES,
    data_dir: Path | str = Path("data/input"),
    wind_feature: str = "wind_speed_100m",
) -> dict:
    results = [
        validate_issue(issue, turbine_id, source_timezone=source_timezone,
                       data_dir=data_dir, wind_feature=wind_feature)
        for issue in issue_times
        for turbine_id in LOCATIONS
    ]
    hours = sum(row["evaluated_hours"] for row in results)
    return {
        "period": "January 2026 historical forecast issues (not February)",
        "source_timezone_assumption": source_timezone,
        "weather_wind_feature": wind_feature,
        "evaluated_hours": hours,
        "mae_normalized_power": sum(row["absolute_error_sum"] for row in results) / hours,
        "issues": results,
        "limitations": [
            "CSV timezone has not been confirmed by the organizer.",
            "Training wind measurement height is unknown; weather 10m/100m selection is an assumption.",
            "No February measured power was supplied, so February MAE cannot be calculated.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-timezone", required=True,
                        help="Explicit timezone assumed for source CSV, e.g. UTC or Asia/Almaty")
    parser.add_argument("--wind-feature", choices=("wind_speed_10m", "wind_speed_100m"),
                        default="wind_speed_100m")
    args = parser.parse_args()
    print(json.dumps(validate_january(source_timezone=args.source_timezone,
                                      wind_feature=args.wind_feature), indent=2))
