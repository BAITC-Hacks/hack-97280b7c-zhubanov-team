"""Deterministic, reviewable operator insights from normalized-power forecasts."""

from __future__ import annotations


def summarize_turbine_forecast(
    hourly: list[dict], *, low_power_threshold: float = 0.2,
    minimum_window_hours: int = 4,
) -> dict:
    """Highlight low-output windows without pretending normalized power is MWh."""
    if not 0 < low_power_threshold < 1 or minimum_window_hours < 1:
        raise ValueError("Invalid low-output scenario parameters")
    if not hourly:
        raise ValueError("At least one forecast hour is required")
    windows = []
    start = None
    end = None
    length = 0
    low_hours = 0
    total = 0.0

    def finish_window() -> None:
        nonlocal start, end, length
        if length >= minimum_window_hours:
            windows.append({"start_time_utc": start, "end_time_utc": end, "hours": length})
        start = end = None
        length = 0

    for row in hourly:
        power = float(row["predicted_normalized_power"])
        if not 0 <= power <= 1:
            raise ValueError("Normalized power must be between 0 and 1")
        total += power
        if power < low_power_threshold:
            low_hours += 1
            if start is None:
                start = row["valid_time_utc"]
            end = row["valid_time_utc"]
            length += 1
        else:
            finish_window()
    finish_window()
    longest = max(windows, key=lambda item: item["hours"], default=None)
    return {
        "threshold_normalized_power": low_power_threshold,
        "minimum_window_hours": minimum_window_hours,
        "forecast_full_load_hours_equivalent": round(total, 3),
        "low_generation_hours": low_hours,
        "low_generation_windows": windows,
        "longest_low_generation_window": longest,
        "operator_review_recommended": longest is not None,
        "note": (
            "Review the flagged low-generation window; this is advisory, not an automatic dispatch action."
            if longest else "No extended low-generation window under this scenario threshold."
        ),
    }
