# HackAlem: wind farm generation forecasting

The final case is [Agentic AI for wind farm generation forecasting](https://docs.google.com/document/d/1Fn5IJoj87Fx7IAknG26zkfX8c0eq7feCujd0m66PCgY/edit). Read `docs/case-map.md`, `docs/api-contract.md`, and `docs/team-tasks.md` before coding. Earlier organizational-analysis plans are obsolete.

## Non-negotiable data rules

- Training turbine observations end at **2026-01-31 23:50** in the supplied CSVs. Never fit, calibrate, or select a model with February 2026 turbine observations when simulating a January 31 issue.
- For every historical issue time, weather features must come from a forecast model run that was already available then. Never substitute later observed, reanalysis, or stitched historical weather as if it were a forecast.
- Record `issue_time_utc`, `weather_run_utc`, weather source/model, forecast valid time, and training cutoff in each generated result. Enforce `weather_run_utc < issue_time_utc` and an explicit availability buffer.
- The target is **normalized active power** in [0,1]. Do not label it MW/MWh or sum turbine output into plant energy without nameplate capacities. Timezone of source timestamps is not stated; make the assumption explicit and configurable.
- Keep raw supplied CSVs, caches, credentials, and `.env` out of Git. Synthetic fixtures may be committed if clearly labeled.

## Team workflow

- Frontend/design owns `frontend/` and branch `feat/frontend`.
- Backend/API and data integration owns `backend/`, API/runtime setup, and branch `feat/backend-api`.
- Forecasting/backtest owns `forecast/`, model/evaluation, and branch `feat/forecast-core`.
- Each teammate works in a separate clone and Codex session. Open a PR into `main` for each feature. Merge only after a small end-to-end check and contract review. Do not edit another owner's directory without coordinating.
- The integration owner updates `docs/api-contract.md` before shared JSON fields change.

The demo must show two turbine 24–48-hour forecasts, archived weather provenance, an analysis/recalculation action, and a repeatable sequence of daily historical issue times through February 2026. If February actual power is unavailable, report forecast coverage and validation on pre-February data, not February accuracy.
