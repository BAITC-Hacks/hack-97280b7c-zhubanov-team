"""Pydantic models for the public forecast API contract."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunRequest(BaseModel):
    issue_time_utc: str
    horizon_hours: Literal[24, 48]


class RollingRequest(BaseModel):
    first_issue_date: date
    last_issue_date: date
    issue_hour_utc: int = Field(ge=0, le=23)
    horizon_hours: Literal[24, 48]

    @model_validator(mode="after")
    def dates_are_ordered(self) -> "RollingRequest":
        if self.last_issue_date < self.first_issue_date:
            raise ValueError("last_issue_date must not be before first_issue_date")
        return self


class HourlyPrediction(BaseModel):
    valid_time_utc: str
    predicted_normalized_power: float = Field(ge=0.0, le=1.0)


class TurbineForecast(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    latitude: float | None = None
    longitude: float | None = None
    hourly: list[HourlyPrediction]


class WeatherProvenance(BaseModel):
    source: str
    model: str
    run_time_utc: str


class ForecastResponse(BaseModel):
    run_id: str
    issue_time_utc: str
    training_cutoff_utc: str
    weather: WeatherProvenance
    turbines: list[TurbineForecast] = Field(min_length=2, max_length=2)
    analysis: list[str]
    warnings: list[str]


class RollingResponse(BaseModel):
    runs: list[ForecastResponse]
    requested_dates: list[str]
    completed_dates: list[str]
    failed_dates: list[dict[str, str]]
