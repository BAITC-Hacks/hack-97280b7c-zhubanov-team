"""Validate and export an existing rolling forecast JSON without fetching or training.

Usage: python -m forecast.export --input rolling.json --output-dir outputs/monthly-utc
The output directory must not exist: a validated bundle is published in one rename.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile


FIELDS = (
    "issue_time_utc", "valid_time_utc", "turbine_id", "normalized_power",
    "weather_source", "weather_model", "weather_run_utc", "availability_buffer_hours",
    "training_cutoff_utc", "latest_training_time_utc", "source_timezone_assumption",
    "model", "weather_wind_feature", "forecast_wind_speed_ms", "forecast_temperature_c",
    "calibration_applied",
)


def _object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    # Protect CSV consumers from formulas in metadata fields.
    if value.lstrip().startswith(("=", "+", "-", "@")) or any(c in value for c in "\r\n\t"):
        raise ValueError(f"{label} contains unsafe CSV metadata")
    return value


def _utc(value: object, label: str) -> datetime:
    text = _text(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be a UTC ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must explicitly use UTC")
    return parsed.astimezone(timezone.utc)


def _number(value: object, label: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be finite and between {low} and {high}")
    return value


def validate_rows(payload: object) -> tuple[list[dict], dict]:
    """Validate the service's rolling format and retain only exportable metadata."""
    data = _object(payload, "rolling forecast")
    horizon = data.get("horizon_hours")
    if type(horizon) is not int or horizon not in (24, 48):
        raise ValueError("horizon_hours must be 24 or 48")
    runs = data.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("runs must be a nonempty list")
    if type(data.get("issue_count")) is not int or data["issue_count"] != len(runs):
        raise ValueError("issue_count does not match runs")
    try:
        first = date.fromisoformat(data["first_issue_date"])
        last = date.fromisoformat(data["last_issue_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("first_issue_date and last_issue_date must be ISO dates") from exc
    if (last - first).days + 1 != len(runs):
        raise ValueError("Date range does not match the daily issue count")

    rows = []
    scenarios = set()
    models = set()
    weather_sources = set()
    previous_issue = None
    for index, item in enumerate(runs):
        run = _object(item, f"runs[{index}]")
        issue = _utc(run.get("issue_time_utc"), "issue_time_utc")
        if issue.minute or issue.second or issue.microsecond:
            raise ValueError("Issue times must fall on an exact hour")
        if issue.date() != first + timedelta(days=index):
            raise ValueError("Issue dates must cover the declared daily range in order")
        if previous_issue is not None and issue - previous_issue != timedelta(days=1):
            raise ValueError("Rolling issue times must be exactly one day apart")
        previous_issue = issue
        run_cutoff = _utc(run.get("training_cutoff_utc"), "training_cutoff_utc")
        if run_cutoff > issue:
            raise ValueError("Training cutoff cannot be after issue time")
        weather = _object(run.get("weather"), "weather")
        source = _text(weather.get("source"), "weather.source")
        weather_model = _text(weather.get("model"), "weather.model")
        weather_run = _utc(weather.get("run_time_utc"), "weather.run_time_utc")
        buffer = _number(weather.get("availability_buffer_hours"), "availability_buffer_hours", 0, 8760)
        if weather_run >= issue or weather_run + timedelta(hours=buffer) > issue:
            raise ValueError("Weather run does not precede issue by its stated availability buffer")
        weather_sources.add((source, weather_model))
        turbines = run.get("turbines")
        if not isinstance(turbines, list) or len(turbines) != 2:
            raise ValueError("Each issue must contain both turbines exactly once")
        ids = [_object(t, "turbine").get("id") for t in turbines]
        if sorted(str(t) for t in ids) != ["turbine-1", "turbine-2"]:
            raise ValueError("Each issue must contain turbine-1 and turbine-2 exactly once")
        run_scenarios = set()
        for turbine in turbines:
            scenario = _text(turbine.get("source_timezone_assumption"), "source_timezone_assumption")
            model = _text(turbine.get("model"), "model")
            cutoff = _utc(turbine.get("training_cutoff_utc"), "turbine.training_cutoff_utc")
            if cutoff > run_cutoff:
                raise ValueError("Turbine cutoff exceeds the run training cutoff")
            latest = turbine.get("latest_training_time_utc")
            if latest is not None and _utc(latest, "latest_training_time_utc") > cutoff:
                raise ValueError("Latest training observation exceeds training cutoff")
            wind_feature = turbine.get("weather_wind_feature", "")
            if wind_feature:
                _text(wind_feature, "weather_wind_feature")
            hours = turbine.get("hourly")
            if not isinstance(hours, list) or len(hours) != horizon:
                raise ValueError("Each turbine must contain exactly horizon_hours points")
            scenarios.add(scenario)
            run_scenarios.add(scenario)
            models.add(model)
            for step, hour in enumerate(hours, start=1):
                hour = _object(hour, "hourly point")
                valid = _utc(hour.get("valid_time_utc"), "valid_time_utc")
                if valid != issue + timedelta(hours=step):
                    raise ValueError("Forecast points must be continuous hourly values after issue")
                power = _number(hour.get("predicted_normalized_power"), "normalized_power", 0, 1)
                wind = hour.get("forecast_wind_speed_ms")
                temperature = hour.get("forecast_temperature_c")
                if wind is not None:
                    _number(wind, "forecast_wind_speed_ms", 0, float("inf"))
                if temperature is not None:
                    _number(temperature, "forecast_temperature_c", -100, 80)
                rows.append({
                    "issue_time_utc": run["issue_time_utc"],
                    "valid_time_utc": hour["valid_time_utc"],
                    "turbine_id": turbine["id"], "normalized_power": power,
                    "weather_source": source, "weather_model": weather_model,
                    "weather_run_utc": weather["run_time_utc"], "availability_buffer_hours": buffer,
                    "training_cutoff_utc": turbine["training_cutoff_utc"],
                    "latest_training_time_utc": latest,
                    "source_timezone_assumption": scenario, "model": model,
                    "weather_wind_feature": wind_feature,
                    "forecast_wind_speed_ms": wind, "forecast_temperature_c": temperature,
                    "calibration_applied": "calibration" in turbine,
                })
        if len(run_scenarios) != 1:
            raise ValueError("Both turbines in an issue must use the same source timezone scenario")
    return rows, {
        "schema_version": 1, "issue_count": len(runs), "row_count": len(rows),
        "horizon_hours": horizon, "turbine_ids": ["turbine-1", "turbine-2"],
        "first_issue_time_utc": runs[0]["issue_time_utc"],
        "last_issue_time_utc": runs[-1]["issue_time_utc"],
        "source_timezone_scenarios": sorted(scenarios), "forecast_models": sorted(models),
        "weather_sources": [{"source": s, "model": m} for s, m in sorted(weather_sources)],
        "target": "normalized active power", "target_unit": "dimensionless [0,1]",
        "validation_scope": "Structure, ranges, continuity and declared temporal provenance only; no forecast accuracy evaluation.",
        "timezone_note": "Source timezone values are supplied assumptions, not organizer-confirmed timezones.",
        "weather_availability_note": "The stated buffer is an availability assumption; actual forecast publication timestamps were not verified.",
    }


def export_forecasts(input_path: Path | str, output_dir: Path | str) -> dict:
    """Publish a fresh CSV/manifest bundle only after complete input validation."""
    input_path, output_dir = Path(input_path), Path(output_dir)
    if output_dir.exists():
        raise ValueError("Output directory already exists; choose a new directory to avoid mixing exports")
    raw = input_path.read_bytes()
    rows, manifest = validate_rows(json.loads(raw.decode("utf-8-sig")))
    manifest["input_sha256"] = hashlib.sha256(raw).hexdigest()
    manifest["exported_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    # This revision identifies the exporter checkout, not necessarily the model that generated the input.
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent,
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        revision = None
    manifest["exporter_git_revision"] = revision
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".forecast-export-", dir=output_dir.parent))
    try:
        csv_path = staging / "forecasts.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        manifest["files"] = {"forecasts.csv": {"sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest()}}
        (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staging.rename(output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        manifest = export_forecasts(args.input, args.output_dir)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Export failed: {exc}\n")
    print(f"Exported {manifest['issue_count']} issues / {manifest['row_count']} turbine-hours to {args.output_dir}")


if __name__ == "__main__":
    main()
