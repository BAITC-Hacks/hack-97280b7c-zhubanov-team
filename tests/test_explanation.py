"""The explanation must be grounded in server forecasts and degrade safely."""

from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from backend.explanation import _nvidia_chat, _openai_chat, build_evidence, explain_forecast


def fixture_forecast(issue_text: str, power: float) -> dict:
    issue = datetime.fromisoformat(issue_text.replace("Z", "+00:00"))
    stamp = lambda value: value.isoformat().replace("+00:00", "Z")
    turbines = []
    for number in (1, 2):
        turbines.append({
            "id": f"turbine-{number}", "training_rows": 100,
            "latest_training_time_utc": stamp(issue - timedelta(minutes=10)),
            "source_timezone_assumption": "UTC", "weather_wind_feature": "wind_speed_100m",
            "operator_insight": {"low_generation_hours": 4, "low_generation_windows": [{
                "start_time_utc": stamp(issue + timedelta(hours=1)),
                "end_time_utc": stamp(issue + timedelta(hours=4)), "hours": 4,
            }]},
            "hourly": [{"valid_time_utc": stamp(issue + timedelta(hours=i)),
                        "predicted_normalized_power": power, "forecast_wind_speed_ms": 5.0,
                        "forecast_temperature_c": 3.0} for i in range(1, 49)],
        })
    return {"issue_time_utc": issue_text, "training_cutoff_utc": issue_text,
            "weather": {"source": "Open-Meteo Single Runs API", "model": "ecmwf_ifs",
                        "run_time_utc": stamp(issue - timedelta(hours=12)),
                        "availability_buffer_hours": 12},
            "turbines": turbines, "analysis": [], "warnings": []}


def test_explanation_has_no_raw_history_and_comparison_is_revision_not_accuracy():
    previous = fixture_forecast("2026-01-31T12:00:00Z", 0.2)
    current = fixture_forecast("2026-02-01T12:00:00Z", 0.3)
    facts = build_evidence(current, previous)
    assert facts["horizon_hours"] == 48
    assert facts["turbines"][0]["mean_normalized_power"] == 0.3
    assert facts["comparison"]["changes"][0]["overlapping_hours"] == 24
    assert facts["comparison"]["changes"][0]["mean_absolute_change_normalized_power"] > 0
    assert "hourly" not in facts["turbines"][0]
    assert facts["weather"]["publication_time_verified"] is False
    result = explain_forecast(current, previous, key="")
    assert result["mode"] == "local"
    assert "Февральских фактических значений" in result["text"]
    assert "Пересмотр" in result["text"]
    assert "точност" not in str(result["evidence"]["comparison"]).lower()


def test_ai_response_and_failed_provider_have_explicit_distinct_modes():
    run = fixture_forecast("2026-01-31T12:00:00Z", 0.3)
    captured = []
    ai = explain_forecast(run, key="test-only", model_call=lambda facts, key: captured.append((facts, key)) or "Объяснение по фактам.")
    assert ai["mode"] == "ai" and ai["provider"] == "NVIDIA NIM"
    assert captured[0][1] == "test-only"
    assert "test-only" not in str(ai)

    def unavailable(facts, key):
        raise OSError("temporary upstream outage")

    local = explain_forecast(run, key="test-only", model_call=unavailable)
    assert local["mode"] == "local"
    assert "temporary upstream outage" not in str(local)
    assert "Сервис ИИ недоступен" in local["notice"]


def test_openai_takes_priority_and_falls_back_without_leaking_secret():
    run = fixture_forecast("2026-01-31T12:00:00Z", 0.3)
    with patch("backend.explanation._provider_key", side_effect=lambda name: {
            "OPENAI_API_KEY": "openai-test-secret", "NVIDIA_API_KEY": "nvidia-test-secret"}[name]):
        result = explain_forecast(run, openai_model_call=lambda facts, key: "Факты подтверждены.")
        assert result["mode"] == "ai" and result["provider"] == "OpenAI"
        assert result["model"] == "gpt-4.1-mini"
        assert "openai-test-secret" not in str(result)

        def unavailable(facts, key):
            raise OSError("private upstream detail")

        local = explain_forecast(run, openai_model_call=unavailable)
        assert local["mode"] == "local"
        assert "private upstream detail" not in str(local)
        assert "OpenAI" in local["notice"]


def test_openai_wire_request_uses_responses_and_no_storage():
    run = fixture_forecast("2026-01-31T12:00:00Z", 0.3)
    outbound = []

    def fake_urlopen(request, timeout):
        outbound.append((request, timeout))
        return BytesIO(json.dumps({"status": "completed", "output": [
            {"type": "reasoning", "content": []},
            {"type": "message", "content": [{"type": "output_text", "text": "Объяснение по фактам."}]},
        ]}).encode())

    with patch("backend.explanation.urlopen", side_effect=fake_urlopen):
        text = _openai_chat(build_evidence(run), "secret-for-test")
    assert text == "Объяснение по фактам."
    request, timeout = outbound[0]
    assert request.full_url == "https://api.openai.com/v1/responses"
    assert request.get_method() == "POST" and timeout <= 30
    assert request.get_header("Authorization") == "Bearer secret-for-test"
    body = json.loads(request.data)
    assert body["model"] == "gpt-4.1-mini" and body["store"] is False
    assert "hourly" not in body["input"]
    assert "secret-for-test" not in request.data.decode()


def test_api_recomputes_server_facts_and_rejects_invalid_previous_issue():
    calls = []

    def forecast(issue_time, horizon, **kwargs):
        calls.append(issue_time)
        assert horizon == 48
        return fixture_forecast(issue_time, 0.3 if issue_time.startswith("2026-02-01") else 0.2)

    app = create_app(Settings(source_timezone="UTC", data_dir="unused"),
                     forecast_generator=forecast,
                     explanation_generator=lambda current, previous: explain_forecast(current, previous, key=""))
    with patch("backend.app.audit_inputs", return_value={}):
        client = TestClient(app)
        response = client.post("/api/forecast/explain", json={
            "issue_time_utc": "2026-02-01T12:00:00Z", "horizon_hours": 48,
            "previous_issue_time_utc": "2026-01-31T12:00:00Z"})
        assert response.status_code == 200, response.text
        assert response.json()["mode"] == "local"
        assert response.json()["evidence"]["comparison"]["changes"][0]["overlapping_hours"] == 24
        assert calls == ["2026-02-01T12:00:00Z", "2026-01-31T12:00:00Z"]

        invalid = client.post("/api/forecast/explain", json={
            "issue_time_utc": "2026-02-01T12:00:00Z", "horizon_hours": 48,
            "previous_issue_time_utc": "2026-01-30T12:00:00Z"})
        assert invalid.status_code == 400
        assert len(calls) == 2
        forged = client.post("/api/forecast/explain", json={
            "issue_time_utc": "2026-02-01T12:00:00Z", "horizon_hours": 48,
            "turbines": [{"predicted_normalized_power": 0.99}]})
        assert forged.status_code == 422
        assert len(calls) == 2


def test_nvidia_wire_request_uses_official_chat_shape_and_server_secret_only():
    run = fixture_forecast("2026-01-31T12:00:00Z", 0.3)
    outbound = []

    def fake_urlopen(request, timeout):
        outbound.append((request, timeout))
        return BytesIO(json.dumps({"choices": [{"message": {"content": "Объяснение прогноза."}}]}).encode())

    with patch("backend.explanation.urlopen", side_effect=fake_urlopen):
        text = _nvidia_chat(build_evidence(run), "secret-for-test")
    assert text == "Объяснение прогноза."
    request, timeout = outbound[0]
    assert request.full_url == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert request.get_method() == "POST" and timeout <= 30
    assert request.get_header("Authorization") == "Bearer secret-for-test"
    body = json.loads(request.data)
    assert body["model"] == "meta/llama-3.3-70b-instruct" and body["stream"] is False
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert "secret-for-test" not in request.data.decode()
    assert "hourly" not in body["messages"][1]["content"]
