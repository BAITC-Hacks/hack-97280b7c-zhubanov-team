// Translate only recognized messages; new backend warnings must remain visible.
const MESSAGES = new Map([
  ['Predictions use an archived weather run available before the issue time.',
    'Использован архивный запуск погодной модели, выбранный по заданному временному буферу до выпуска прогноза. Это допущение о доступности: фактическое время публикации не проверено.'],
  ['A per-turbine bias correction was fitted on Jan 20 and 23 archived forecast issues.',
    'Для каждой турбины поправка смещения обучена на архивных выпусках погодного прогноза за 20 и 23 января.'],
  ['No weather-forecast bias correction was applied.',
    'Поправка смещения погодного прогноза не применялась.'],
  ['Low-generation windows and full-load-hour equivalents are advisory scenario outputs, not MW/MWh.',
    'Окна низкой выработки и эквивалентные часы полной нагрузки — информационные показатели сценария, а не МВт или МВт·ч.'],
  ['Measured wind-sensor height and rated capacities are unknown; power is normalized, not MW.',
    'Высота датчика ветра и номинальные мощности неизвестны. Мощность нормализована и не выражается в МВт.'],
  ['February actual power was not supplied; no February error metric is available.',
    'Фактическая мощность за февраль не предоставлена; оценить ошибку прогноза за февраль невозможно.'],
  ['Review the flagged low-generation window; this is advisory, not an automatic dispatch action.',
    'Проверьте отмеченное окно низкой выработки. Это рекомендация для оператора; автоматическая команда на управление не формируется.'],
  ['No extended low-generation window under this scenario threshold.',
    'При выбранном сценарном пороге продолжительных окон низкой выработки не найдено.'],
  ['Organizer CSV has no declared timezone; source time is interpreted as a configurable scenario.',
    'В CSV организаторов часовой пояс не указан; интерпретация времени задаётся как настраиваемый сценарий.'],
]);

export function localizeMessage(text) {
  if (typeof text !== 'string') return text;
  if (MESSAGES.has(text)) return MESSAGES.get(text);

  const mean = /^Mean forecast normalized power: turbine-1 (\d+(?:\.\d+)?); turbine-2 (\d+(?:\.\d+)?)\.$/.exec(text);
  if (mean) return `Средняя прогнозная нормализованная мощность: турбина 1 — ${mean[1]}; турбина 2 — ${mean[2]}.`;

  const scenario = /^Organizer CSV has no declared timezone; interpreted as (\S+) for this scenario\.$/.exec(text);
  if (scenario) return `В CSV организаторов часовой пояс не указан. В этом сценарии время интерпретируется как ${scenario[1]}; это допущение.`;

  return text;
}
