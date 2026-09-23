"""Real model/service/export with isolated synthetic CSVs and archived weather."""

from datetime import datetime, timedelta
import json
from pathlib import Path
import os
import subprocess
import sys
import time

import pytest

import forecast.agent as agent_module
from forecast.agent import AgentConfig, ForecastAgent


@pytest.fixture
def agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    lines = ["ID,time,wind,power,temp"]
    for i in range(180):
        speed, power = [(2, 0.1), (4, 0.4), (6, 0.8)][i % 3]
        timestamp = datetime(2026, 1, 1) + timedelta(minutes=i * 10)
        lines.append(f"{i},{timestamp},{speed},{power},5")
    for turbine in ("turbine-1", "turbine-2"):
        (inputs / f"{turbine}.csv").write_text("\n".join(lines), encoding="utf-8")
    cache = Path("data/cache/weather")
    cache.mkdir(parents=True)
    for day in (datetime(2026, 1, 31), datetime(2026, 2, 1)):
        payload = {"hourly": {
            "time": [(day + timedelta(hours=h)).isoformat(timespec="minutes") for h in range(72)],
            "wind_speed_10m": [4.0] * 72, "wind_speed_100m": [6.0] * 72,
            "temperature_2m": [5.0] * 72,
        }}
        for turbine in ("turbine-1", "turbine-2"):
            (cache / f"ecmwf_ifs_{turbine}_{day:%Y%m%dT%H%M}.json").write_text(json.dumps(payload))
    return ForecastAgent(AgentConfig("UTC", last_issue_date="2026-02-01"),
                         data_dir=inputs, output_dir=tmp_path / "agent-output")


def test_input_change_recalculates_once_and_preserves_prior_revision(agent):
    first = agent.tick()
    assert first["event"] == "forecast_published"
    assert first["row_count"] == 192
    assert agent.tick()["event"] == "unchanged"
    csv = agent.data_dir / "turbine-1.csv"
    csv.write_text(csv.read_text().replace(",6,0.8,5", ",6,0.6,5"))
    second = agent.tick()
    assert second["reason"] == "inputs_changed"
    assert second["changed_inputs"] == ["csv/turbine-1.csv"]
    assert second["previous_revision_id"] == first["revision_id"]
    assert second["revision_change"]["changed_points"] == 96
    assert second["revision_change"]["max_absolute_revision"] == pytest.approx(0.2)
    assert (agent.output_dir / first["revision_id"] / "bundle/forecasts.csv").is_file()
    assert (agent.output_dir / second["revision_id"] / "bundle/forecasts.csv").is_file()
    assert agent.tick()["event"] == "unchanged"


@pytest.mark.parametrize("invalid", ['{"incomplete":', '{"hourly": null}'])
def test_bad_weather_does_not_publish_and_is_retried_after_repair(agent, invalid):
    first = agent.tick()
    latest = (agent.output_dir / "latest.json").read_bytes()
    weather = next(path for name, path in agent.files.items() if name.startswith("weather/"))
    original = json.loads(weather.read_text())
    weather.write_text(invalid)
    assert agent.tick()["event"] == "forecast_failed"
    assert (agent.output_dir / "latest.json").read_bytes() == latest
    original["hourly"]["wind_speed_100m"] = [4.0] * 72
    weather.write_text(json.dumps(original))
    repaired = agent.tick()
    assert repaired["event"] == "forecast_published"
    assert repaired["previous_revision_id"] == first["revision_id"]
    assert repaired["revision_change"]["changed_points"] == 48
    events = [json.loads(line)["event"] for line in (agent.output_dir / "events.jsonl").read_text().splitlines()]
    assert "forecast_failed" in events
    assert events.count("forecast_published") == 2


def test_mid_calculation_change_rejected_then_retried(agent, monkeypatch):
    original = agent_module.generate_rolling_forecasts
    csv = agent.data_dir / "turbine-1.csv"

    def changed_during_calculation(**kwargs):
        output = original(**kwargs)
        csv.write_text(csv.read_text().replace(",6,0.8,5", ",6,0.6,5"))
        return output

    monkeypatch.setattr(agent_module, "generate_rolling_forecasts", changed_during_calculation)
    assert agent.tick()["event"] == "forecast_failed"
    assert not (agent.output_dir / "latest.json").exists()
    monkeypatch.setattr(agent_module, "generate_rolling_forecasts", original)
    assert agent.tick()["event"] == "forecast_published"


def test_first_download_populates_missing_cache_without_redundant_rerun(agent, monkeypatch):
    import io
    import backend.weather as weather_module

    path = next(path for name, path in agent.files.items() if name.startswith("weather/"))
    raw = path.read_text()
    path.unlink()  # Only this test's temporary synthetic weather file.
    calls = []

    def download(url, timeout):
        calls.append(url)
        return io.StringIO(raw)

    monkeypatch.setattr(weather_module, "urlopen", download)
    assert agent.tick()["event"] == "forecast_published"
    assert len(calls) == 1
    assert path.exists()
    assert agent.tick()["event"] == "unchanged"


def test_invalid_measurements_keep_last_valid_publication(agent):
    agent.tick()
    latest = (agent.output_dir / "latest.json").read_bytes()
    csv = agent.data_dir / "turbine-1.csv"
    csv.write_text(csv.read_text().replace(",6,0.8,5", ",6,1.8,5"))
    failure = agent.tick()
    assert failure["event"] == "forecast_failed"
    assert "invalid measurements" in failure["error"]
    assert (agent.output_dir / "latest.json").read_bytes() == latest


def test_watch_cli_detects_update_without_a_manual_tick(agent):
    env = {**os.environ, "PYTHONPATH": str(Path(agent_module.__file__).resolve().parents[1])}
    command = [sys.executable, "-m", "forecast.agent", "--source-timezone", "UTC",
               "--last-issue-date", "2026-02-01", "--data-dir", str(agent.data_dir),
               "--output-dir", str(agent.output_dir), "--watch", "--poll-seconds", "1",
               "--max-checks", "3"]
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 20
        latest = agent.output_dir / "latest.json"
        while not latest.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert latest.exists(), "CLI did not publish its first revision"
        csv = agent.data_dir / "turbine-1.csv"
        csv.write_text(csv.read_text().replace(",6,0.8,5", ",6,0.6,5"))
        stdout, stderr = process.communicate(timeout=20)
        assert process.returncode == 0, stderr
        events = [json.loads(line) for line in stdout.splitlines()]
        assert [event["event"] for event in events] == [
            "forecast_published", "forecast_published", "unchanged"]
        assert events[1]["reason"] == "inputs_changed"
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=5)
