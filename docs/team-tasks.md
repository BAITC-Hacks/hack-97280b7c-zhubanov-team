# Three-person plan

For the timed four-hour sprint and mandatory push every hour, follow [four-hour-sprint.md](four-hour-sprint.md). The sprint document also answers the model-training and validation decisions.

Work from separate clones/branches, make small PRs into `main`, and use `docs/api-contract.md` as the shared boundary. Pull `main` before starting. All Codex sessions should read `AGENTS.md` first.

| Owner | Branch / files | First deliverable | Completion check |
|---|---|---|---|
| 1. Frontend + design | `feat/frontend`, `frontend/` | Two-turbine chart, issue-time selector, 24/48h switch, weather provenance panel, recalculate button; start with contract fixture | Both 48-point series display, source/run visible, missing-data/error state clear |
| 2. Backend + integration | `feat/backend-api`, `backend/`, runtime config | Parse/aggregate CSV, fetch/cache archived forecast run for both coordinates, expose run/rolling API, enforce run availability | Jan 31 request returns 48 weather-aligned hours for each turbine; no post-issue observation is read |
| 3. Forecast + evaluation | `feat/forecast-core`, `forecast/` | Leakage-safe per-turbine baseline, daily Jan31–Feb28 forecast loop, pre-Feb holdout evaluation and analysis of reruns | Predictions stay in [0,1], all 29 issue dates work, evaluation labels its true held-out period |

Integration order: backend returns contract fixture → frontend connects → forecast module plugs into backend → one end-to-end run → live demo rehearsal. Each PR states inputs, outputs, how to run it, and actual test results. Avoid claiming February MAE without February actual power. Do not use future weather observations in any historical run.
