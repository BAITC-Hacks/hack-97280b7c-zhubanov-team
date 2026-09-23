"""Verify the committed forecast evidence using only the Python standard library."""

import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


UTC = timezone.utc
FIRST_ISSUE = datetime(2026, 1, 31, 12, tzinfo=UTC)
ISSUES = {FIRST_ISSUE + timedelta(days=i) for i in range(29)}
FEBRUARY = {datetime(2026, 2, 1, tzinfo=UTC) + timedelta(hours=i) for i in range(672)}
TURBINES = {"turbine-1", "turbine-2"}
SCENARIOS = {"monthly-utc": ("UTC", 23), "monthly-almaty": ("Asia/Almaty", 18)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None and result.utcoffset() == timedelta(0),
            f"Timestamp must declare UTC: {value}")
    return result


def verify(directory):
    scenario, last_hour = SCENARIOS[directory.name]
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    csv_path = directory / "forecasts.csv"
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    require(digest == manifest["files"]["forecasts.csv"]["sha256"], "CSV SHA-256 mismatch")
    require(manifest["schema_version"] == 1, "Unexpected manifest schema")
    require(manifest["issue_count"] == 29 and manifest["row_count"] == 2784,
            "Manifest must declare 29 issues / 2784 rows")
    require(manifest["horizon_hours"] == 48, "Manifest horizon must be 48 hours")
    require(set(manifest["turbine_ids"]) == TURBINES, "Manifest turbine IDs differ")
    require(manifest["source_timezone_scenarios"] == [scenario], "Manifest timezone differs")
    require(timestamp(manifest["first_issue_time_utc"]) == min(ISSUES)
            and timestamp(manifest["last_issue_time_utc"]) == max(ISSUES),
            "Manifest issue range differs")

    with csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == 2784, f"Expected 2784 rows, got {len(rows)}")
    groups = defaultdict(list)
    coverage = defaultdict(set)
    source_end = datetime(2026, 1, 31, last_hour, 50, tzinfo=UTC)
    metadata = defaultdict(set)
    for number, row in enumerate(rows, 2):
        issue = timestamp(row["issue_time_utc"])
        valid = timestamp(row["valid_time_utc"])
        run = timestamp(row["weather_run_utc"])
        cutoff = timestamp(row["training_cutoff_utc"])
        latest = timestamp(row["latest_training_time_utc"])
        turbine = row["turbine_id"]
        power = float(row["normalized_power"])
        buffer = float(row["availability_buffer_hours"])
        label = f"CSV line {number}"
        require(turbine in TURBINES and issue in ISSUES, f"{label}: unknown turbine/issue")
        require(math.isfinite(power) and 0 <= power <= 1, f"{label}: power outside [0,1]")
        require(buffer == 12 and run < issue and run + timedelta(hours=buffer) <= issue,
                f"{label}: declared weather buffer violated")
        require(latest <= cutoff <= issue and latest <= source_end,
                f"{label}: declared training cutoff/source end violated")
        require(row["source_timezone_assumption"] == scenario, f"{label}: timezone differs")
        require(row["weather_source"] == "Open-Meteo Single Runs API"
                and row["weather_model"] == "ecmwf_ifs"
                and row["weather_wind_feature"] == "wind_speed_100m",
                f"{label}: weather source/model/feature differs")
        require(row["model"] == "density_adjusted_power_curve_median_0.5ms"
                and row["calibration_applied"] == "False", f"{label}: model differs")
        groups[issue, turbine].append(valid)
        coverage[turbine].add(valid)
        metadata[issue, turbine].add((run, cutoff, latest, buffer))

    require(set(groups) == {(issue, turbine) for issue in ISSUES for turbine in TURBINES},
            "Missing daily issue/turbine combination")
    for (issue, turbine), times in groups.items():
        expected = [issue + timedelta(hours=i) for i in range(1, 49)]
        require(sorted(times) == expected, f"{issue}/{turbine}: not exactly 48 continuous hours")
        require(len(metadata[issue, turbine]) == 1, f"{issue}/{turbine}: inconsistent provenance")
    for turbine in TURBINES:
        require(FEBRUARY <= coverage[turbine], f"{turbine}: missing February UTC hours")
    print(f"PASS {directory.name}: CSV SHA-256; 29 daily issues; 2 turbines; 2784 rows; "
          "48 hours/issue; 672 February UTC hours/turbine; declared cutoffs and 12h buffer.")


def main():
    root = Path(__file__).resolve().parent
    try:
        for name in SCENARIOS:
            verify(root / name)
    except (ValueError, KeyError, OSError, TypeError, csv.Error) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("Scope: structure and declared provenance only; no accuracy or weather publication verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
