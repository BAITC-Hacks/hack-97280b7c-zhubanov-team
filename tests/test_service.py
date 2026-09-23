import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from forecast.service import compare_recalculation, generate_forecast


class ForecastServiceTest(unittest.TestCase):
    def test_two_turbines_share_prior_weather_run(self):
        issue = datetime(2026, 1, 31, 12, tzinfo=timezone.utc)
        hours = [
            {"valid_time_utc": (issue + timedelta(hours=index)).isoformat().replace("+00:00", "Z"),
             "wind_speed_100m": 6.0, "temperature_2m": 5.0}
            for index in range(1, 25)
        ]

        def weather(issue_time, turbine_id, horizon):
            self.assertEqual(horizon, 24)
            return {"weather_run_utc": "2026-01-31T00:00:00Z", "hourly": hours}

        def model(turbine_id, weather_hours, cutoff, **kwargs):
            self.assertEqual(cutoff, "2026-01-31T12:00:00Z")
            return {"id": turbine_id, "training_rows": 100,
                    "hourly": [{"valid_time_utc": row["valid_time_utc"],
                                "predicted_normalized_power": 0.5} for row in weather_hours]}

        with patch("forecast.service.fetch_archived_forecast", side_effect=weather), \
             patch("forecast.service.predict", side_effect=model):
            result = generate_forecast("2026-01-31T12:00:00Z", 24,
                                       source_timezone="Asia/Almaty")
        self.assertEqual(len(result["turbines"]), 2)
        self.assertTrue(all(len(row["hourly"]) == 24 for row in result["turbines"]))
        self.assertEqual(result["weather"]["run_time_utc"], "2026-01-31T00:00:00Z")
        self.assertTrue(any("no declared timezone" in warning for warning in result["warnings"]))

    def test_recalculation_uses_only_overlapping_hours(self):
        previous = {
            "issue_time_utc": "2026-01-31T12:00:00Z",
            "weather": {"run_time_utc": "2026-01-31T00:00:00Z"},
            "turbines": [{"id": "turbine-1", "hourly": [
                {"valid_time_utc": "2026-02-01T13:00:00Z", "predicted_normalized_power": 0.2}]}],
        }
        current = {
            "issue_time_utc": "2026-02-01T12:00:00Z",
            "weather": {"run_time_utc": "2026-02-01T00:00:00Z"},
            "turbines": [{"id": "turbine-1", "hourly": [
                {"valid_time_utc": "2026-02-01T13:00:00Z", "predicted_normalized_power": 0.3},
                {"valid_time_utc": "2026-02-02T13:00:00Z", "predicted_normalized_power": 0.9}]}],
        }
        change = compare_recalculation(previous, current)["changes"][0]
        self.assertEqual(change["overlapping_hours"], 1)
        self.assertAlmostEqual(change["mean_change_normalized_power"], 0.1)


if __name__ == "__main__":
    unittest.main()
