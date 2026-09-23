# First forecasting baseline and January diagnostic

`forecast/power_curve.py` fits a separate empirical power curve for each turbine: median normalized active power within 0.5 m/s bins of its measured historical wind speed, with interpolation between populated bins. Only CSV rows at or before the supplied UTC training cutoff enter fitting. The model currently uses wind speed only; temperature is available in the input but is not yet used. Predictions are clipped to [0,1]. This is a trained baseline, not a final physical turbine model.

The weather predictor uses `wind_speed_100m` from the archived ECMWF IFS run via `backend/weather.py`. The organizer did not specify the height of the measured wind-speed sensor, so 100 m is an explicit proxy choice. The CSV timestamps have no timezone; every fitting and validation call therefore requires a `source_timezone` argument.

## Reproduce

Install `pandas` and `numpy` if not present, place the two organizer CSVs in `data/input/`, then run:

```powershell
python -m unittest discover -s tests -v
python -m forecast.validation --source-timezone Asia/Almaty
```

The second command downloads/caches four January archived weather runs per turbine. It evaluates 48 hours after each issue at 2026-01-20, 23, 26 and 29 at 12:00 UTC, fitting afresh using only pre-issue turbine observations. Each of the eight turbine/issue combinations had 48 actual hourly values with at least four 10-minute observations per hour. The reported MAE uses unitless normalized power.

Initial diagnostic on 2026-09-23, conditional on interpreting the CSV timestamps as `Asia/Almaty`:

| January issues | Turbine-hours | MAE, 100 m weather wind |
|---|---:|---:|
| Jan 20 and 23 | 192 | 0.185 |
| Jan 26 and 29 | 192 | 0.190 |
| All four | 384 | 0.187 |

The 10 m wind feature had MAE 0.360 on Jan 20 and 23, so 100 m was retained. A six-hour recent-power persistence forecast scored approximately 0.406 MAE on Jan 26 and 29. These comparisons are exploratory: the source timezone was not confirmed, and the January dates were inspected during development. Treat these as a conditional diagnostic, not an independent benchmark or a February score. Under a UTC interpretation of the source CSV, the same four-issue 100 m MAE was 0.269, illustrating the sensitivity to timezone alignment. Obtain organizer confirmation before presenting a definitive metric.

There are no February actual-power rows in the supplied files. February forecasts can be generated, but February MAE cannot yet be calculated. Nameplate capacities are absent, so all predictions stay in normalized-power units.

## Full rolling forecast

`forecast.service.generate_forecast()` combines the archived weather and trained curves for both turbines. `generate_rolling_forecasts()` repeats this for every daily issue from Jan 31 through Feb 28 and compares the 24 overlapping hours between consecutive 48-hour forecasts. The default remains the uncalibrated baseline. An experimental additive bias correction trained on Jan 20/23 increased the Jan 26/29 MAE from **0.190** to **0.197**, so it is disabled by default.

```powershell
python -m forecast.service --source-timezone Asia/Almaty
```

The output is written to ignored `data/cache/rolling-forecasts.json`. A full run on 2026-09-23 produced **29 issues, 2,784 turbine-hours, and 28 recalculation comparisons**; every turbine/issue had 48 hourly points and every comparison had 24 overlapping hours. All predictions were between 0.01 and 0.99 normalized power. These are forecasts, not measured February outcomes.
