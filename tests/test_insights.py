import unittest

from forecast.insights import summarize_turbine_forecast


class OperatorInsightTest(unittest.TestCase):
    def test_flags_consecutive_low_generation_and_full_load_hours(self):
        values = [0.5, 0.1, 0.0, 0.1, 0.15, 0.4]
        rows = [
            {"valid_time_utc": f"2026-02-01T{hour:02d}:00:00Z",
             "predicted_normalized_power": power}
            for hour, power in enumerate(values)
        ]
        insight = summarize_turbine_forecast(rows)
        self.assertTrue(insight["operator_review_recommended"])
        self.assertEqual(insight["low_generation_hours"], 4)
        self.assertEqual(insight["longest_low_generation_window"]["hours"], 4)
        self.assertAlmostEqual(insight["forecast_full_load_hours_equivalent"], 1.25)

    def test_short_low_period_does_not_trigger_review(self):
        rows = [
            {"valid_time_utc": "2026-02-01T01:00:00Z", "predicted_normalized_power": 0.1},
            {"valid_time_utc": "2026-02-01T02:00:00Z", "predicted_normalized_power": 0.5},
        ]
        self.assertFalse(summarize_turbine_forecast(rows)["operator_review_recommended"])


if __name__ == "__main__":
    unittest.main()
