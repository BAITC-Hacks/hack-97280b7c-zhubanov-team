"""Environment-backed settings for the forecast API."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    source_timezone: str = "UTC"
    data_dir: str = "data/input"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            source_timezone=os.getenv("SOURCE_TIMEZONE", cls.source_timezone),
            data_dir=os.getenv("DATA_DIR", cls.data_dir),
        )
