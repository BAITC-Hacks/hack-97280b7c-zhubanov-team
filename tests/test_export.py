"""Synthetic fixtures match generate_rolling_forecasts / power_curve.predict."""

import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from forecast.export import export_forecasts, validate_rows


def rolling_fixture(horizon=48):
    first = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
    stamp = lambda dt: dt.isoformat().replace("+00:00", "Z")
    runs = []
    for day in range(2):
        issue = first + timedelta(days=day)
        turbines = []
        for turbine_id in ("turbine-1", "turbine-2"):
            turbines.append({
                "id": turbine_id, "model": "density_adjusted_power_curve_median_0.5ms",
                "weather_wind_feature": "wind_speed_100m",
                "training_cutoff_utc": stamp(issue),
                "latest_training_time_utc": stamp(min(issue, first + timedelta(hours=11, minutes=50))),
                "training_rows": 1000, "source_timezone_assumption": "UTC",
                "hourly": [{
                    "valid_time_utc": stamp(issue + timedelta(hours=step)),
                    "predicted_normalized_power": step / horizon,
                    "forecast_wind_speed_ms": 8.5, "forecast_temperature_c": -4.0,
                } for step in range(1, horizon + 1)],
            })
        runs.append({
            "run_id": stamp(issue), "issue_time_utc": stamp(issue),
            "training_cutoff_utc": stamp(issue),
            "weather": {"source": "Open-Meteo Single Runs API", "model": "ecmwf_ifs",
                        "run_time_utc": stamp(issue - timedelta(hours=12)),
                        "availability_buffer_hours": 12},
            "turbines": turbines, "analysis": [], "warnings": [],
        })
    return {"first_issue_date": "2026-01-31", "last_issue_date": "2026-02-01",
            "issue_count": 2, "horizon_hours": horizon, "runs": runs, "recalculations": []}


class ForecastExportTest(unittest.TestCase):
    def test_exports_service_format_with_provenance_and_content_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            input_path = Path(folder) / "input.json"
            raw = json.dumps(rolling_fixture()).encode("utf-8")
            input_path.write_bytes(raw)
            output = Path(folder) / "bundle"
            manifest = export_forecasts(input_path, output)
            with (output / "forecasts.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 192)
            self.assertEqual(manifest["row_count"], 192)
            self.assertEqual(manifest["source_timezone_scenarios"], ["UTC"])
            self.assertEqual(manifest["input_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(manifest["files"]["forecasts.csv"]["sha256"], hashlib.sha256((output / "forecasts.csv").read_bytes()).hexdigest())
            self.assertEqual(rows[0]["weather_run_utc"], "2026-01-31T00:00:00Z")
            self.assertEqual(rows[0]["latest_training_time_utc"], "2026-01-31T12:00:00Z")
            self.assertEqual(rows[0]["forecast_temperature_c"], "-4.0")
            self.assertEqual(rows[-1]["normalized_power"], "1.0")
            self.assertEqual(json.loads((output / "manifest.json").read_text(encoding="utf-8")), manifest)
            self.assertEqual({p.name for p in output.iterdir()}, {"forecasts.csv", "manifest.json"})

    def test_24_hour_horizon_and_missing_optional_values(self):
        fixture = rolling_fixture(24)
        turbine = fixture["runs"][0]["turbines"][0]
        del turbine["latest_training_time_utc"]
        del turbine["hourly"][0]["forecast_wind_speed_ms"]
        del turbine["hourly"][0]["forecast_temperature_c"]
        rows, manifest = validate_rows(fixture)
        self.assertEqual(manifest["row_count"], 96)
        self.assertIsNone(rows[0]["latest_training_time_utc"])
        self.assertIsNone(rows[0]["forecast_wind_speed_ms"])
        self.assertEqual(rows[0]["source_timezone_assumption"], "UTC")

    def test_rejects_temporal_leakage_and_missing_provenance(self):
        mutations = [
            lambda f: f["runs"][0]["weather"].update(run_time_utc="2026-01-31T12:00:00Z"),
            lambda f: f["runs"][0]["weather"].update(run_time_utc="2026-01-31T06:00:00Z"),
            lambda f: f["runs"][0]["weather"].pop("availability_buffer_hours"),
            lambda f: f["runs"][0]["weather"].pop("source"),
            lambda f: f["runs"][0]["turbines"][0].pop("source_timezone_assumption"),
            lambda f: f["runs"][0]["turbines"][0].update(latest_training_time_utc="2026-01-31T12:10:00Z"),
            lambda f: f["runs"][0].update(training_cutoff_utc="2026-02-01T12:00:00Z"),
            lambda f: f["runs"][0]["turbines"][0].update(training_cutoff_utc="2026-02-01T12:00:00Z"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                fixture = rolling_fixture()
                mutate(fixture)
                with self.assertRaises(ValueError):
                    validate_rows(fixture)

    def test_rejects_missing_turbine_gaps_ranges_and_wrong_counts(self):
        mutations = [
            lambda f: f.update(issue_count=1),
            lambda f: f.update(horizon_hours=12),
            lambda f: f["runs"][0]["turbines"].pop(),
            lambda f: f["runs"][0]["turbines"][1].update(id="turbine-1"),
            lambda f: f["runs"][0]["turbines"][0]["hourly"].pop(),
            lambda f: f["runs"][0]["turbines"][0]["hourly"][0].update(valid_time_utc="2026-01-31T14:00:00Z"),
            lambda f: f["runs"][0]["turbines"][0]["hourly"][0].update(predicted_normalized_power=1.1),
            lambda f: f["runs"][0]["turbines"][0]["hourly"][0].update(predicted_normalized_power=float("nan")),
            lambda f: f["runs"][0]["turbines"][0]["hourly"][0].update(predicted_normalized_power=True),
            lambda f: f["runs"][0]["turbines"][0].update(model="=BAD()"),
            lambda f: f["runs"][0]["turbines"][0].update(source_timezone_assumption="Asia/Almaty"),
            lambda f: f["runs"][0].update(issue_time_utc="2026-01-31T12:00:00"),
            lambda f: f["runs"].reverse(),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                fixture = rolling_fixture()
                mutate(fixture)
                with self.assertRaises(ValueError):
                    validate_rows(fixture)

    def test_invalid_input_does_not_publish_or_overwrite_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            fixture = rolling_fixture()
            fixture["runs"][-1]["turbines"][-1]["hourly"][-1]["predicted_normalized_power"] = -1
            path.write_text(json.dumps(fixture), encoding="utf-8")
            output = Path(folder) / "bundle"
            with self.assertRaises(ValueError):
                export_forecasts(path, output)
            self.assertFalse(output.exists())
            self.assertEqual(list(Path(folder).glob(".forecast-export-*")), [])
            path.write_text(json.dumps(rolling_fixture()), encoding="utf-8")
            export_forecasts(path, output)
            original = (output / "manifest.json").read_bytes()
            with self.assertRaisesRegex(ValueError, "already exists"):
                export_forecasts(path, output)
            self.assertEqual((output / "manifest.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
