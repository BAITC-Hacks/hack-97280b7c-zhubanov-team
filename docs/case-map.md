# Case map

Source: [official wind-farm case](https://docs.google.com/document/d/1Fn5IJoj87Fx7IAknG26zkfX8c0eq7feCujd0m66PCgY/edit).

| Requirement | Implementation target | Evidence in demo |
|---|---|---|
| Hourly generation forecast, 24–48 hours | Per-turbine normalized active-power series | 48 timestamped points for each turbine |
| Two turbine locations and historical operating data | Local CSV parser and per-turbine models | Data coverage and input audit |
| Autonomously obtain open-source weather forecasts | Archived forecast-run client | Source, model, run and issue timestamps |
| Prepare inputs and forecast | 10-minute-to-hourly training preparation; forecasting module | Reproducible result from a selected issue time |
| Analyze and recalculate when inputs update | Agent orchestration and rerun action | Versioned previous and new result with change explanation |
| Historical issuance, Jan 31 then daily in February | Rolling 24/48-hour issue schedule | Timeline of daily issue timestamps and forecast coverage |

Critical distinction: the model may use February **weather forecasts that were already published by the chosen issue time**, but not realized February weather or February turbine output. The supplied turbine CSVs stop January 31, so a genuine February error metric needs further actuals from organizers. Validate model quality on held-out data before February and report the period and source transparently.

Evaluation weights in the case: functionality 25%, technical implementation 25%, reproducibility/README 25%, value 15%, originality 10%.
