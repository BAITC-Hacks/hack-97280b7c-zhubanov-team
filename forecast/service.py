"""Coordinate weather, per-turbine models and repeated historical issues."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import json

from backend.weather import LOCATIONS, fetch_archived_forecast, parse_utc
from forecast.calibration import LAST_CALIBRATION_VALID_TIME, fit_weather_bias
from forecast.insights import summarize_turbine_forecast
from forecast.power_curve import predict


def generate_forecast(
    issue_time_utc: str,
    horizon_hours: int = 48,
    *,
    source_timezone: str,
    data_dir: Path | str = Path("data/input"),
    calibrate: bool = False,
) -> dict:
    """Produce one contract-shaped forecast using only pre-issue inputs."""
    issue = parse_utc(issue_time_utc)
    if horizon_hours not in (24, 48):
        raise ValueError("horizon_hours must be 24 or 48")
    if calibrate and issue <= parse_utc(LAST_CALIBRATION_VALID_TIME):
        raise ValueError("Calibration observations must predate the forecast issue")
    weather_by_turbine = {
        turbine_id: fetch_archived_forecast(issue_time_utc, turbine_id, horizon_hours)
        for turbine_id in LOCATIONS
    }
    run_times = {item["weather_run_utc"] for item in weather_by_turbine.values()}
    if len(run_times) != 1:
        raise ValueError("Turbines must use the same archived weather model run")

    turbines = []
    for turbine_id, (latitude, longitude) in LOCATIONS.items():
        model_result = predict(
            turbine_id,
            weather_by_turbine[turbine_id]["hourly"],
            issue_time_utc,
            source_timezone=source_timezone,
            data_dir=data_dir,
        )
        if calibrate:
            calibration = fit_weather_bias(turbine_id, source_timezone, str(data_dir))
            offset = calibration["additive_bias_normalized_power"]
            for hour in model_result["hourly"]:
                hour["predicted_normalized_power"] = max(
                    0.0, min(1.0, hour["predicted_normalized_power"] + offset)
                )
            model_result["calibration"] = calibration
        model_result["operator_insight"] = summarize_turbine_forecast(model_result["hourly"])
        turbines.append({**model_result, "latitude": latitude, "longitude": longitude})

    averages = {
        row["id"]: sum(hour["predicted_normalized_power"] for hour in row["hourly"])
        / horizon_hours
        for row in turbines
    }
    return {
        "run_id": issue.strftime("%Y%m%dT%H%MZ"),
        "issue_time_utc": issue.isoformat().replace("+00:00", "Z"),
        "training_cutoff_utc": issue.isoformat().replace("+00:00", "Z"),
        "weather": {
            "source": "Open-Meteo Single Runs API",
            "model": "ecmwf_ifs",
            "run_time_utc": run_times.pop(),
            "availability_buffer_hours": 12,
        },
        "turbines": turbines,
        "analysis": [
            f"Mean forecast normalized power: turbine-1 {averages['turbine-1']:.3f}; "
            f"turbine-2 {averages['turbine-2']:.3f}.",
            "Predictions use an archived weather run available before the issue time.",
            "A per-turbine bias correction was fitted on Jan 20 and 23 archived forecast issues."
            if calibrate else "No weather-forecast bias correction was applied.",
            "Low-generation windows and full-load-hour equivalents are advisory scenario outputs, not MW/MWh.",
        ],
        "warnings": [
            f"Organizer CSV has no declared timezone; interpreted as {source_timezone} for this scenario.",
            "Measured wind-sensor height and rated capacities are unknown; power is normalized, not MW.",
            "February actual power was not supplied; no February error metric is available.",
        ],
    }


def compare_recalculation(previous: dict, current: dict) -> dict:
    """Describe changes on overlapping forecast hours after a new issue/run."""
    if parse_utc(current["issue_time_utc"]) <= parse_utc(previous["issue_time_utc"]):
        raise ValueError("Current issue must be later than previous issue")
    changes = []
    by_id = {row["id"]: row for row in previous["turbines"]}
    for turbine in current["turbines"]:
        earlier = {
            row["valid_time_utc"]: row["predicted_normalized_power"]
            for row in by_id[turbine["id"]]["hourly"]
        }
        differences = [
            row["predicted_normalized_power"] - earlier[row["valid_time_utc"]]
            for row in turbine["hourly"]
            if row["valid_time_utc"] in earlier
        ]
        overlapping = [
            (earlier[row["valid_time_utc"]], row)
            for row in turbine["hourly"]
            if row["valid_time_utc"] in earlier
        ]
        biggest = max(
            overlapping,
            key=lambda pair: abs(pair[1]["predicted_normalized_power"] - pair[0]),
            default=None,
        )
        previous_by_time = {
            row["valid_time_utc"]: row
            for row in by_id[turbine["id"]]["hourly"]
        }
        wind_differences = [
            row["forecast_wind_speed_ms"]
            - previous_by_time[row["valid_time_utc"]]["forecast_wind_speed_ms"]
            for _, row in overlapping
            if "forecast_wind_speed_ms" in row
            and "forecast_wind_speed_ms" in previous_by_time[row["valid_time_utc"]]
        ]
        changes.append({
            "turbine_id": turbine["id"],
            "overlapping_hours": len(differences),
            "mean_change_normalized_power": sum(differences) / len(differences)
            if differences else None,
            "mean_absolute_change_normalized_power": sum(abs(value) for value in differences)
            / len(differences) if differences else None,
            "mean_forecast_wind_change_ms": sum(wind_differences) / len(wind_differences)
            if wind_differences else None,
            "largest_revision": {
                "valid_time_utc": biggest[1]["valid_time_utc"],
                "previous_normalized_power": biggest[0],
                "current_normalized_power": biggest[1]["predicted_normalized_power"],
                "absolute_change_normalized_power": abs(
                    biggest[1]["predicted_normalized_power"] - biggest[0]
                ),
                "previous_forecast_wind_speed_ms": previous_by_time[
                    biggest[1]["valid_time_utc"]
                ].get("forecast_wind_speed_ms"),
                "current_forecast_wind_speed_ms": biggest[1].get("forecast_wind_speed_ms"),
            } if biggest else None,
        })
    return {
        "previous_issue_time_utc": previous["issue_time_utc"],
        "current_issue_time_utc": current["issue_time_utc"],
        "previous_weather_run_utc": previous["weather"]["run_time_utc"],
        "current_weather_run_utc": current["weather"]["run_time_utc"],
        "changes": changes,
    }


def generate_rolling_forecasts(
    first_issue_date: str,
    last_issue_date: str,
    *,
    issue_hour_utc: int = 12,
    horizon_hours: int = 48,
    source_timezone: str,
    data_dir: Path | str = Path("data/input"),
    calibrate: bool = False,
) -> dict:
    """Generate each daily issue, inclusive, and compare successive outputs."""
    first = date.fromisoformat(first_issue_date)
    last = date.fromisoformat(last_issue_date)
    if first > last or (last - first).days > 60:
        raise ValueError("Date range must be ordered and at most 61 days")
    if not 0 <= issue_hour_utc <= 23:
        raise ValueError("issue_hour_utc must be 0..23")

    runs = []
    comparisons = []
    day = first
    while day <= last:
        issue = datetime.combine(day, time(issue_hour_utc), tzinfo=timezone.utc)
        run = generate_forecast(
            issue.isoformat().replace("+00:00", "Z"),
            horizon_hours,
            source_timezone=source_timezone,
            data_dir=data_dir,
            calibrate=calibrate,
        )
        if runs:
            comparisons.append(compare_recalculation(runs[-1], run))
        runs.append(run)
        day += timedelta(days=1)
    return {
        "first_issue_date": first_issue_date,
        "last_issue_date": last_issue_date,
        "issue_count": len(runs),
        "horizon_hours": horizon_hours,
        "runs": runs,
        "recalculations": comparisons,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-timezone", required=True)
    parser.add_argument("--first-issue-date", default="2026-01-31")
    parser.add_argument("--last-issue-date", default="2026-02-28")
    parser.add_argument("--issue-hour-utc", type=int, default=12)
    parser.add_argument("--horizon-hours", type=int, choices=(24, 48), default=48)
    parser.add_argument("--output", type=Path, default=Path("data/cache/rolling-forecasts.json"))
    args = parser.parse_args()
    output = generate_rolling_forecasts(
        args.first_issue_date, args.last_issue_date,
        issue_hour_utc=args.issue_hour_utc,
        horizon_hours=args.horizon_hours,
        source_timezone=args.source_timezone,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {output['issue_count']} issues to {args.output}")
