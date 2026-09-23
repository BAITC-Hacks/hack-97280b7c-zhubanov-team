"""Fetch archived weather runs without leaking future observations into backtests."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

API_URL = "https://single-runs-api.open-meteo.com/v1/forecast"
MODEL = "ecmwf_ifs"
VARIABLES = ("wind_speed_10m", "wind_speed_100m", "temperature_2m")
RUN_HOURS = (0, 6, 12, 18)
AVAILABILITY_BUFFER = timedelta(hours=12)
LOCATIONS = {
    "turbine-1": (43.643198, 78.538828),
    "turbine-2": (43.645150, 78.535604),
}


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Timestamp must include UTC timezone")
    return parsed.astimezone(timezone.utc)


def available_run(issue_time: datetime) -> datetime:
    if issue_time.tzinfo is None or issue_time.utcoffset() != timedelta(0):
        raise ValueError("Issue time must be UTC")
    cutoff = issue_time - AVAILABILITY_BUFFER
    run_hour = max(hour for hour in RUN_HOURS if hour <= cutoff.hour)
    return cutoff.replace(hour=run_hour, minute=0, second=0, microsecond=0)


def select_hours(payload: dict, issue_time: datetime, horizon_hours: int) -> list[dict]:
    if horizon_hours not in (24, 48):
        raise ValueError("horizon_hours must be 24 or 48")
    if not isinstance(payload, dict) or not isinstance(payload.get("hourly"), dict):
        raise ValueError("Weather response must contain an hourly object")
    hourly = payload["hourly"]
    times = hourly.get("time")
    if not isinstance(times, list) or any(not isinstance(value, str) for value in times):
        raise ValueError("Weather response time must be a list of timestamp strings")
    if any(not isinstance(hourly.get(name), list) for name in VARIABLES):
        raise ValueError("Weather response hourly variables must be lists")
    if any(len(hourly[name]) != len(times) for name in VARIABLES):
        raise ValueError("Weather response has incomplete hourly variables")
    selected = []
    for index, raw_time in enumerate(times):
        valid_time = parse_utc(raw_time + "Z" if "+" not in raw_time and not raw_time.endswith("Z") else raw_time)
        if issue_time < valid_time <= issue_time + timedelta(hours=horizon_hours):
            values = {name: hourly[name][index] for name in VARIABLES}
            if any(isinstance(value, bool) or not isinstance(value, (int, float))
                   or not math.isfinite(value) for value in values.values()):
                raise ValueError(f"Weather variable must be finite numeric data at {valid_time.isoformat()}")
            selected.append({"valid_time_utc": valid_time.isoformat().replace("+00:00", "Z"), **values})
    if len(selected) != horizon_hours:
        raise ValueError(f"Expected {horizon_hours} forecast hours, found {len(selected)}")
    expected = [issue_time + timedelta(hours=hour) for hour in range(1, horizon_hours + 1)]
    actual = [parse_utc(row["valid_time_utc"]) for row in selected]
    if actual != expected:
        raise ValueError("Forecast timestamps are not continuous hourly values after issue time")
    return selected


def fetch_archived_forecast(
    issue_time_utc: str,
    turbine_id: str,
    horizon_hours: int = 48,
    cache_dir: Path | str = Path("data/cache/weather"),
) -> dict:
    """Return a prior run's hourly weather for one turbine and one issue time."""
    issue_time = parse_utc(issue_time_utc)
    if issue_time.minute or issue_time.second or issue_time.microsecond:
        raise ValueError("Issue time must fall on an exact hour")
    if turbine_id not in LOCATIONS:
        raise ValueError(f"Unknown turbine ID: {turbine_id}")
    run_time = available_run(issue_time)
    if run_time + AVAILABILITY_BUFFER > issue_time:
        raise ValueError("Weather run may not have been available at issue time")

    latitude, longitude = LOCATIONS[turbine_id]
    cache_path = Path(cache_dir) / f"{MODEL}_{turbine_id}_{run_time:%Y%m%dT%H%M}.json"
    if cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    else:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "run": run_time.strftime("%Y-%m-%dT%H:%M"),
            "models": MODEL,
            "hourly": ",".join(VARIABLES),
            "wind_speed_unit": "ms",
            "timezone": "UTC",
            "forecast_hours": 72,
        }
        with urlopen(f"{API_URL}?{urlencode(params)}", timeout=45) as response:
            payload = json.load(response)
        # Validate before caching a remote response.
        select_hours(payload, issue_time, horizon_hours)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload), encoding="utf-8")

    return {
        "turbine_id": turbine_id,
        "issue_time_utc": issue_time.isoformat().replace("+00:00", "Z"),
        "weather_source": "Open-Meteo Single Runs API",
        "weather_model": MODEL,
        "weather_run_utc": run_time.isoformat().replace("+00:00", "Z"),
        "availability_buffer_hours": 12,
        "hourly": select_hours(payload, issue_time, horizon_hours),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue_time_utc", help="ISO UTC, e.g. 2026-01-31T12:00:00Z")
    parser.add_argument("turbine_id", choices=LOCATIONS)
    parser.add_argument("--hours", type=int, default=48, choices=(24, 48))
    args = parser.parse_args()
    result = fetch_archived_forecast(args.issue_time_utc, args.turbine_id, args.hours)
    print(json.dumps(result, ensure_ascii=False, indent=2))
