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
BROAD_ISSUES = tuple(f"2026-01-{day:02d}T12:00:00Z" for day in range(1, 29, 3))


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
    additive_bias_normalized_power: float = 0.0,
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
        [max(0.0, min(1.0, row["predicted_normalized_power"] + additive_bias_normalized_power))
         for row in result["hourly"]],
        index=pd.DatetimeIndex([parse_utc(row["valid_time_utc"]) for row in result["hourly"]]),
    )
    aligned = pd.DataFrame({"prediction": predictions, "actual": actual.reindex(predictions.index)}).dropna()
    if aligned.empty:
        raise ValueError("No measured power hours align with this forecast; check source timezone")
    errors = np.abs(aligned["prediction"] - aligned["actual"])
    signed_errors = aligned["prediction"] - aligned["actual"]
    recent_actual = actual.loc[
        (actual.index <= issue) & (actual.index > issue - pd.Timedelta(hours=6))
    ].dropna()
    persistence_value = float(recent_actual.mean()) if len(recent_actual) >= 4 else None
    persistence_errors = (
        np.abs(aligned["actual"] - persistence_value)
        if persistence_value is not None else None
    )
    first_day = errors.loc[errors.index <= issue + pd.Timedelta(hours=24)]
    second_day = errors.loc[errors.index > issue + pd.Timedelta(hours=24)]
    return {
        "issue_time_utc": issue.isoformat().replace("+00:00", "Z"),
        "turbine_id": turbine_id,
        "source_timezone_assumption": source_timezone,
        "weather_run_utc": weather["weather_run_utc"],
        "weather_wind_feature": wind_feature,
        "additive_bias_normalized_power": additive_bias_normalized_power,
        "forecast_hours": 48,
        "evaluated_hours": int(len(aligned)),
        "mae_normalized_power": float(errors.mean()),
        "absolute_error_sum": float(errors.sum()),
        "first_24h_mae_normalized_power": float(first_day.mean()) if len(first_day) else None,
        "first_24h_absolute_error_sum": float(first_day.sum()),
        "first_24h_evaluated_hours": int(len(first_day)),
        "second_24h_mae_normalized_power": float(second_day.mean()) if len(second_day) else None,
        "second_24h_absolute_error_sum": float(second_day.sum()),
        "second_24h_evaluated_hours": int(len(second_day)),
        "persistence_6h_mae_normalized_power": float(persistence_errors.mean())
        if persistence_errors is not None else None,
        "persistence_6h_absolute_error_sum": float(persistence_errors.sum())
        if persistence_errors is not None else None,
        "mean_error_normalized_power": float(signed_errors.mean()),
        "mean_prediction_normalized_power": float(aligned["prediction"].mean()),
        "mean_actual_normalized_power": float(aligned["actual"].mean()),
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
    persistence_rows = [row for row in results if row["persistence_6h_absolute_error_sum"] is not None]
    persistence_hours = sum(row["evaluated_hours"] for row in persistence_rows)
    first_hours = sum(row["first_24h_evaluated_hours"] for row in results)
    second_hours = sum(row["second_24h_evaluated_hours"] for row in results)
    return {
        "period": "January 2026 historical forecast issues (not February)",
        "source_timezone_assumption": source_timezone,
        "weather_wind_feature": wind_feature,
        "evaluated_hours": hours,
        "mae_normalized_power": sum(row["absolute_error_sum"] for row in results) / hours,
        "first_24h_mae_normalized_power": (
            sum(row["first_24h_absolute_error_sum"] for row in results) / first_hours
            if first_hours else None
        ),
        "second_24h_mae_normalized_power": (
            sum(row["second_24h_absolute_error_sum"] for row in results) / second_hours
            if second_hours else None
        ),
        "persistence_6h_mae_normalized_power": (
            sum(row["persistence_6h_absolute_error_sum"] for row in persistence_rows)
            / persistence_hours if persistence_hours else None
        ),
        "persistence_evaluated_hours": persistence_hours,
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
    parser.add_argument("--schedule", choices=("initial", "broad"), default="initial")
    args = parser.parse_args()
    print(json.dumps(validate_january(source_timezone=args.source_timezone,
                                      wind_feature=args.wind_feature,
                                      issue_times=BROAD_ISSUES if args.schedule == "broad" else DEFAULT_ISSUES),
                     indent=2))
