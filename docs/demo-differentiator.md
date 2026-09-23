# Judge-facing distinction: an auditable forecast decision loop

We cannot know what other teams will build. Our concrete distinction is a **repeatable historical decision loop**, not just a forecast chart:

1. Choose a simulated issue time. Fetch an archived weather **model run available before that time**, show its UTC run timestamp and the turbine training cutoff.
2. Forecast both turbines for 48 hours. Show normalized power, the specific wind/temperature forecast used for each hour, and a low-generation window for operator review.
3. Move to the next day's issue. Compare only the 24 hours present in both forecasts. Show the largest revised hour, average change in normalized power, and the associated change in forecast wind speed. The weather comparison is evidence of changed input, not a causal proof.
4. Show the ten-issue January diagnostic against a six-hour persistence baseline. State that CSV timezone is undefined and results are scenario-dependent; February actual power and turbine MW ratings were not supplied.

`forecast/insights.py` generates the low-output windows and full-load-hour **equivalents** per turbine. The threshold `0.2` normalized power and minimum four-hour window are explicit demo scenario parameters, not a grid rule. The system never sends dispatch instructions or claims MWh. An operator decides what action, if any, to take.

This workflow directly demonstrates automatic data retrieval, analysis, recalculation, provenance, and human review while remaining reproducible from the provided CSVs and [Open-Meteo Single Runs](https://open-meteo.com/en/docs/single-runs-api). The frontend can render the optional `operator_insight` object for each turbine and `largest_revision` inside each recalculation change; existing required forecast fields remain unchanged.
