"""Grounded forecast explanation with optional OpenAI or NVIDIA language models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from statistics import mean
from urllib.request import Request, urlopen

NVIDIA_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"
OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"
OPENAI_MODEL = "gpt-4.1-mini"
MAX_RESPONSE_BYTES = 32_768


def _provider_key(key_name: str) -> str | None:
    """Read a server-only secret; never return or log it to the browser."""
    value = os.getenv(key_name, "").strip()
    if value:
        return value
    dotenv = Path(__file__).resolve().parents[1] / ".env"
    if not dotenv.is_file():
        return None
    for line in dotenv.read_text(encoding="utf-8-sig").splitlines():
        name, delimiter, raw = line.partition("=")
        if delimiter and name.strip() == key_name:
            value = raw.strip().strip('"\'')
            return value or None
    return None


def _number(value: float | None, digits: int = 3) -> float | None:
    return round(value, digits) if value is not None else None


def build_evidence(forecast: dict, previous: dict | None = None) -> dict:
    """Select facts for the explainer; no raw organizer observations are sent."""
    issue = forecast["issue_time_utc"]
    weather = forecast["weather"]
    evidence = {
        "issue_time_utc": issue,
        "horizon_hours": len(forecast["turbines"][0]["hourly"]),
        "unit": "normalized active power, dimensionless [0,1]; no MW or MWh",
        "weather": {
            "source": weather["source"], "model": weather["model"],
            "run_time_utc": weather["run_time_utc"],
            "availability_buffer_hours": weather["availability_buffer_hours"],
            "publication_time_verified": False,
        },
        "turbines": [],
        "comparison": None,
        "limits": [
            "CSV timezone is not supplied by the organizers; the chosen interpretation is a scenario.",
            "February actual turbine power was not supplied; February forecast accuracy cannot be measured.",
            "The weather-run buffer is an assumption, not proof of historical publication time.",
            "Low-generation windows are operator advice, not automatic dispatch commands.",
        ],
    }
    for turbine in forecast["turbines"]:
        points = turbine["hourly"]
        powers = [hour["predicted_normalized_power"] for hour in points]
        winds = [hour["forecast_wind_speed_ms"] for hour in points if "forecast_wind_speed_ms" in hour]
        insight = turbine.get("operator_insight", {})
        evidence["turbines"].append({
            "id": turbine["id"],
            "mean_normalized_power": _number(mean(powers)),
            "min_normalized_power": _number(min(powers)),
            "max_normalized_power": _number(max(powers)),
            "mean_forecast_wind_ms": _number(mean(winds), 2) if winds else None,
            "latest_training_time_utc": turbine["latest_training_time_utc"],
            "training_rows": turbine["training_rows"],
            "source_timezone_assumption": turbine["source_timezone_assumption"],
            "weather_wind_feature": turbine["weather_wind_feature"],
            "low_generation_hours": insight.get("low_generation_hours"),
            "low_generation_windows": insight.get("low_generation_windows", [])[:3],
        })
    if previous is not None:
        from forecast.service import compare_recalculation
        evidence["comparison"] = compare_recalculation(previous, forecast)
    return evidence


def local_explanation(evidence: dict) -> str:
    """Always available: detailed facts without any generated claims."""
    lead = (f"Выпуск {evidence['issue_time_utc']}: почасовой прогноз на "
            f"{evidence['horizon_hours']} часов для двух турбин. Мощность нормализована от 0 до 1.")
    turbine_lines = []
    for item in evidence["turbines"]:
        number = item["id"].split("-")[-1]
        description = (f"Турбина {number}: среднее {item['mean_normalized_power']:.3f}, "
                       f"диапазон {item['min_normalized_power']:.3f}–{item['max_normalized_power']:.3f}.")
        if item["mean_forecast_wind_ms"] is not None:
            description += f" Средний прогнозный ветер {item['mean_forecast_wind_ms']:.2f} м/с."
        description += f" Часов ниже сценарного порога: {item['low_generation_hours']}."
        if item["low_generation_windows"]:
            window = item["low_generation_windows"][0]
            description += (f" Первое окно для проверки: {window['start_time_utc']} — "
                            f"{window['end_time_utc']} ({window['hours']} ч).")
        turbine_lines.append(description)
    source = evidence["weather"]
    origin = (f"Источник: {source['source']}, модель {source['model']}, запуск "
              f"{source['run_time_utc']}. Использованы доступные по выбранной границе "
              "исторические данные каждой турбины и ветер 100 м как приближение.")
    comparison = evidence["comparison"]
    if comparison:
        details = []
        for change in comparison["changes"]:
            amount = change["mean_absolute_change_normalized_power"]
            details.append(f"{change['turbine_id']}: {change['overlapping_hours']} общих часов, "
                           f"средний размер пересмотра {amount:.3f}" if amount is not None else
                           f"{change['turbine_id']}: общих часов нет")
        origin += " Пересмотр к предыдущему выпуску: " + "; ".join(details) + "."
    caveat = ("Ограничения: часовой пояс CSV неизвестен, время публикации погоды не подтверждено "
              f"(буфер {source['availability_buffer_hours']} ч — допущение). "
              "Февральских фактических значений мощности нет; оценить точность за февраль нельзя. "
              "Окна низкой выработки — подсказка для оператора, не команда управления.")
    return "\n\n".join([lead, *turbine_lines, origin, caveat])


def _system_prompt() -> str:
    return (
        "Ты объясняешь прогноз ветроэлектростанции по предоставленным фактам. Ответь по-русски "
        "короткими абзацами: ожидаемая нормализованная мощность двух турбин, источник и запуск "
        "погодной модели, граница истории обучения, пересмотр к предыдущему выпуску (если он есть), "
        "что проверить оператору, ограничения. "
        "Используй только JSON фактов. Не придумывай наблюдения, причинно-следственные связи, "
        "точность за февраль, МВт/МВт·ч, экономический эффект, надёжность источника или причины "
        "выбора погодной модели. Если сравнения нет, скажи об этом. "
        "Важно: availability_buffer_hours означает минимальный интервал между временем запуска "
        "погодной модели и временем выпуска прогноза; это НЕ время публикации погодных данных. "
        "Фактическое время публикации не проверено. source_timezone_assumption — сценарная "
        "трактовка CSV, а не известный часовой пояс или подтверждённое значение по умолчанию. "
        "Явно назови эти допущения. Не давай команды управления турбинами."
    )


def _nvidia_chat(evidence: dict, key: str) -> str:
    body = json.dumps({
        "model": NVIDIA_MODEL,
        "messages": [{"role": "system", "content": _system_prompt()},
                     {"role": "user", "content": json.dumps(evidence, ensure_ascii=False)}],
        "temperature": 0.2, "max_tokens": 700, "stream": False,
    }, ensure_ascii=False).encode("utf-8")
    request = Request(NVIDIA_ENDPOINT, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json",
    }, method="POST")
    with urlopen(request, timeout=25) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("NVIDIA response exceeded size limit")
    result = json.loads(raw)
    content = result["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("NVIDIA returned an empty explanation")
    return content.strip()[:5000]


def _openai_chat(evidence: dict, key: str) -> str:
    body = json.dumps({
        "model": OPENAI_MODEL,
        "instructions": _system_prompt(),
        "input": json.dumps(evidence, ensure_ascii=False),
        "max_output_tokens": 700,
        "store": False,
    }, ensure_ascii=False).encode("utf-8")
    request = Request(OPENAI_ENDPOINT, data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json",
    }, method="POST")
    with urlopen(request, timeout=25) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("OpenAI response exceeded size limit")
    result = json.loads(raw)
    if result.get("status") not in (None, "completed"):
        raise ValueError("OpenAI response did not complete")
    parts = [content.get("text", "")
             for item in result.get("output", []) if item.get("type") == "message"
             for content in item.get("content", []) if content.get("type") == "output_text"]
    text = "\n".join(part for part in parts if isinstance(part, str) and part.strip()).strip()
    if not text:
        raise ValueError("OpenAI returned an empty explanation")
    return text[:5000]


def explain_forecast(forecast: dict, previous: dict | None = None, *,
                     key: str | None = None, model_call=None,
                     openai_key: str | None = None, openai_model_call=None) -> dict:
    facts = build_evidence(forecast, previous)
    fallback = local_explanation(facts)
    # Explicit legacy NVIDIA test overrides do not discover a second provider.
    openai_secret = openai_key if openai_key is not None else (
        _provider_key("OPENAI_API_KEY") if key is None else None)
    if openai_secret:
        try:
            generated = (openai_model_call or _openai_chat)(facts, openai_secret)
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            return {"mode": "local", "text": fallback, "evidence": facts,
                    "notice": "Сервис OpenAI недоступен; показано локальное объяснение по данным прогноза."}
        return {"mode": "ai", "text": generated, "evidence": facts,
                "provider": "OpenAI", "model": OPENAI_MODEL,
                "notice": "Текст ИИ основан на указанных фактах. Сверяйте выводы с графиками и паспортом прогноза."}
    secret = key if key is not None else _provider_key("NVIDIA_API_KEY")
    if not secret:
        return {"mode": "local", "text": fallback, "evidence": facts,
                "notice": "Ключ OpenAI или NVIDIA не настроен; показано локальное объяснение по данным прогноза."}
    try:
        generated = (model_call or _nvidia_chat)(facts, secret)
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return {"mode": "local", "text": fallback, "evidence": facts,
                "notice": "Сервис ИИ недоступен; показано локальное объяснение по данным прогноза."}
    return {"mode": "ai", "text": generated, "evidence": facts,
            "provider": "NVIDIA NIM", "model": NVIDIA_MODEL,
            "notice": "Текст ИИ основан на указанных фактах. Сверяйте выводы с графиками и паспортом прогноза."}
