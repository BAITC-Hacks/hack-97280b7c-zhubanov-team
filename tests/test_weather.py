import unittest
import copy
from datetime import datetime, timezone

from backend.weather import available_run, parse_utc, select_hours


class WeatherArchiveTest(unittest.TestCase):
    def test_run_precedes_issue_by_twelve_hours(self):
        issue = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
        self.assertEqual(available_run(issue), datetime(2026, 1, 31, tzinfo=timezone.utc))

    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            parse_utc("2026-01-31T12:00:00")

    def test_selects_only_future_valid_hours(self):
        issue = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
        times = [f"2026-01-{31:02d}T{hour:02d}:00" for hour in range(24)]
        times += [f"2026-02-01T{hour:02d}:00" for hour in range(24)]
        times += [f"2026-02-02T{hour:02d}:00" for hour in range(24)]
        payload = {"hourly": {"time": times, "wind_speed_10m": [4.0] * 72,
                              "wind_speed_100m": [6.0] * 72, "temperature_2m": [3.0] * 72}}
        rows = select_hours(payload, issue, 48)
        self.assertEqual(rows[0]["valid_time_utc"], "2026-01-31T13:00:00Z")
        self.assertEqual(rows[-1]["valid_time_utc"], "2026-02-02T12:00:00Z")

    def test_malformed_json_shapes_raise_value_error(self):
        issue = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
        cases = [None, [], {"hourly": None}, {"hourly": []},
                 {"hourly": {"time": None}}, {"hourly": {"time": "2026-01-31T13:00"}},
                 {"hourly": {"time": [None]}}]
        valid = {"hourly": {"time": ["2026-01-31T13:00"],
                            "wind_speed_10m": [4.0], "wind_speed_100m": [6.0],
                            "temperature_2m": [3.0]}}
        for variable in ("wind_speed_10m", "wind_speed_100m", "temperature_2m"):
            for invalid in (None, 4.0, {}, "6.0"):
                payload = copy.deepcopy(valid)
                payload["hourly"][variable] = invalid
                cases.append(payload)
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                select_hours(payload, issue, 24)

    def test_malformed_weather_values_raise_value_error(self):
        issue = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
        for value in (None, True, "6.0", {}, [], float("nan"), float("inf")):
            payload = {"hourly": {"time": ["2026-01-31T13:00"],
                                  "wind_speed_10m": [4.0], "wind_speed_100m": [value],
                                  "temperature_2m": [3.0]}}
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "finite numeric"):
                select_hours(payload, issue, 24)


if __name__ == "__main__":
    unittest.main()
