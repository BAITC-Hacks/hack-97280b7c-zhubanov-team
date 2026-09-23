import { useId } from 'react';
import { formatUtc } from './forecast.js';

const CHART = { width: 760, height: 292, left: 58, right: 18, top: 20, bottom: 48 };
const Y_TICKS = [0, 0.25, 0.5, 0.75, 1];

function timeLabel(value, includeDate = false) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return '—';
  const time = new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'UTC', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date);
  if (!includeDate) return time;
  const day = new Intl.DateTimeFormat('ru-RU', { timeZone: 'UTC', day: '2-digit', month: 'short' }).format(date);
  return `${day}, ${time}`;
}

export default function ForecastChart({ turbine, index }) {
  const gradientId = `forecast-area-${useId().replace(/:/g, '')}`;
  const points = turbine.hourly;
  const windValues = points.map((point) => point.forecast_wind_speed_ms).filter(Number.isFinite);
  const temperatureValues = points.map((point) => point.forecast_temperature_c).filter(Number.isFinite);
  const mean = (values) => values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  const meanWind = mean(windValues);
  const meanTemperature = mean(temperatureValues);
  const plotWidth = CHART.width - CHART.left - CHART.right;
  const plotHeight = CHART.height - CHART.top - CHART.bottom;
  const x = (i) => CHART.left + (points.length <= 1 ? 0 : (i / (points.length - 1)) * plotWidth);
  const y = (value) => CHART.top + (1 - value) * plotHeight;
  const linePath = points.map((point, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(point.predicted_normalized_power).toFixed(1)}`).join(' ');
  const areaPath = `${linePath} L ${x(points.length - 1).toFixed(1)} ${(CHART.top + plotHeight).toFixed(1)} L ${x(0).toFixed(1)} ${(CHART.top + plotHeight).toFixed(1)} Z`;
  const tickIndices = [...new Set([0, Math.round((points.length - 1) / 3), Math.round(2 * (points.length - 1) / 3), points.length - 1])];
  const isFirst = index === 0;

  return (
    <article className={`chart-card chart-card--${isFirst ? 'teal' : 'blue'}`}>
      <div className="chart-card__heading">
        <div className="chart-card__identity">
          <span className={`turbine-mark turbine-mark--${isFirst ? 'teal' : 'blue'}`} aria-hidden="true">
            <svg viewBox="0 0 40 40" fill="none">
              <path d="M20 18.8 11.4 7.1c-.7-.9.1-2.2 1.2-1.9l8.1 2.2.2 11.4Zm1.7 1.2 13.8-3.9c1.1-.3 2 .9 1.4 1.9l-4.8 7-10.4-5Zm-2.2 1.8-3.1 14c-.2 1.1-1.7 1.5-2.3.5l-4.6-7.1 10-7.4Zm.5-4.1a2.2 2.2 0 1 0 0 4.4 2.2 2.2 0 0 0 0-4.4Z" fill="currentColor"/>
              <path d="M20 22v13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </span>
          <div>
            <span className="eyebrow">ТУРБИНА {index + 1}</span>
            <h2>{turbine.id === 'turbine-1' ? 'Первая турбина' : 'Вторая турбина'}</h2>
          </div>
        </div>
        <div className="chart-card__point-count"><strong>{points.length}</strong><span>часовых точек</span></div>
      </div>

      <div className="chart-legend"><span className="legend-line" />Прогноз нормализованной мощности</div>
      <figure className="chart-figure">
        <svg className="forecast-svg" viewBox={`0 0 ${CHART.width} ${CHART.height}`} role="img" aria-labelledby={`${gradientId}-title ${gradientId}-description`}>
          <title id={`${gradientId}-title`}>{`Прогноз нормализованной мощности: ${turbine.id}`}</title>
          <desc id={`${gradientId}-description`}>{`График от 0 до 1 для ${points.length} почасовых точек. Мощность и доступные погодные входы каждой точки показаны в подсказке.`}</desc>
          <defs>
            <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="currentColor" stopOpacity=".2" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
            </linearGradient>
          </defs>
          {Y_TICKS.map((tick) => {
            const tickY = y(tick);
            return (
              <g key={tick} className="chart-gridline">
                <line x1={CHART.left} x2={CHART.width - CHART.right} y1={tickY} y2={tickY} />
                <text x={CHART.left - 12} y={tickY + 4} textAnchor="end">{tick.toFixed(2)}</text>
              </g>
            );
          })}
          <path className="chart-area" d={areaPath} fill={`url(#${gradientId})`} />
          <path className="chart-line" d={linePath} fill="none" stroke="currentColor" />
          {points.map((point, pointIndex) => (
            <circle
              key={point.valid_time_utc}
              className="chart-point"
              cx={x(pointIndex)}
              cy={y(point.predicted_normalized_power)}
              r="2.5"
              fill="currentColor"
            >
              <title>{[
                formatUtc(point.valid_time_utc),
                `Нормализованная мощность: ${(point.predicted_normalized_power * 100).toFixed(1)}%`,
                Number.isFinite(point.forecast_wind_speed_ms) ? `Прогнозный ветер: ${point.forecast_wind_speed_ms.toFixed(2)} м/с` : null,
                Number.isFinite(point.forecast_temperature_c) ? `Прогнозная температура: ${point.forecast_temperature_c.toFixed(1)} °C` : null,
              ].filter(Boolean).join('\n')}</title>
            </circle>
          ))}
          {tickIndices.map((pointIndex, tickIndex) => (
            <g key={pointIndex} className="chart-x-tick">
              <line x1={x(pointIndex)} x2={x(pointIndex)} y1={CHART.top + plotHeight} y2={CHART.top + plotHeight + 5} />
              <text x={x(pointIndex)} y={CHART.height - 22} textAnchor={tickIndex === 0 ? 'start' : tickIndex === tickIndices.length - 1 ? 'end' : 'middle'}>
                {tickIndex === 0 || tickIndex === tickIndices.length - 1 ? timeLabel(points[pointIndex].valid_time_utc, true) : timeLabel(points[pointIndex].valid_time_utc)}
              </text>
            </g>
          ))}
          <text className="chart-axis-caption" x={CHART.left} y={CHART.height - 4}>Время выпуска — UTC</text>
        </svg>
        <figcaption className="sr-only">Нормализованная мощность от 0 до 1. Наведите указатель на точки для просмотра значений.</figcaption>
      </figure>
      {(meanWind !== null || meanTemperature !== null) && (
        <p className="chart-input-summary">
          Средние погодные входы за горизонт:
          {meanWind !== null && ` ветер ${meanWind.toFixed(2)} м/с`}
          {meanWind !== null && meanTemperature !== null && ' ·'}
          {meanTemperature !== null && ` температура ${meanTemperature.toFixed(1)} °C`}
          {' · значения каждого часа — в подсказке'}
        </p>
      )}
      <div className="chart-card__footnote"><span>0</span><span>Нормализованная мощность</span><span>1</span></div>
      {turbine.operator_insight && <OperatorInsight insight={turbine.operator_insight} />}
    </article>
  );
}

function OperatorInsight({ insight }) {
  const windows = insight.low_generation_windows ?? [];
  return (
    <aside className="operator-insight" aria-label="Сценарный анализ для проверки оператором">
      <div className="operator-insight__heading">
        <div><span className="eyebrow">НЕ АВТОМАТИЧЕСКОЕ РЕШЕНИЕ</span><strong>Окна для проверки оператором</strong></div>
        <span className={insight.operator_review_recommended ? 'operator-insight__status is-review' : 'operator-insight__status'}>
          {insight.operator_review_recommended ? 'НУЖЕН ПРОСМОТР' : 'ОКОН НЕ НАЙДЕНО'}
        </span>
      </div>
      <div className="operator-insight__metrics">
        <div><span>Часов ниже сценарного порога</span><strong>{insight.low_generation_hours ?? '—'} ч</strong></div>
        <div><span>Эквивалент полной нагрузки</span><strong>{Number.isFinite(insight.forecast_full_load_hours_equivalent) ? `${insight.forecast_full_load_hours_equivalent.toFixed(2)} ч` : '—'}</strong></div>
        <div><span>Порог · минимальное окно</span><strong>{Number.isFinite(insight.threshold_normalized_power) ? `${insight.threshold_normalized_power.toFixed(2)} · ${insight.minimum_window_hours ?? '—'} ч` : '—'}</strong></div>
      </div>
      {windows.length > 0 ? (
        <ul className="operator-insight__windows">
          {windows.map((window) => (
            <li key={`${window.start_time_utc}-${window.end_time_utc}`}>
              <span>UTC: {formatUtc(window.start_time_utc)} — {formatUtc(window.end_time_utc)}</span>
              <strong>{window.hours} ч</strong>
            </li>
          ))}
        </ul>
      ) : <p className="operator-insight__empty">Нет окон длительностью не меньше заданного минимума.</p>}
      <p className="operator-insight__note">{insight.note ?? 'Показатель носит информационный характер.'} В длительность включены обе крайние почасовые точки. Эквивалентные часы не являются MWh; порог — параметр сценария, а не правило энергосети.</p>
    </aside>
  );
}
