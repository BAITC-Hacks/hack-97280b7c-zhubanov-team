"""Cutoff-aware input audit and hourly aggregation; never impute gaps."""

from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from backend.weather import LOCATIONS, parse_utc


def load_hourly(path, cutoff_utc, source_timezone):
    ZoneInfo(source_timezone)
    raw = pd.read_csv(path)
    if len(raw.columns) != 5:
        raise ValueError(f"{Path(path).name}: expected five CSV columns")
    source_times = pd.to_datetime(raw.iloc[:, 1], errors="coerce")
    if source_times.isna().any():
        raise ValueError(f"{Path(path).name}: invalid timestamps")
    times = source_times.dt.tz_localize(
        source_timezone, ambiguous="NaT", nonexistent="NaT"
    ).dt.tz_convert("UTC")
    # A local clock can repeat or skip an hour at a timezone transition. Its
    # UTC offset is unknowable from a naive CSV timestamp, so omit those rows.
    unresolved_times = int(times.isna().sum())
    rows = pd.DataFrame({"time": times})
    for name, position in (("wind", 2), ("power", 3), ("temperature", 4)):
        rows[name] = pd.to_numeric(raw.iloc[:, position], errors="coerce")
    rows = rows.loc[
        rows.time.notna() & (rows.time <= pd.Timestamp(parse_utc(cutoff_utc)))
    ].sort_values("time")
    if rows.empty:
        raise ValueError(f"{Path(path).name}: no observations before cutoff")
    if rows.time.duplicated().any():
        raise ValueError(f"{Path(path).name}: duplicate timestamps before cutoff")
    if ((rows.time.dt.minute % 10 != 0) | (rows.time.dt.second != 0) | (rows.time.dt.microsecond != 0)).any():
        raise ValueError(f"{Path(path).name}: observations must follow ten-minute cadence")
    valid = (np.isfinite(rows[["wind", "power", "temperature"]]).all(axis=1)
             & rows.wind.ge(0) & rows.power.between(0, 1) & rows.temperature.between(-100, 80))
    if not valid.all():
        raise ValueError(f"{Path(path).name}: missing or invalid measurements before cutoff")
    intervals = rows.time.diff().dropna()
    hourly = rows.set_index("time").resample("h").agg(
        wind=("wind", "mean"), power=("power", "mean"),
        temperature=("temperature", "mean"), samples=("power", "count"))
    # Keep incomplete hours visible, but do not present their means as complete observations.
    hourly.loc[hourly.samples < 6, ["wind", "power", "temperature"]] = np.nan
    report = {"source_timezone": source_timezone, "cutoff_utc": cutoff_utc,
              "unresolved_source_timestamps_dropped": unresolved_times,
              "rows_before_cutoff": len(rows),
              "gaps_over_ten_minutes": int((intervals > pd.Timedelta(minutes=10)).sum()),
              "incomplete_hours": int((hourly.samples < 6).sum()),
              "complete_hours": int((hourly.samples == 6).sum())}
    return hourly, report


def audit_inputs(data_dir, cutoff_utc, source_timezone):
    return {name: load_hourly(Path(data_dir) / f"{name}.csv", cutoff_utc, source_timezone)[1]
            for name in LOCATIONS}


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--source-timezone", required=True)
    parser.add_argument("--data-dir", default="data/input")
    args = parser.parse_args()
    print(json.dumps(audit_inputs(args.data_dir, args.cutoff, args.source_timezone), indent=2))
