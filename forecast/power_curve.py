"""Fast, reproducible empirical wind-to-power model for each turbine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from backend.weather import LOCATIONS, parse_utc

BIN_WIDTH_MS = 0.5
MIN_BIN_SAMPLES = 20
WIND_FEATURE = "wind_speed_100m"  # Hub height is unknown; validate this choice.
REFERENCE_TEMPERATURE_K = 288.15  # 15 °C; relative density proxy, pressure unavailable.


def density_adjusted_speed(wind_speed_ms: float, temperature_c: float) -> float:
    speed = float(wind_speed_ms)
    temperature = float(temperature_c)
    if not np.isfinite(speed) or speed < 0:
        raise ValueError("Wind speed must be finite and nonnegative")
    if not np.isfinite(temperature) or not -100 <= temperature <= 80:
        raise ValueError("Temperature is outside the supported physical range")
    return speed * (REFERENCE_TEMPERATURE_K / (273.15 + temperature)) ** (1 / 3)


@dataclass(frozen=True)
class PowerCurve:
    turbine_id: str
    bin_centers_ms: np.ndarray
    median_power: np.ndarray
    training_rows: int
    latest_training_time_utc: str
    source_timezone: str

    def estimate(self, wind_speed_ms: float, temperature_c: float) -> float:
        adjusted_speed = density_adjusted_speed(wind_speed_ms, temperature_c)
        estimate = np.interp(adjusted_speed, self.bin_centers_ms, self.median_power)
        return float(np.clip(estimate, 0.0, 1.0))


def _load_training_rows(csv_path: Path, cutoff_utc: str, source_timezone: str) -> pd.DataFrame:
    try:
        ZoneInfo(source_timezone)
    except Exception as exc:
        raise ValueError(f"Unknown source timezone: {source_timezone}") from exc
    cutoff = pd.Timestamp(parse_utc(cutoff_utc))
    raw = pd.read_csv(csv_path, encoding="utf-8")
    if raw.shape[1] < 5:
        raise ValueError("Expected five columns in turbine CSV")
    # The organizer supplied Russian headers; positions are stable in both files.
    rows = pd.DataFrame({
        "time": pd.to_datetime(raw.iloc[:, 1], errors="coerce"),
        "wind": pd.to_numeric(raw.iloc[:, 2], errors="coerce"),
        "power": pd.to_numeric(raw.iloc[:, 3], errors="coerce"),
        "temp": pd.to_numeric(raw.iloc[:, 4], errors="coerce"),
    })
    rows["time"] = rows["time"].dt.tz_localize(
        source_timezone, ambiguous="NaT", nonexistent="NaT"
    ).dt.tz_convert("UTC")
    rows = rows.loc[
        rows["time"].notna()
        & (rows["time"] <= cutoff)
        & rows["wind"].notna()
        & rows["power"].notna()
        & rows["temp"].notna()
        & (rows["wind"] >= 0)
        & rows["power"].between(0, 1)
        & rows["temp"].between(-100, 80)
    ].copy()
    if len(rows) < 100:
        raise ValueError("Not enough valid pre-cutoff turbine observations to train")
    return rows


def fit_power_curve(
    turbine_id: str,
    training_cutoff_utc: str,
    *,
    source_timezone: str,
    data_dir: Path | str = Path("data/input"),
) -> PowerCurve:
    """Fit only from observed turbine rows at or before the simulated cutoff."""
    if turbine_id not in LOCATIONS:
        raise ValueError(f"Unknown turbine ID: {turbine_id}")
    csv_path = Path(data_dir) / f"{turbine_id}.csv"
    rows = _load_training_rows(csv_path, training_cutoff_utc, source_timezone)
    rows["adjusted_wind"] = rows["wind"] * (
        REFERENCE_TEMPERATURE_K / (273.15 + rows["temp"])
    ) ** (1 / 3)
    rows["bin"] = np.floor(rows["adjusted_wind"] / BIN_WIDTH_MS).astype(int)
    summary = rows.groupby("bin", observed=True).agg(
        median_wind=("adjusted_wind", "median"), median_power=("power", "median"),
        count=("power", "size")
    )
    summary = summary.loc[summary["count"] >= MIN_BIN_SAMPLES]
    if len(summary) < 3:
        raise ValueError("Not enough populated wind-speed bins to train")
    centers = summary["median_wind"].to_numpy(dtype=float)
    medians = summary["median_power"].to_numpy(dtype=float)
    latest = rows["time"].max().isoformat().replace("+00:00", "Z")
    return PowerCurve(turbine_id, centers, medians, len(rows), latest, source_timezone)


def predict(
    turbine_id: str,
    weather_hourly: list[dict],
    training_cutoff_utc: str,
    *,
    source_timezone: str,
    data_dir: Path | str = Path("data/input"),
    wind_feature: str = WIND_FEATURE,
) -> dict:
    """Return normalized-power predictions aligned with archived weather hours."""
    if wind_feature not in ("wind_speed_10m", "wind_speed_100m"):
        raise ValueError("Unsupported weather wind feature")
    cutoff = parse_utc(training_cutoff_utc)
    if not weather_hourly:
        raise ValueError("At least one weather forecast hour is required")
    curve = fit_power_curve(
        turbine_id, training_cutoff_utc, source_timezone=source_timezone, data_dir=data_dir
    )
    hourly = []
    previous = cutoff
    for row in weather_hourly:
        valid = parse_utc(row["valid_time_utc"])
        if valid <= previous:
            raise ValueError("Weather forecast hours must be ordered after the training cutoff")
        previous = valid
        hourly.append({
            "valid_time_utc": row["valid_time_utc"],
            "predicted_normalized_power": curve.estimate(row[wind_feature], row["temperature_2m"]),
            "forecast_wind_speed_ms": float(row[wind_feature]),
            "forecast_temperature_c": float(row["temperature_2m"]),
        })
    return {
        "id": turbine_id,
        "model": "density_adjusted_power_curve_median_0.5ms",
        "weather_wind_feature": wind_feature,
        "training_cutoff_utc": training_cutoff_utc,
        "latest_training_time_utc": curve.latest_training_time_utc,
        "training_rows": curve.training_rows,
        "source_timezone_assumption": source_timezone,
        "hourly": hourly,
    }
