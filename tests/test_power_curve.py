import tempfile
import unittest
from pathlib import Path

from forecast.power_curve import density_adjusted_speed, fit_power_curve, predict


class PowerCurveTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        path = self.data_dir / "turbine-1.csv"
        with path.open("w", encoding="utf-8") as file:
            file.write("ID,time,wind,power,temp\n")
            for index in range(120):
                speed = 2 + (index % 3) * 2
                power = {2: 0.1, 4: 0.4, 6: 0.8}[speed]
                file.write(f"{index},2026-01-01 00:00:00,{speed},{power},5\n")
            # These post-cutoff rows would reverse the curve if leaked.
            for index in range(120, 240):
                file.write(f"{index},2026-01-03 00:00:00,6,0.0,5\n")

    def tearDown(self):
        self.temp.cleanup()

    def test_fit_excludes_future_rows(self):
        curve = fit_power_curve("turbine-1", "2026-01-02T00:00:00Z", source_timezone="UTC", data_dir=self.data_dir)
        self.assertEqual(curve.training_rows, 120)
        self.assertAlmostEqual(curve.estimate(6, 5), 0.8)

    def test_colder_air_increases_density_adjusted_speed(self):
        self.assertGreater(density_adjusted_speed(6, -10), density_adjusted_speed(6, 25))

    def test_prediction_contract(self):
        rows = [{"valid_time_utc": "2026-01-02T01:00:00Z", "wind_speed_100m": 6.0,
                 "temperature_2m": 5.0}]
        result = predict("turbine-1", rows, "2026-01-02T00:00:00Z", source_timezone="UTC", data_dir=self.data_dir)
        self.assertEqual(len(result["hourly"]), 1)
        self.assertGreater(result["hourly"][0]["predicted_normalized_power"], 0.7)

    def test_rejects_weather_not_after_cutoff(self):
        rows = [{"valid_time_utc": "2026-01-01T23:00:00Z", "wind_speed_100m": 6.0,
                 "temperature_2m": 5.0}]
        with self.assertRaises(ValueError):
            predict("turbine-1", rows, "2026-01-02T00:00:00Z", source_timezone="UTC", data_dir=self.data_dir)


if __name__ == "__main__":
    unittest.main()
