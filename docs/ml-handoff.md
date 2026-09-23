# ML handoff for the backend teammate

The ML implementation is already on `main`. Please **import it rather than rebuilding it**. Files: `forecast/power_curve.py` (training/prediction), `forecast/service.py` (two turbines, rolling issues, recalculation), `forecast/validation.py` (January diagnostic), and `backend/weather.py` (archived issued weather). The raw organizer CSVs belong only in ignored `data/input/` per the README.

Use Python with `numpy` and `pandas` installed. From the repository root:

```python
from forecast.service import generate_forecast, generate_rolling_forecasts

single = generate_forecast(
    "2026-01-31T12:00:00Z", 48,
    source_timezone="Asia/Almaty",  # explicit, unconfirmed organizer-time assumption
)
rolling = generate_rolling_forecasts(
    "2026-01-31", "2026-02-28",
    issue_hour_utc=12, horizon_hours=48,
    source_timezone="Asia/Almaty",
)
```

`single` already follows `docs/api-contract.md`: it has `issue_time_utc`, `training_cutoff_utc`, `weather` provenance, `turbines` (two 48-point arrays), `analysis`, and `warnings`. `rolling` has 29 `runs` and 28 `recalculations`; each recalculation compares only the overlapping valid hours. The backend can return these dicts directly from `POST /api/forecast/run` and `POST /api/forecast/rolling`, with normal request validation and error handling. Please coordinate any JSON changes with the frontend teammate.

For an isolated smoke check without a server:

```powershell
python -m unittest discover -s tests -v
python -m forecast.service --source-timezone Asia/Almaty
```

The second command writes the full forecast to ignored `data/cache/rolling-forecasts.json`. A verified run produced 29 daily issues, 2,784 turbine-hours and 28 comparisons. The normalized-power model fits both turbines in about two seconds on the current laptop; no GPU or NVIDIA API is needed for training. Model/validation details are in `docs/model-validation.md`.

The team reports that organizers provided **no timezone definition** for the CSV timestamps. Keep `source_timezone` explicit in every run and retain the warning in the API response. The broad January MAE is 0.173 under `Asia/Almaty` versus 0.206 under `UTC`; neither is a definitive competition score. There are no supplied February actual-power measurements, so February MAE is unavailable.
