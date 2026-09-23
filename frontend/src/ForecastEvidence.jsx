import { formatUtc } from './forecast.js';

export default function ForecastEvidence({ forecast, loading, isStale }) {
  const isApi = forecast.origin === 'api';
  const buffer = forecast.weather.availability_buffer_hours;
  const hasBuffer = Number.isFinite(buffer) && buffer >= 0;
  const bufferRespected = hasBuffer && Date.parse(forecast.weather.run_time_utc) + buffer * 3600000 <= Date.parse(forecast.issue_time_utc);
  return (
    <section className="evidence-panel" aria-labelledby="evidence-title" aria-busy={loading}>
      <div className="evidence-panel__heading">
        <h2 id="evidence-title">Как получен прогноз</h2>
        <span>{loading ? 'Расчёт выполняется' : isApi ? 'По данным ответа API' : 'Демонстрационный пример'}</span>
      </div>
      <p className="evidence-panel__intro">{loading
        ? 'Получаем прогноз и проверяем ответ. Ниже остаются сведения о предыдущем результате.'
        : isStale ? 'Показан предыдущий результат. Пересчитайте прогноз для выбранных параметров.'
          : 'Источник погоды, история обучения и результат для выбранного выпуска.'}</p>
      {!isApi ? <p className="evidence-panel__intro">В демо значения синтетические. Выберите Backend API и пересчитайте прогноз, чтобы увидеть сведения о модели и данных.</p> : <>
        <ol className="evidence-steps">
          <li><span className="evidence-steps__number">1</span><div><h3>Архивная погода</h3>
            <p>{forecast.weather.source} · {forecast.weather.model}</p>
            <p>Запуск: <strong>{formatUtc(forecast.weather.run_time_utc)} UTC</strong></p>
            <p>{bufferRespected ? `Запуск предшествует выпуску минимум на ${buffer} ч — принятый запас доступности.` : 'Запас доступности погодного запуска не подтверждён метаданными ответа.'}</p>
          </div></li>
          <li><span className="evidence-steps__number">2</span><div><h3>История для модели</h3>
            {forecast.turbines.map((turbine, index) => <p key={turbine.id}>Турбина {index + 1}: последняя запись <strong>{formatUtc(turbine.latest_training_time_utc)} UTC</strong>.
              {' '}Сценарий времени: <strong>{turbine.source_timezone_assumption ?? 'не указан'}</strong>.
              {Number.isInteger(turbine.training_rows) && <> Обучающих строк: {turbine.training_rows.toLocaleString('ru-RU')}.</>}
            </p>)}
          </div></li>
          <li><span className="evidence-steps__number">3</span><div><h3>Почасовой прогноз</h3>
            <p>Две турбины × {forecast.horizon_hours} ч. Нормализованная мощность от 0 до 1.</p>
            <p>Выпуск: <strong>{formatUtc(forecast.issue_time_utc)} UTC</strong>. Структура, непрерывность часов и диапазон мощности проверены интерфейсом.</p>
          </div></li>
          <li><span className="evidence-steps__number">4</span><div><h3>Проверка оператором</h3>
            <p>Окна низкой выработки — повод проверить ситуацию. При следующем выпуске сравниваются общие часы прогноза.</p>
            <p>Автоматических команд на управление турбинами нет.</p>
          </div></li>
        </ol>
        <p className="evidence-panel__footnote">Это описание по метаданным результата, а не журнал выполнения в реальном времени. Часовой пояс CSV и запас доступности погоды — допущения; фактическое время публикации погоды не проверено.</p>
      </>}
    </section>
  );
}
