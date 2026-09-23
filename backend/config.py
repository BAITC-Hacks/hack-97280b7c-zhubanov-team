"""Runtime configuration for the forecast API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from forecast.power_curve import WIND_FEATURE


@dataclass(frozen=True)
class Settings:
    source_timezone: str = "UTC"
    data_dir: Path = Path("data/input")
    weather_cache_dir: Path = Path("data/cache/weather")
    wind_feature: str = WIND_FEATURE

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            source_timezone=os.getenv("SOURCE_TIMEZONE", cls.source_timezone),
            data_dir=Path(os.getenv("DATA_DIR", str(cls.data_dir))),
            weather_cache_dir=Path(
                os.getenv("WEATHER_CACHE_DIR", str(cls.weather_cache_dir))
            ),
            wind_feature=os.getenv("WIND_FEATURE", cls.wind_feature),
        )
