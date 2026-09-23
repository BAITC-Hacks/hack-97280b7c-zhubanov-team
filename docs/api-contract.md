# Shared API contract — draft v1

This interface unblocks parallel frontend, API, and forecast work. The backend owner may refine it with the team before code integration. Timestamps are ISO-8601 UTC with `Z`; predictions are unitless normalized active power in [0,1].

`POST /api/forecast/run`

```json
{"issue_time_utc":"2026-01-31T12:00:00Z","horizon_hours":48}
```

Response:

```json
{
  "run_id":"jan31-1200",
  "issue_time_utc":"2026-01-31T12:00:00Z",
  "training_cutoff_utc":"2026-01-31T11:50:00Z",
  "weather":{"source":"Open-Meteo Single Runs API","model":"ecmwf_ifs","run_time_utc":"2026-01-31T00:00:00Z"},
  "turbines":[
    {"id":"turbine-1","latitude":43.643198,"longitude":78.538828,"hourly":[{"valid_time_utc":"2026-01-31T13:00:00Z","predicted_normalized_power":0.42}]},
    {"id":"turbine-2","latitude":43.645150,"longitude":78.535604,"hourly":[{"valid_time_utc":"2026-01-31T13:00:00Z","predicted_normalized_power":0.40}]}
  ],
  "analysis":["Forecast relies on archived weather run 2026-01-31 00:00 UTC."],
  "warnings":["CSV timezone has not been confirmed by the organizer."]
}
```

The example prediction values are placeholders only. Actual responses must contain exactly `horizon_hours` hourly points per turbine and a cutoff that respects the simulated issue time. Until the CSV timezone is confirmed, `training_cutoff_utc` is provisional and must be calculated from an explicit configuration, not inferred from the naive CSV timestamp.

`POST /api/forecast/rolling` takes `{"first_issue_date":"2026-01-31","last_issue_date":"2026-02-28","issue_hour_utc":12,"horizon_hours":48}` and returns one run per day plus coverage/validation metadata. `POST /api/forecast/run` can be repeated after a new eligible weather run is available; the UI compares the two results and shows why they changed.
