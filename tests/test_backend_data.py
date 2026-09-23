from datetime import datetime, timedelta

import pytest

from backend.data import load_hourly


def write_csv(path, indices):
    start = datetime(2026, 1, 1)
    lines = ["ID,time,wind,power,temp"]
    for i in indices:
        lines.append(f"{i},{start + timedelta(minutes=10*i)},6,0.5,5")
    path.write_text("\n".join(lines), encoding="utf-8")


def test_cutoff_and_gaps_are_not_filled(tmp_path):
    path = tmp_path / "turbine.csv"
    write_csv(path, [*range(6), 12, 13, 14, 15, 16, 17, 18])
    hourly, report = load_hourly(path, "2026-01-01T02:50:00Z", "UTC")
    assert report["rows_before_cutoff"] == 12
    assert report["gaps_over_ten_minutes"] == 1
    assert report["complete_hours"] == 2
    assert report["incomplete_hours"] == 1
    assert hourly.iloc[0].power == 0.5
    assert hourly.iloc[1][["wind", "power", "temperature"]].isna().all()


def test_duplicate_timestamps_are_rejected(tmp_path):
    path = tmp_path / "turbine.csv"
    write_csv(path, [0, 0])
    with pytest.raises(ValueError, match="duplicate"):
        load_hourly(path, "2026-01-01T01:00:00Z", "UTC")


def test_timezone_changes_cutoff_selection(tmp_path):
    path = tmp_path / "turbine.csv"
    write_csv(path, range(36))
    _, utc = load_hourly(path, "2026-01-01T00:50:00Z", "UTC")
    _, local = load_hourly(path, "2026-01-01T00:50:00Z", "Asia/Almaty")
    assert utc["rows_before_cutoff"] == 6
    assert local["rows_before_cutoff"] == 36


def test_ambiguous_local_hour_is_omitted_without_rejecting_csv(tmp_path):
    path = tmp_path / "turbine.csv"
    times = [
        datetime(2024, 2, 29, hour, minute)
        for hour in (22, 23)
        for minute in range(0, 60, 10)
    ] + [datetime(2024, 3, 1, 0, minute) for minute in range(0, 60, 10)]
    path.write_text(
        "ID,time,wind,power,temp\n"
        + "\n".join(f"{i},{time},6,0.5,5" for i, time in enumerate(times)),
        encoding="utf-8",
    )

    hourly, report = load_hourly(path, "2024-03-01T00:00:00Z", "Asia/Almaty")

    assert report["unresolved_source_timestamps_dropped"] == 6
    assert report["rows_before_cutoff"] == 12
    assert report["complete_hours"] == 2
    assert hourly.power.notna().sum() == 2
