"""Observe local historical inputs, recalculate changed inputs and publish revisions.

This is a deterministic controller, not an LLM planner or a live-weather scheduler.
Run from the repository root; the weather service uses data/cache/weather there.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time as clock
from uuid import uuid4
from zoneinfo import ZoneInfo

from backend.data import audit_inputs
from backend.weather import LOCATIONS, MODEL, available_run
from forecast.export import export_forecasts, validate_rows
from forecast.service import generate_rolling_forecasts


@dataclass(frozen=True)
class AgentConfig:
    source_timezone: str
    first_issue_date: str = "2026-01-31"
    last_issue_date: str = "2026-02-28"
    issue_hour_utc: int = 12
    horizon_hours: int = 48

    def __post_init__(self):
        ZoneInfo(self.source_timezone)
        first, last = date.fromisoformat(self.first_issue_date), date.fromisoformat(self.last_issue_date)
        if not 0 <= (last - first).days <= 60:
            raise ValueError("Date range must be ordered and at most 61 days")
        if self.horizon_hours not in (24, 48) or not 0 <= self.issue_hour_utc <= 23:
            raise ValueError("Choose a 24/48-hour horizon and an issue hour in 0..23")


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _revision_change(previous: list[dict] | None, current: list[dict]) -> dict | None:
    if previous is None:
        return None
    key = lambda row: (row["issue_time_utc"], row["turbine_id"], row["valid_time_utc"])
    earlier = {key(row): row["normalized_power"] for row in previous}
    changes = [abs(row["normalized_power"] - earlier[key(row)])
               for row in current if key(row) in earlier]
    return {
        "matched_points": len(changes),
        "changed_points": sum(value > 1e-12 for value in changes),
        "mean_absolute_revision": sum(changes) / len(changes) if changes else None,
        "max_absolute_revision": max(changes, default=None),
        "note": "Changes between recalculations, not forecast accuracy.",
    }


class ForecastAgent:
    """One tick observes inputs and decides whether a new revision is necessary.

    A failed calculation never replaces latest.json or marks changed inputs handled.
    One process must own an output directory; restarting starts a new initial revision.
    """

    def __init__(self, config: AgentConfig, *, data_dir: Path, output_dir: Path):
        self.config = config
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.accepted_inputs: dict | None = None
        self.previous_rows: list[dict] | None = None
        self.previous_revision: str | None = None
        self.files = {f"csv/{name}.csv": self.data_dir / f"{name}.csv" for name in LOCATIONS}
        first, last = date.fromisoformat(config.first_issue_date), date.fromisoformat(config.last_issue_date)
        for offset in range((last - first).days + 1):
            issue = datetime.combine(first + timedelta(days=offset), time(config.issue_hour_utc), timezone.utc)
            run = available_run(issue)
            for name in LOCATIONS:
                filename = f"{MODEL}_{name}_{run:%Y%m%dT%H%M}.json"
                self.files[f"weather/{filename}"] = Path("data/cache/weather") / filename

    def snapshot(self) -> dict:
        hashes = {}
        for name, path in self.files.items():
            try:
                with path.open("rb") as stream:
                    hashes[name] = hashlib.file_digest(stream, "sha256").hexdigest()
            except FileNotFoundError:
                hashes[name] = None
        return hashes

    def record(self, event: str, **details) -> dict:
        entry = {"time_utc": _stamp(), "event": event, **details}
        with (self.output_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def tick(self) -> dict:
        try:
            before = self.snapshot()
            if before == self.accepted_inputs:
                return {"event": "unchanged", "revision_id": self.previous_revision}
            reason = "initial_run" if self.accepted_inputs is None else "inputs_changed"
            changed = list(before) if self.accepted_inputs is None else [
                name for name in before if before[name] != self.accepted_inputs[name]
            ]
            self.record("forecast_started", reason=reason, changed_inputs=changed)
            cutoff = f"{self.config.last_issue_date}T{self.config.issue_hour_utc:02d}:00:00Z"
            audit_inputs(self.data_dir, cutoff, self.config.source_timezone)
            self.record("input_audit_completed")
            payload = generate_rolling_forecasts(**asdict(self.config), data_dir=self.data_dir)
            rows, summary = validate_rows(payload)
            after = self.snapshot()
            # Missing weather files may be filled by the service. Existing files
            # must remain stable throughout the calculation; otherwise retry.
            unstable = [name for name in before if before[name] != after[name]
                        and (before[name] is not None or name.startswith("csv/"))]
            if unstable or any(value is None for value in after.values()):
                raise ValueError("Inputs changed during calculation or remain missing; retry required")
            change = _revision_change(self.previous_rows, rows)
            self.record("forecast_validated", issue_count=summary["issue_count"],
                        row_count=len(rows), revision_change=change)
            revision_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:12]
            revision = self.output_dir / revision_id
            revision.mkdir()
            _write_json(revision / "rolling.json", payload)
            export_forecasts(revision / "rolling.json", revision / "bundle")
            report = {
                "revision_id": revision_id, "previous_revision_id": self.previous_revision,
                "created_at_utc": _stamp(), "reason": reason, "changed_inputs": changed,
                "configuration": asdict(self.config), "input_sha256": after,
                "revision_change": change, "issue_count": summary["issue_count"],
                "row_count": len(rows),
                "historical_note": "A revised replay is not proof that corrected inputs existed historically.",
                "weather_availability_note": summary["weather_availability_note"],
            }
            _write_json(revision / "revision.json", report)
            pending = self.output_dir / f".latest-{uuid4().hex}.json"
            _write_json(pending, report)
            pending.replace(self.output_dir / "latest.json")
            self.accepted_inputs, self.previous_rows, self.previous_revision = after, rows, revision_id
            return self.record("forecast_published", **report)
        except (OSError, ValueError) as exc:
            return self.record("forecast_failed", error_type=type(exc).__name__,
                               error=str(exc)[:500], last_successful_revision=self.previous_revision)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-timezone", required=True)
    parser.add_argument("--first-issue-date", default="2026-01-31")
    parser.add_argument("--last-issue-date", default="2026-02-28")
    parser.add_argument("--issue-hour-utc", type=int, default=12)
    parser.add_argument("--horizon-hours", type=int, choices=(24, 48), default=48)
    parser.add_argument("--data-dir", type=Path, default=Path("data/input"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/agent"))
    parser.add_argument("--watch", action="store_true", help="Keep checking local input content for changes")
    parser.add_argument("--poll-seconds", type=float, default=60)
    parser.add_argument("--max-checks", type=int, help="Stop after this many checks; default unbounded in watch mode")
    args = parser.parse_args()
    if args.poll_seconds < 1 or (args.max_checks is not None and args.max_checks < 1):
        parser.error("poll-seconds and max-checks must be positive (minimum interval 1 second)")
    try:
        config = AgentConfig(args.source_timezone, args.first_issue_date, args.last_issue_date,
                             args.issue_hour_utc, args.horizon_hours)
        agent = ForecastAgent(config, data_dir=args.data_dir, output_dir=args.output_dir)
    except (ValueError, KeyError) as exc:
        parser.error(str(exc))
    limit = args.max_checks if args.watch else 1
    checks = 0
    try:
        while limit is None or checks < limit:
            event = agent.tick()
            print(json.dumps({key: event[key] for key in ("event", "revision_id", "reason", "error")
                              if key in event}, ensure_ascii=False), flush=True)
            checks += 1
            if not args.watch or (limit is not None and checks >= limit):
                if event["event"] == "forecast_failed":
                    raise SystemExit(1)
                break
            clock.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print("Forecast observer stopped.")


if __name__ == "__main__":
    main()
