import { useMemo, useRef, useState } from 'react';
import ForecastChart from './ForecastChart.jsx';
import ForecastEvidence from './ForecastEvidence.jsx';
import { downloadText, forecastCsv, forecastFilename, forecastPassport } from './export.js';
import { localizeMessage } from './messages.js';
import { JANUARY_DIAGNOSTIC } from './diagnostics.js';
import {
  compareForecastRuns,
  createDemoForecast,
  DEFAULT_ISSUE,
  FIRST_ISSUE,
  formatUtc,
  issueValueToUtc,
  LAST_ISSUE,
  shiftIssue,
  validateForecastResponse,
} from './forecast.js';
import './App.css';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
const DAILY_ISSUE_COUNT = 29;

function Icon({ name, size = 18 }) {
  const shared = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true };
  if (name === 'wind') return <svg {...shared}><path d="M3 8h12.5a2.5 2.5 0 1 0-2.3-3.5M2 12h17a2.5 2.5 0 1 1-2.3 3.5M4 16h7.5a2.5 2.5 0 1 1-2.2 3.5" /></svg>;
  if (name === 'clock') return <svg {...shared}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.2 2" /></svg>;
  if (name === 'cloud') return <svg {...shared}><path d="M7.5 18h9.2a4.3 4.3 0 0 0 .4-8.6A5.8 5.8 0 0 0 6 10.7 3.7 3.7 0 0 0 7.5 18Z" /></svg>;
  if (name === 'refresh') return <svg {...shared}><path d="M20 7v5h-5M4 17v-5h5" /><path d="M5.5 9a7 7 0 0 1 11.7-2L20 12M4 12l2.8 5a7 7 0 0 0 11.7-2" /></svg>;
  if (name === 'arrow') return <svg {...shared}><path d="M5 12h14M13 6l6 6-6 6" /></svg>;
  if (name === 'shield') return <svg {...shared}><path d="M12 3 5 6v5c0 4.6 2.9 8 7 10 4.1-2 7-5.4 7-10V6l-7-3Z" /><path d="m9 12 2 2 4-4" /></svg>;
  if (name === 'alert') return <svg {...shared}><path d="M12 3 2.8 19h18.4L12 3Z" /><path d="M12 9v4m0 3h.01" /></svg>;
  return null;
}

function getIssuePosition(value) {
  const selectedDay = Date.parse(`${value.slice(0, 10)}T00:00:00Z`);
  const firstDay = Date.parse('2026-01-31T00:00:00Z');
  return Math.max(0, Math.min(DAILY_ISSUE_COUNT - 1, Math.floor((selectedDay - firstDay) / 86400000)));
}

function getErrorMessage(error) {
  if (error instanceof TypeError && /fetch/i.test(error.message)) {
    return `Не удалось связаться с API. Проверьте, что backend запущен${API_BASE_URL ? ` по адресу ${API_BASE_URL}` : ' на http://127.0.0.1:8000'} и доступен маршрут POST /api/forecast/run.`;
  }
  return error?.message || 'Не удалось получить прогноз. Попробуйте ещё раз.';
}

function formatPowerChange(value) {
  const sign = value > 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(1)} п.п.`;
}

function formatWindChange(value) {
  if (!Number.isFinite(value)) return 'погодные входы отсутствуют в ответе API';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)} м/с`;
}

async function requestForecast(issueTimeUtc, horizonHours) {
  const response = await fetch(`${API_BASE_URL}/api/forecast/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ issue_time_utc: issueTimeUtc, horizon_hours: horizonHours }),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail ?? payload?.error ?? payload?.message;
    throw new Error(detail ? `Ошибка API (${response.status}): ${detail}` : `Backend вернул ошибку ${response.status}.`);
  }
  return validateForecastResponse(payload, issueTimeUtc, horizonHours);
}

function App() {
  const [mode, setMode] = useState('demo');
  const [issueValue, setIssueValue] = useState(DEFAULT_ISSUE);
  const [horizon, setHorizon] = useState(48);
  const [forecast, setForecast] = useState(() => createDemoForecast(issueValueToUtc(DEFAULT_ISSUE), 48));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [comparison, setComparison] = useState(null);
  const [message, setMessage] = useState('');
  const [exportMessage, setExportMessage] = useState('');
  const [preparedExport, setPreparedExport] = useState(null);
  const [explanation, setExplanation] = useState(null);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [explanationError, setExplanationError] = useState('');
  const explanationRequest = useRef(0);

  const issueUtc = useMemo(() => {
    try { return issueValueToUtc(issueValue); } catch { return ''; }
  }, [issueValue]);
  const isStale = !issueUtc || Date.parse(forecast.issue_time_utc) !== Date.parse(issueUtc) || forecast.horizon_hours !== horizon || forecast.origin !== mode;
  const issueIndex = getIssuePosition(issueValue);
  const isScheduledIssue = issueValue.slice(11, 16) === '12:00';
  const issueNumber = String(issueIndex + 1).padStart(2, '0');
  const isLastDay = issueValue.slice(0, 10) === '2026-02-28';
  const showingDemoData = forecast.origin === 'demo';
  const exportDisabled = loading || isStale || showingDemoData || Boolean(error);
  const explanationDisabled = exportDisabled || explanationLoading;
  const visibleExplanation = !explanationDisabled && explanation?.issueTime === forecast.issue_time_utc && explanation?.horizon === horizon ? explanation.result : null;

  function clearExplanation() {
    explanationRequest.current += 1;
    setExplanation(null);
    setExplanationLoading(false);
    setExplanationError('');
  }

  async function requestExplanation() {
    if (explanationDisabled) return;
    const requestId = ++explanationRequest.current;
    const currentIssue = forecast.issue_time_utc;
    const currentHorizon = horizon;
    setExplanation(null);
    setExplanationLoading(true);
    setExplanationError('');
    try {
      const previousIssue = comparison?.current_issue_time_utc === currentIssue
        ? comparison.previous_issue_time_utc : null;
      const response = await fetch(`${API_BASE_URL}/api/forecast/explain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ issue_time_utc: currentIssue, horizon_hours: currentHorizon,
          ...(previousIssue ? { previous_issue_time_utc: previousIssue } : {}) }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail || `Сервис объяснений ответил с ошибкой ${response.status}.`);
      if (!['ai', 'local'].includes(payload?.mode) || typeof payload?.text !== 'string'
        || payload?.evidence?.issue_time_utc !== currentIssue
        || payload?.evidence?.horizon_hours !== currentHorizon) {
        throw new Error('Ответ объясняющего агента не соответствует текущему выпуску.');
      }
      if (requestId === explanationRequest.current) {
        setExplanation({ issueTime: currentIssue, horizon: currentHorizon, result: payload });
      }
    } catch (explainError) {
      if (requestId === explanationRequest.current) setExplanationError(getErrorMessage(explainError));
    } finally {
      if (requestId === explanationRequest.current) setExplanationLoading(false);
    }
  }

  function exportForecast(extension) {
    if (exportDisabled) return;
    try {
      const content = extension === 'csv' ? forecastCsv(forecast) : forecastPassport(forecast, comparison);
      const filename = forecastFilename(forecast, extension);
      setPreparedExport({ content, filename });
      downloadText(content, filename, extension === 'csv' ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8');
      setExportMessage(`Выгрузка ${extension.toUpperCase()} подготовлена для выпуска ${formatUtc(forecast.issue_time_utc)} UTC. Сохранение зависит от настроек браузера.`);
    } catch (exportError) {
      setExportMessage(`Не удалось подготовить выгрузку: ${exportError.message}`);
    }
  }

  async function runForecast(overrides = {}) {
    clearExplanation();
    const selectedValue = overrides.issueValue ?? issueValue;
    const selectedHorizon = overrides.horizon ?? horizon;
    const selectedMode = overrides.mode ?? mode;
    let requestedIssue;
    try {
      requestedIssue = issueValueToUtc(selectedValue);
    } catch (runError) {
      setError(getErrorMessage(runError));
      setMessage('');
      return;
    }

    setLoading(true);
    setExportMessage('');
    setPreparedExport(null);
    setError('');
    setMessage('');
    setComparison(null);
    try {
      let nextForecast;
      if (selectedMode === 'demo') {
        await new Promise((resolve) => window.setTimeout(resolve, 280));
        nextForecast = createDemoForecast(requestedIssue, selectedHorizon);
      } else {
        nextForecast = await requestForecast(requestedIssue, selectedHorizon);
      }
      setComparison(compareForecastRuns(forecast, nextForecast));
      setForecast(nextForecast);
      setMessage(selectedMode === 'demo'
        ? 'Демо-пример перестроен. Значения по-прежнему синтетические.'
        : 'Прогноз получен; структура и ограничения контракта проверены.');
    } catch (runError) {
      setError(getErrorMessage(runError));
    } finally {
      setLoading(false);
    }
  }

  function stepIssue(days) {
    const nextValue = shiftIssue(issueValue, days);
    if (nextValue < FIRST_ISSUE || nextValue > LAST_ISSUE) return;
    setIssueValue(nextValue);
    runForecast({ issueValue: nextValue });
  }

  const progress = ((issueIndex + 1) / DAILY_ISSUE_COUNT) * 100;
  const pointsCount = forecast.turbines[0]?.hourly.length ?? 0;

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#main" aria-label="HackAlem Wind Forecast — главная">
          <span className="brand__symbol"><Icon name="wind" size={21} /></span>
          <span className="brand__text"><strong>HACKALEM</strong><small>WIND FORECAST</small></span>
        </a>
        <div className="topbar__right">
          <span className="workspace-label"><span className="live-dot" />РАБОЧАЯ СРЕДА</span>
          <span className="topbar__divider" />
          <span className="topbar__team">Команда Жубанова</span>
          <span className="avatar" aria-label="Команда">Ж</span>
        </div>
      </header>

      <main id="main" className="main-content">
        <div className="page-heading">
          <div>
            <div className="breadcrumb"><span>HackAlem AI</span><span className="breadcrumb__slash">/</span><span>Энергетика</span></div>
            <h1>Прогноз ветропарка</h1>
            <p className="page-subtitle">Почасовая нормализованная мощность · две турбины · выпуск по UTC</p>
          </div>
          <span className={`environment-badge ${showingDemoData ? 'environment-badge--demo' : 'environment-badge--api'}`}>
            <span className="environment-badge__dot" />{showingDemoData ? 'ДЕМО-ДАННЫЕ' : 'BACKEND API'}
          </span>
        </div>

        {showingDemoData && (
          <section className="demo-banner" aria-label="Важное предупреждение о данных">
            <span className="demo-banner__icon"><Icon name="alert" size={19} /></span>
            <div><strong>Демонстрационный режим — не реальный прогноз</strong><p>Графики построены из синтетических тестовых значений. Подключите backend, чтобы показать расчёт модели и архивную погоду.</p></div>
            <span className="demo-banner__tag">ТЕСТОВЫЕ ДАННЫЕ</span>
          </section>
        )}

        <section className="control-panel" aria-labelledby="controls-title">
          <div className="control-panel__top">
            <div className="section-label"><span className="section-label__number">01</span><h2 id="controls-title">Параметры выпуска</h2></div>
            <div className="mode-control" role="group" aria-label="Источник прогноза">
              <button type="button" className={mode === 'demo' ? 'mode-button is-selected' : 'mode-button'} aria-pressed={mode === 'demo'} onClick={() => { clearExplanation(); setMode('demo'); setError(''); setMessage(''); }} disabled={loading}>Демо</button>
              <button type="button" className={mode === 'api' ? 'mode-button is-selected' : 'mode-button'} aria-pressed={mode === 'api'} onClick={() => { clearExplanation(); setMode('api'); setError(''); setMessage(''); }} disabled={loading}>Backend API</button>
            </div>
          </div>
          <div className="control-panel__fields">
            <label className="field field--issue">
              <span className="field__label"><Icon name="clock" size={15} />Время выпуска <span className="field__utc">UTC</span></span>
              <input type="datetime-local" value={issueValue} min={FIRST_ISSUE} max={LAST_ISSUE} step="3600" onChange={(event) => { clearExplanation(); setIssueValue(event.target.value); setMessage(''); }} disabled={loading} aria-label="Выберите дату и время выпуска по UTC" />
            </label>
            <div className="field field--horizon">
              <span className="field__label"><Icon name="wind" size={15} />Горизонт прогноза</span>
              <div className="horizon-switch" role="group" aria-label="Горизонт прогноза в часах">
                {[24, 48].map((hours) => <button key={hours} type="button" className={horizon === hours ? 'horizon-switch__button is-active' : 'horizon-switch__button'} aria-pressed={horizon === hours} onClick={() => { clearExplanation(); setHorizon(hours); setMessage(''); }} disabled={loading}>{hours} ч</button>)}
              </div>
            </div>
            <button className="run-button" type="button" onClick={() => runForecast()} disabled={loading || !issueUtc}>
              {loading ? <span className="spinner" aria-hidden="true" /> : <Icon name="refresh" size={17} />}
              <span>{loading ? 'Считаем…' : 'Пересчитать прогноз'}</span>
              {!loading && <Icon name="arrow" size={16} />}
            </button>
          </div>
          {isStale && !loading && <p className="control-hint" role="status">Параметры изменены. Нажмите «Пересчитать прогноз», чтобы обновить графики.</p>}
        </section>

        {error && (
          <div className="alert alert--error" role="alert">
            <span className="alert__icon"><Icon name="alert" size={19} /></span>
            <div><strong>Не удалось обновить прогноз</strong><p>{error}</p>{mode === 'api' && <small>Для локальной разработки настройте адрес API в frontend/.env или используйте proxy Vite.</small>}</div>
            <button type="button" className="alert__retry" onClick={() => runForecast()} disabled={loading}>Повторить</button>
          </div>
        )}
        {message && !error && <p className="sr-only" role="status">{message}</p>}

        <section className="forecast-section" aria-labelledby="forecast-title">
          <div className="forecast-section__heading">
            <div><div className="section-label"><span className="section-label__number">02</span><h2 id="forecast-title">Почасовой прогноз</h2></div><p className="section-description">Значения в диапазоне 0–1 · нормализованная активная мощность</p></div>
            <div className="forecast-section__meta"><span className="coverage-pill"><span className="coverage-pill__dot" />{pointsCount} / {forecast.horizon_hours} точек</span><span className="unit-pill">БЕЗ MW / MWh</span></div>
          </div>

          <div className="export-panel">
            <div><strong>Сохранить текущий выпуск</strong><p>CSV — значения для двух турбин. Паспорт JSON — прогноз, источники, допущения и доступное сравнение выпусков.</p></div>
            <div className="export-panel__actions">
              <button type="button" className="step-button" onClick={() => exportForecast('csv')} disabled={exportDisabled}>Скачать CSV</button>
              <button type="button" className="step-button" onClick={() => exportForecast('json')} disabled={exportDisabled}>Паспорт JSON</button>
            </div>
            {exportDisabled && <p className="export-panel__hint">{loading ? 'Выгрузка будет доступна после расчёта.' : showingDemoData ? 'Для выгрузки получите прогноз из Backend API.' : 'Пересчитайте прогноз: выгрузка доступна для актуального успешного результата.'}</p>}
            {exportMessage && <p className="export-panel__hint" role="status">{exportMessage}</p>}
            {preparedExport && !exportDisabled && <details className="export-preview">
              <summary>Показать содержимое файла</summary>
              <p>Если браузер не сохранил файл, выделите содержимое поля и скопируйте его в файл с указанным именем.</p>
              <label><span>{preparedExport.filename}</span><textarea readOnly aria-label="Содержимое подготовленного файла" value={preparedExport.content} spellCheck={false} /></label>
            </details>}
          </div>

          <div className={`chart-grid ${loading ? 'chart-grid--loading' : ''}`} aria-busy={loading}>
            {forecast.turbines.map((turbine, index) => <ForecastChart key={turbine.id} turbine={turbine} index={index} />)}
          </div>
        </section>

        <section className="release-section" aria-labelledby="release-title">
          <div className="release-section__header">
            <div><div className="section-label"><span className="section-label__number">03</span><h2 id="release-title">Ежедневные выпуски</h2></div><p className="section-description">Сценарий: 31 января — 28 февраля 2026 · выбранный час выпуска — UTC</p></div>
            <div className="release-counter"><strong>{issueNumber}</strong><span>/ {DAILY_ISSUE_COUNT}</span><small>день выпуска</small></div>
          </div>
          <div className="release-track" aria-label={`Выбран выпуск ${issueNumber} из ${DAILY_ISSUE_COUNT}`}>
            <div className="release-track__fill" style={{ width: `${progress}%` }} />
            {Array.from({ length: DAILY_ISSUE_COUNT }, (_, index) => <span key={index} className={`release-track__stop ${index === issueIndex ? 'is-current' : ''}`} aria-hidden="true" />)}
          </div>
          <div className="release-controls">
            <span className="release-date">{formatUtc(`${issueValue.slice(0, 10)}T00:00:00Z`, { dateOnly: true, day: 'numeric', month: 'long' })}</span>
            <div className="release-controls__buttons">
              <button className="step-button" type="button" onClick={() => stepIssue(-1)} disabled={loading || issueValue.slice(0, 10) === '2026-01-31'} aria-label="Предыдущий ежедневный выпуск"><span aria-hidden="true">←</span> Предыдущий</button>
              <button className="step-button step-button--next" type="button" onClick={() => stepIssue(1)} disabled={loading || isLastDay} aria-label="Следующий ежедневный выпуск">Следующий <span aria-hidden="true">→</span></button>
            </div>
          </div>
          {!isScheduledIssue && <p className="release-note">Выбрано нестандартное время. В календаре ежедневных выпусков используется 12:00 UTC.</p>}
        </section>

        <ForecastEvidence forecast={forecast} loading={loading} isStale={isStale} />

        <section className="explanation-panel" aria-labelledby="explanation-title">
          <div className="explanation-panel__heading">
            <div><div className="section-label"><span className="section-label__number">ИИ</span><h2 id="explanation-title">Подробное объяснение прогноза</h2></div>
              <p>Агент собирает факты о погоде, модели, обеих турбинах и пересмотре выпуска. Числа прогноза он не меняет.</p></div>
            <button type="button" className="step-button explanation-panel__button" onClick={requestExplanation} disabled={explanationDisabled}>
              {explanationLoading ? 'Объясняем…' : 'Объяснить этот выпуск'}
            </button>
          </div>
          {showingDemoData && <p className="explanation-panel__hint">Для объяснения по данным организаторов выберите Backend API и рассчитайте выпуск.</p>}
          {isStale && !showingDemoData && <p className="explanation-panel__hint">Сначала обновите прогноз для выбранных параметров.</p>}
          {explanationError && <p className="explanation-panel__error" role="alert">{explanationError}</p>}
          {visibleExplanation && <div className="explanation-panel__result" role="status">
            <strong>{visibleExplanation.mode === 'ai' ? 'Ответ NVIDIA AI' : 'Локальное объяснение'}</strong>
            <p className="explanation-panel__text">{visibleExplanation.text}</p>
            <small>{visibleExplanation.notice}</small>
            <small>Часовой пояс CSV неизвестен. Время публикации погоды не подтверждено. Точность за февраль не измерена.</small>
          </div>}
        </section>

        <section className="provenance-section" aria-labelledby="provenance-title">
          <div className="section-label provenance-section__title"><span className="section-label__number">04</span><h2 id="provenance-title">Происхождение и ограничения</h2></div>
          <div className="provenance-grid">
            <article className="provenance-card">
              <div className="provenance-card__icon provenance-card__icon--weather"><Icon name="cloud" size={19} /></div>
              <div className="provenance-card__body"><span className="eyebrow">ИСТОЧНИК ПОГОДЫ</span><strong>{forecast.weather.source}</strong><span>Модель: {forecast.weather.model}</span><span>ID запуска: {forecast.run_id ?? '—'}</span></div>
              <div className="provenance-card__time"><span>Время запуска модели</span><strong>{formatUtc(forecast.weather.run_time_utc)}</strong></div>
            </article>
            <article className="provenance-card">
              <div className="provenance-card__icon provenance-card__icon--cutoff"><Icon name="shield" size={19} /></div>
              <div className="provenance-card__body"><span className="eyebrow">ОТСЕЧЕНИЕ ОБУЧЕНИЯ</span><strong>{formatUtc(forecast.training_cutoff_utc)}</strong><span>Данные не позже выбранного выпуска</span></div>
              <div className="provenance-card__time"><span>Время выпуска</span><strong>{formatUtc(forecast.issue_time_utc)}</strong></div>
            </article>
          </div>

          {comparison !== null && (
            <section className="comparison-panel" aria-labelledby="comparison-title">
              <div className="comparison-panel__heading">
                <div><div className="section-label"><span className="section-label__number">Δ</span><h3 id="comparison-title">Пересмотр между выпусками</h3></div>
                  <p>Сравнение {formatUtc(comparison.previous_issue_time_utc)} → {formatUtc(comparison.current_issue_time_utc)} по совпадающим часам прогноза.</p>
                </div>
              </div>
              {comparison.turbines.length > 0 ? (
                <div className="comparison-grid">
                  {comparison.turbines.map((change) => (
                    <article className="comparison-card" key={change.turbine_id}>
                      <div className="comparison-card__title"><strong>{change.turbine_id === 'turbine-1' ? 'Первая турбина' : 'Вторая турбина'}</strong><span>{change.overlapping_hours} общих часов</span></div>
                      <div className="comparison-card__metrics">
                        <div><span>Среднее изменение</span><strong>{formatPowerChange(change.mean_change_normalized_power)}</strong></div>
                        <div><span>Средний размер пересмотра</span><strong>{formatPowerChange(change.mean_absolute_change_normalized_power)}</strong></div>
                        <div><span>Среднее изменение ветра</span><strong>{formatWindChange(change.mean_forecast_wind_change_ms)}</strong></div>
                      </div>
                      {change.largest_revision && <div className="comparison-card__largest">
                        <span>Самый большой пересмотр · {formatUtc(change.largest_revision.valid_time_utc)} UTC</span>
                        <strong>{(change.largest_revision.previous_normalized_power * 100).toFixed(1)}% → {(change.largest_revision.current_normalized_power * 100).toFixed(1)}% ({formatPowerChange(change.largest_revision.current_normalized_power - change.largest_revision.previous_normalized_power)})</strong>
                        <small>Ветер для этого часа: {Number.isFinite(change.largest_revision.previous_forecast_wind_speed_ms) && Number.isFinite(change.largest_revision.current_forecast_wind_speed_ms) ? `${change.largest_revision.previous_forecast_wind_speed_ms.toFixed(2)} → ${change.largest_revision.current_forecast_wind_speed_ms.toFixed(2)} м/с` : 'нет данных в контрактном ответе'}</small>
                      </div>}
                    </article>
                  ))}
                </div>
              ) : <p className="comparison-panel__empty">Между выбранными выпусками нет общих будущих часов. Для сравнения соседних дней нужен горизонт 48 часов.</p>}
              <p className="comparison-panel__footnote">Изменение погодного входа — наблюдаемое свидетельство пересмотра, но не доказательство причины. Это не оценка точности.</p>
            </section>
          )}

          {(forecast.analysis.length > 0 || forecast.warnings.length > 0) && (
            <div className="notes-panel">
              {forecast.analysis.map((item, index) => <p key={`analysis-${index}`} className="notes-panel__analysis"><span>АНАЛИЗ</span>{localizeMessage(item)}</p>)}
              {forecast.warnings.map((item, index) => <p key={`warning-${index}`} className="notes-panel__warning"><span><Icon name="alert" size={14} />ПРИМЕЧАНИЕ</span>{localizeMessage(item)}</p>)}
            </div>
          )}
        </section>

        <section className="diagnostic-section" aria-labelledby="diagnostic-title">
          <div className="diagnostic-section__heading">
            <div><div className="section-label"><span className="section-label__number">05</span><h2 id="diagnostic-title">Январская историческая проверка</h2></div><p>Отдельный диагностический отчёт модели · не результат синтетических графиков выше</p></div>
            <span className="diagnostic-badge">СЦЕНАРНЫЕ ДАННЫЕ</span>
          </div>
          <p className="diagnostic-summary"><strong>{JANUARY_DIAGNOSTIC.issueDays.length} выпусков · {JANUARY_DIAGNOSTIC.issueDays.length * 2 * JANUARY_DIAGNOSTIC.horizonHours} часов двух турбин · горизонт {JANUARY_DIAGNOSTIC.horizonHours} ч</strong><span>Даты: {JANUARY_DIAGNOSTIC.issueDays.map((day) => `${day} янв.`).join(', ')}. Модель сравнивалась с простым прогнозом persistence по последним 6 часам.</span></p>
          <div className="diagnostic-table-wrap">
            <table className="diagnostic-table">
              <thead><tr><th scope="col">Трактовка времени CSV</th><th scope="col">Модель · MAE</th><th scope="col">Persistence · MAE</th></tr></thead>
              <tbody>{JANUARY_DIAGNOSTIC.scenarios.map((scenario) => (
                <tr key={scenario.sourceTimezone}><th scope="row">{scenario.sourceTimezone}</th><td>{scenario.modelMae.toFixed(3)}</td><td>{scenario.persistenceMae.toFixed(3)}</td></tr>
              ))}</tbody>
            </table>
          </div>
          <p className="diagnostic-caveat">MAE — в нормализованной мощности. Часовой пояс CSV организатором не задан: обе строки — допущения, нельзя выбирать лучшую как официальный результат. Это исследовательская январская проверка, не независимый benchmark; февральских фактических данных нет. Источник: docs/model-validation.md, широкая проверка от {JANUARY_DIAGNOSTIC.reportDate}.</p>
        </section>

        <footer className="page-footer"><span>HACKALEM AI <span className="footer-dot">·</span> WIND FARM FORECAST</span><span>Почасовые значения нормализованной мощности [0, 1]</span><span>CSV-серия заканчивается 31 января; февральская точность пока не измерена</span></footer>
      </main>
    </div>
  );
}

export default App;
