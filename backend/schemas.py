"""Request and response models for the public forecast API."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunRequest(BaseModel):
    issue_time_utc: str = Field(min_length=1)
    horizon_hours: Literal[24, 48]


class RollingRequest(BaseModel):
    first_issue_date: date
    last_issue_date: date
    issue_hour_utc: int = Field(ge=0, le=23)
    horizon_hours: Literal[24, 48]

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "RollingRequest":
        if self.first_issue_date > self.last_issue_date:
            raise ValueError("first_issue_date must not be after last_issue_date")
        return self


class ForecastResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    run_id: str
    issue_time_utc: str
    training_cutoff_utc: str
    weather: dict
    turbines: list[dict]
    analysis: list[str]
    warnings: list[str]


class RollingResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    runs: list[dict]
    recalculations: list[dict]
