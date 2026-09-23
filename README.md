# HackAlem — Wind Farm Forecast Agent

Official case: [Agentic AI for wind farm generation forecasting](https://docs.google.com/document/d/1Fn5IJoj87Fx7IAknG26zkfX8c0eq7feCujd0m66PCgY/edit). Our goal is hourly normalized-power forecasts for two wind turbines over a 24–48-hour horizon, issued repeatedly during February 2026 using weather forecasts available at each issue time.

The organizer supplied two 10-minute CSV histories ending January 31, 2026. They contain no February actual power, so February forecast error cannot yet be measured. See [data audit](docs/data-audit.md), [case map](docs/case-map.md), [API contract](docs/api-contract.md), and [team tasks](docs/team-tasks.md).

## Data setup

Download the private organizer files into ignored local paths:

- [Turbine 1](https://drive.google.com/file/d/1hubNF3tgc7DbgXxHLpIF6zIBHtvMyzLX/view) → `data/input/turbine-1.csv`
- [Turbine 2](https://drive.google.com/file/d/1_WTrYhZ3-71A9IpkBb9RHPN7ncVaupBk/view) → `data/input/turbine-2.csv`

Never commit these source files. Run instructions and validation commands will be added with the implementation. Until then this repository contains the agreed requirements and interface; it is not yet a working forecast application.
