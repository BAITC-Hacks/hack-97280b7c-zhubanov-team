export const DEFAULT_ISSUE = '2026-01-31T12:00';
export const FIRST_ISSUE = '2026-01-31T00:00';
export const LAST_ISSUE = '2026-02-28T23:00';

export function issueValueToUtc(value) {
  if (!value || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) {
    throw new Error('Выберите дату и время выпуска.');
  }
  const timestamp = Date.parse(`${value}:00Z`);
  if (!Number.isFinite(timestamp)) throw new Error('Не удалось прочитать дату выпуска.');
  return new Date(timestamp).toISOString();
}

export function shiftIssue(value, days) {
  const timestamp = Date.parse(`${value}:00Z`);
  if (!Number.isFinite(timestamp)) return value;
  const next = new Date(timestamp + days * 24 * 60 * 60 * 1000);
  return `${next.toISOString().slice(0, 16)}`;
}

export function formatUtc(value, options = {}) {
  if (!value || !Number.isFinite(Date.parse(value))) return '—';
  const { dateOnly = false, ...formatOptions } = options;
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'UTC',
    ...(dateOnly
      ? { day: '2-digit', month: 'short', year: 'numeric' }
      : { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false }),
    ...formatOptions,
  }).format(new Date(value));
}

function requireDate(value, label) {
  const isUtcTimestamp = typeof value === 'string'
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(value);
  if (!isUtcTimestamp || !Number.isFinite(Date.parse(value))) {
    throw new Error(`В ответе API нет корректного поля «${label}».`);
  }
  return Date.parse(value);
}

function validateOperatorInsight(insight, turbineId) {
  if (insight === undefined) return undefined;
  if (!insight || typeof insight !== 'object' || Array.isArray(insight)) {
    throw new Error(`${turbineId}: некорректный блок операторского анализа.`);
  }

  const threshold = insight.threshold_normalized_power;
  if (threshold !== undefined && (typeof threshold !== 'number' || !Number.isFinite(threshold) || threshold < 0 || threshold > 1)) {
    throw new Error(`${turbineId}: порог сценария должен быть в диапазоне от 0 до 1.`);
  }
  const minimumHours = insight.minimum_window_hours;
  if (minimumHours !== undefined && (!Number.isInteger(minimumHours) || minimumHours < 1)) {
    throw new Error(`${turbineId}: минимальная длительность окна указана некорректно.`);
  }
  const fullLoadHours = insight.forecast_full_load_hours_equivalent;
  if (fullLoadHours !== undefined && (typeof fullLoadHours !== 'number' || !Number.isFinite(fullLoadHours) || fullLoadHours < 0)) {
    throw new Error(`${turbineId}: эквивалент часов полной нагрузки указан некорректно.`);
  }
  const lowHours = insight.low_generation_hours;
  if (lowHours !== undefined && (!Number.isInteger(lowHours) || lowHours < 0)) {
    throw new Error(`${turbineId}: число часов низкой мощности указано некорректно.`);
  }
  if (insight.operator_review_recommended !== undefined && typeof insight.operator_review_recommended !== 'boolean') {
    throw new Error(`${turbineId}: флаг проверки оператором указан некорректно.`);
  }
  if (insight.note !== undefined && typeof insight.note !== 'string') {
    throw new Error(`${turbineId}: пояснение операторского анализа указано некорректно.`);
  }

  const windows = insight.low_generation_windows ?? [];
  if (!Array.isArray(windows)) throw new Error(`${turbineId}: список окон низкой мощности указан некорректно.`);
  const validWindows = windows.map((window, index) => {
    requireDate(window?.start_time_utc, `${turbineId}.operator_insight.low_generation_windows[${index}].start_time_utc`);
    requireDate(window?.end_time_utc, `${turbineId}.operator_insight.low_generation_windows[${index}].end_time_utc`);
    if (!Number.isInteger(window.hours) || window.hours < 1) {
      throw new Error(`${turbineId}: длительность окна низкой мощности указана некорректно.`);
    }
    return window;
  });
  return { ...insight, low_generation_windows: validWindows };
}

export function validateForecastResponse(payload, expectedIssueTime, horizonHours) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('API вернул пустой или некорректный ответ.');
  }

  const issueTime = requireDate(payload.issue_time_utc, 'issue_time_utc');
  if (new Date(issueTime).toISOString() !== expectedIssueTime) {
    throw new Error('Время выпуска в ответе API не совпадает с выбранным.');
  }
  const cutoff = requireDate(payload.training_cutoff_utc, 'training_cutoff_utc');
  if (cutoff > issueTime) {
    throw new Error('API вернул отсечение обучения позже времени выпуска. Результат скрыт.');
  }

  const weather = payload.weather;
  if (!weather || typeof weather.source !== 'string' || typeof weather.model !== 'string') {
    throw new Error('В ответе API отсутствуют источник или модель погоды.');
  }
  const weatherRunTime = requireDate(weather.run_time_utc, 'weather.run_time_utc');
  if (weatherRunTime >= issueTime) {
    throw new Error('Время погодного запуска должно быть раньше выпуска. Результат скрыт.');
  }

  if (!Array.isArray(payload.turbines)) throw new Error('В ответе API нет списка турбин.');
  const expectedIds = ['turbine-1', 'turbine-2'];
  if (payload.turbines.length !== expectedIds.length) {
    throw new Error('API должен вернуть ровно две турбины по контракту.');
  }
  const foundIds = payload.turbines.map((turbine) => turbine?.id);
  if (expectedIds.some((id) => !foundIds.includes(id))) {
    throw new Error('API должен вернуть прогноз для turbine-1 и turbine-2.');
  }

  const turbines = expectedIds.map((id) => {
    const turbine = payload.turbines.find((entry) => entry?.id === id);
    if (!Array.isArray(turbine.hourly) || turbine.hourly.length !== horizonHours) {
      throw new Error(`${id}: ожидалось ${horizonHours} почасовых точек.`);
    }
    const hourly = turbine.hourly.map((point, index) => {
      const validTime = requireDate(point?.valid_time_utc, `${id}.hourly[${index}].valid_time_utc`);
      const power = point?.predicted_normalized_power;
      if (validTime !== issueTime + (index + 1) * 60 * 60 * 1000) {
        throw new Error(`${id}: ожидалась непрерывная почасовая серия сразу после выпуска.`);
      }
      if (typeof power !== 'number' || !Number.isFinite(power) || power < 0 || power > 1) {
        throw new Error(`${id}: прогноз мощности должен быть числом в диапазоне от 0 до 1.`);
      }
      const wind = point.forecast_wind_speed_ms;
      if (wind !== undefined && (typeof wind !== 'number' || !Number.isFinite(wind) || wind < 0)) {
        throw new Error(`${id}: прогнозная скорость ветра должна быть неотрицательным числом.`);
      }
      const temperature = point.forecast_temperature_c;
      if (temperature !== undefined && (typeof temperature !== 'number' || !Number.isFinite(temperature))) {
        throw new Error(`${id}: прогнозная температура указана некорректно.`);
      }
      return { ...point, valid_time_utc: point.valid_time_utc, predicted_normalized_power: power };
    });
    return { ...turbine, hourly, operator_insight: validateOperatorInsight(turbine.operator_insight, id) };
  });

  return {
    ...payload,
    origin: 'api',
    horizon_hours: horizonHours,
    turbines,
    analysis: Array.isArray(payload.analysis) ? payload.analysis.filter((line) => typeof line === 'string') : [],
    warnings: Array.isArray(payload.warnings) ? payload.warnings.filter((line) => typeof line === 'string') : [],
  };
}

export function createDemoForecast(issueTimeUtc, horizonHours) {
  const issueMillis = Date.parse(issueTimeUtc);
  const weatherRun = new Date(issueMillis - 12 * 60 * 60 * 1000).toISOString();
  const cutoff = new Date(issueMillis - 10 * 60 * 1000).toISOString();
  const turbines = [
    { id: 'turbine-1', phase: 0.2, baseline: 0.49, amplitude: 0.25 },
    { id: 'turbine-2', phase: 0.85, baseline: 0.44, amplitude: 0.23 },
  ].map(({ id, phase, baseline, amplitude }) => ({
    id,
    hourly: Array.from({ length: horizonHours }, (_, index) => {
      const validTime = new Date(issueMillis + (index + 1) * 60 * 60 * 1000).toISOString();
      const wave = Math.sin(index / 5.1 + phase) * amplitude;
      const gust = Math.cos(index / 10.7 + phase) * 0.09;
      const hourOfDay = index % 24;
      const isSyntheticLowWindow = hourOfDay >= 15 && hourOfDay < 20;
      const power = isSyntheticLowWindow
        ? 0.12 + (0.03 * (1 + Math.sin(index + phase)))
        : Math.max(0, Math.min(1, baseline + wave + gust));
      const forecastWind = 6.5 + (2.2 * Math.sin(index / 6.4 + phase)) + (0.8 * Math.cos(index / 10 + phase));
      const forecastTemperature = 4 + (4.5 * Math.sin(index / 16 + phase));
      return {
        valid_time_utc: validTime,
        predicted_normalized_power: Number(power.toFixed(3)),
        forecast_wind_speed_ms: Number(Math.max(0, forecastWind).toFixed(2)),
        forecast_temperature_c: Number(forecastTemperature.toFixed(1)),
      };
    }),
  })).map((turbine) => ({ ...turbine, operator_insight: summarizeForecast(turbine.hourly) }));

  return {
    run_id: `demo-${issueTimeUtc.replace(/[-:]/g, '').replace('T', '-')}`,
    issue_time_utc: issueTimeUtc,
    training_cutoff_utc: cutoff,
    weather: {
      source: 'Локальная демонстрационная фикстура',
      model: 'synthetic-demo',
      run_time_utc: weatherRun,
    },
    turbines,
    analysis: ['Демонстрационные кривые нужны только для показа интерфейса; это не расчёт модели.'],
    warnings: ['Все значения и метаданные этого режима синтетические. Не используйте их как прогноз или оценку точности.'],
    origin: 'demo',
    horizon_hours: horizonHours,
  };
}

function summarizeForecast(hourly) {
  const threshold = 0.2;
  const minimumHours = 4;
  const lowGenerationWindows = [];
  let startTime = null;
  let endTime = null;
  let duration = 0;

  function finishWindow() {
    if (duration >= minimumHours) {
      lowGenerationWindows.push({ start_time_utc: startTime, end_time_utc: endTime, hours: duration });
    }
    startTime = null;
    endTime = null;
    duration = 0;
  }

  for (const point of hourly) {
    if (point.predicted_normalized_power < threshold) {
      startTime ??= point.valid_time_utc;
      endTime = point.valid_time_utc;
      duration += 1;
    } else {
      finishWindow();
    }
  }
  finishWindow();

  return {
    threshold_normalized_power: threshold,
    minimum_window_hours: minimumHours,
    forecast_full_load_hours_equivalent: Number(hourly.reduce((sum, point) => sum + point.predicted_normalized_power, 0).toFixed(3)),
    low_generation_hours: hourly.filter((point) => point.predicted_normalized_power < threshold).length,
    low_generation_windows: lowGenerationWindows,
    operator_review_recommended: lowGenerationWindows.length > 0,
    note: lowGenerationWindows.length > 0
      ? 'Синтетическое окно отмечено только для демонстрации операторской проверки; это не команда на диспетчеризацию.'
      : 'Синтетические значения не образуют длинного окна ниже выбранного порога.',
  };
}

export function compareForecastRuns(previous, next) {
  if (!previous || !next || previous.origin !== 'api' || next.origin !== 'api') return null;
  if (Date.parse(next.issue_time_utc) <= Date.parse(previous.issue_time_utc)) return null;
  const turbines = [];
  for (const id of ['turbine-1', 'turbine-2']) {
    const oldPoints = previous.turbines.find((turbine) => turbine.id === id)?.hourly ?? [];
    const newPoints = next.turbines.find((turbine) => turbine.id === id)?.hourly ?? [];
    const oldByTime = new Map(oldPoints.map((point) => [point.valid_time_utc, point]));
    const overlap = newPoints
      .filter((point) => oldByTime.has(point.valid_time_utc))
      .map((point) => ({ previous: oldByTime.get(point.valid_time_utc), current: point }));
    if (!overlap.length) continue;

    const powerChanges = overlap.map(({ previous: oldPoint, current }) => current.predicted_normalized_power - oldPoint.predicted_normalized_power);
    const windChanges = overlap
      .filter(({ previous: oldPoint, current }) => Number.isFinite(oldPoint.forecast_wind_speed_ms) && Number.isFinite(current.forecast_wind_speed_ms))
      .map(({ previous: oldPoint, current }) => current.forecast_wind_speed_ms - oldPoint.forecast_wind_speed_ms);
    const largest = overlap.reduce((best, pair) => {
      const change = Math.abs(pair.current.predicted_normalized_power - pair.previous.predicted_normalized_power);
      return change > best.change ? { ...pair, change } : best;
    }, { ...overlap[0], change: -1 });
    turbines.push({
      turbine_id: id,
      overlapping_hours: overlap.length,
      mean_change_normalized_power: powerChanges.reduce((sum, value) => sum + value, 0) / powerChanges.length,
      mean_absolute_change_normalized_power: powerChanges.reduce((sum, value) => sum + Math.abs(value), 0) / powerChanges.length,
      mean_forecast_wind_change_ms: windChanges.length
        ? windChanges.reduce((sum, value) => sum + value, 0) / windChanges.length
        : null,
      largest_revision: {
        valid_time_utc: largest.current.valid_time_utc,
        previous_normalized_power: largest.previous.predicted_normalized_power,
        current_normalized_power: largest.current.predicted_normalized_power,
        absolute_change_normalized_power: largest.change,
        previous_forecast_wind_speed_ms: largest.previous.forecast_wind_speed_ms ?? null,
        current_forecast_wind_speed_ms: largest.current.forecast_wind_speed_ms ?? null,
      },
    });
  }
  return {
    previous_issue_time_utc: previous.issue_time_utc,
    current_issue_time_utc: next.issue_time_utc,
    turbines,
  };
}
