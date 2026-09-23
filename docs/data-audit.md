# Organizer data audit (2026-09-23)

The two linked CSVs were inspected locally; raw rows are deliberately excluded from Git.

| Dataset | Rows | First timestamp | Last timestamp | Missing target | Duplicate timestamps |
|---|---:|---|---|---:|---:|
| Turbine 1 | 142,360 | 2023-03-11 00:00 | 2026-01-31 23:50 | 0 | 0 |
| Turbine 2 | 149,499 | 2023-03-11 00:00 | 2026-01-31 23:50 | 0 | 0 |

Columns: `ID`, `Статистическое время`, `Средняя скорость ветра(m/s)`, `Нормализованная активная мощность`, `Средняя температура окружающей среды(°C)`. Nominal sampling is every ten minutes. Target values are within [0,1]. Check gaps and coverage during preprocessing; do not silently fill large missing intervals.

The complete timestamp span would contain 152,352 ten-minute slots per turbine. Turbine 1 covers **93.44%** of those slots (67 gaps longer than ten minutes, 31 gaps of at least one hour); its largest gap is **999 hours** between 2024-05-18 03:40 and 2024-06-28 18:40, followed by a 450.3-hour gap into July 17. Turbine 2 covers **98.13%** (178 gaps longer than ten minutes, 78 gaps of at least one hour); its largest gap is **57.5 hours**. Both have a complete **4,464/4,464 ten-minute rows in January 2026**, which supports the January forecast validation. These figures count timestamp slots and do not imply that missing output was zero. No long gap is filled for model fitting or evaluation.

Locations from organizer map links: turbine 1 `43.643198, 78.538828`; turbine 2 `43.645150, 78.535604`. The source CSV does not state timezone or turbine rated capacities. Keep those as explicit assumptions/settings.

Weather source candidate: [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api), archived ECMWF IFS runs. A Jan 31, 2026 00:00 UTC run was successfully queried for these coordinates with hourly 10 m/100 m wind speed and 2 m temperature. Use a conservative 12-hour run-to-issue buffer until exact publication timing is established. Run initialization time alone is not proof that the run was publicly available then.
