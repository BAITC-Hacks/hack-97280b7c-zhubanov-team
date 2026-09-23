import { validateForecastResponse } from './forecast.js';

function exportableForecast(forecast) {
  if (forecast?.origin !== 'api') throw new Error('Для выгрузки сначала получите прогноз из API.');
  if (![24, 48].includes(forecast.horizon_hours)) throw new Error('Неизвестный горизонт прогноза.');
  const result = validateForecastResponse(forecast, new Date(forecast.issue_time_utc).toISOString(), forecast.horizon_hours);
  const buffer = result.weather.availability_buffer_hours;
  if (buffer !== undefined && (!Number.isFinite(buffer) || buffer < 0
    || Date.parse(result.weather.run_time_utc) + buffer * 3600000 > Date.parse(result.issue_time_utc))) {
    throw new Error('Метаданные погоды не соблюдают указанный запас доступности.');
  }
  for (const turbine of result.turbines) {
    const cutoff = turbine.training_cutoff_utc ?? result.training_cutoff_utc;
    if (!Number.isFinite(Date.parse(cutoff)) || Date.parse(cutoff) > Date.parse(result.training_cutoff_utc)) {
      throw new Error('Некорректное отсечение обучения турбины.');
    }
    const latest = turbine.latest_training_time_utc;
    if (latest != null && (!Number.isFinite(Date.parse(latest)) || Date.parse(latest) > Date.parse(cutoff))) {
      throw new Error('Последняя обучающая запись превышает отсечение обучения.');
    }
  }
  return result;
}

// Quote every cell and neutralize spreadsheet formulas in external text fields.
function csvCell(value) {
  let text = value == null ? '' : String(value);
  if (typeof value === 'string' && (/^[\t\r\n]/.test(value) || /^[=+\-@]/.test(value.trimStart()))) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

export function forecastCsv(forecast) {
  const result = exportableForecast(forecast);
  const headers = ['data_origin', 'target_unit', 'issue_time_utc', 'valid_time_utc', 'turbine_id',
    'normalized_power', 'forecast_wind_speed_ms', 'forecast_temperature_c', 'weather_source',
    'weather_model', 'weather_run_utc', 'availability_buffer_hours_assumed', 'training_cutoff_utc',
    'latest_training_time_utc', 'source_timezone_assumption', 'power_model'];
  const rows = result.turbines.flatMap((turbine) => turbine.hourly.map((point) => [
    'api', 'dimensionless [0,1]', result.issue_time_utc, point.valid_time_utc, turbine.id,
    point.predicted_normalized_power, point.forecast_wind_speed_ms, point.forecast_temperature_c,
    result.weather.source, result.weather.model, result.weather.run_time_utc,
    result.weather.availability_buffer_hours, turbine.training_cutoff_utc ?? result.training_cutoff_utc,
    turbine.latest_training_time_utc, turbine.source_timezone_assumption, turbine.model,
  ]));
  return '\uFEFF' + [headers, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
}

export function forecastPassport(forecast, comparison = null) {
  const result = exportableForecast(forecast);
  const matchingComparison = comparison && Date.parse(comparison.current_issue_time_utc) === Date.parse(result.issue_time_utc)
    ? comparison : null;
  return JSON.stringify({
    schema_version: 1,
    exported_at_utc: new Date().toISOString(),
    target: 'normalized active power',
    target_unit: 'dimensionless [0,1]',
    turbine_count: result.turbines.length,
    row_count: result.turbines.reduce((total, turbine) => total + turbine.hourly.length, 0),
    limitations: [
      'CSV timezone is an assumption, not organizer-confirmed.',
      'The weather availability buffer is an assumption; actual publication time was not verified.',
      'February actual power was not supplied. No February accuracy or MW/MWh is claimed.',
      'This passport records returned forecast metadata, not an independent audit or live execution trace.',
    ],
    forecast: result,
    recalculation: matchingComparison,
  }, null, 2);
}

export function forecastFilename(forecast, extension) {
  const issue = new Date(forecast.issue_time_utc).toISOString().replaceAll(/[-:.]/g, '');
  return `wind-forecast-${issue}-${forecast.horizon_hours}h.${extension}`;
}

export function downloadText(text, filename, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
