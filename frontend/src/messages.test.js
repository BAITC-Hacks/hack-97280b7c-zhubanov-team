import assert from 'node:assert/strict';
import test from 'node:test';
import { localizeMessage } from './messages.js';

test('preserves exact numeric precision when translating mean normalized power', () => {
  assert.equal(
    localizeMessage('Mean forecast normalized power: turbine-1 0.003; turbine-2 1.000.'),
    'Средняя прогнозная нормализованная мощность: турбина 1 — 0.003; турбина 2 — 1.000.',
  );
});

test('keeps timezone scenarios explicit, including the scenario uncertainty', () => {
  for (const zone of ['UTC', 'Asia/Almaty', 'UTC+05:00']) {
    const translated = localizeMessage(`Organizer CSV has no declared timezone; interpreted as ${zone} for this scenario.`);
    assert.ok(translated.includes(zone));
    assert.match(translated, /не указан/);
    assert.match(translated, /допущение/);
  }
});

test('weather wording preserves the 12-hour buffer and unverified publication', () => {
  const translated = localizeMessage('Archived weather run selected with a 12-hour availability buffer; actual publication time was not verified.');
  assert.match(translated, /буфером доступности 12 часов/);
  assert.match(translated, /допущение/);
  assert.match(translated, /фактическое время публикации не проверено/);
});

test('legacy weather wording remains localized with the uncertainty explicit', () => {
  const translated = localizeMessage('Predictions use an archived weather run available before the issue time.');
  assert.match(translated, /буферу/);
  assert.match(translated, /допущение/);
  assert.match(translated, /фактическое время публикации не проверено/);
});

test('known warnings retain capacity and February evaluation limitations', () => {
  assert.match(localizeMessage('Measured wind-sensor height and rated capacities are unknown; power is normalized, not MW.'), /неизвестны/);
  assert.match(localizeMessage('February actual power was not supplied; no February error metric is available.'), /оценить ошибку прогноза за февраль невозможно/);
});

test('operator note preserves the advisory boundary and no-window result', () => {
  assert.match(localizeMessage('Review the flagged low-generation window; this is advisory, not an automatic dispatch action.'), /автоматическая команда на управление не формируется/);
  assert.match(localizeMessage('No extended low-generation window under this scenario threshold.'), /не найдено/);
});

test('unknown text, extended warnings and already Russian messages survive unchanged', () => {
  for (const text of [
    'Unexpected weather gap: 17 hours in Asia/Almaty.',
    'Organizer CSV has no declared timezone; interpreted as UTC for this scenario. Additional warning: incomplete data.',
    'Mean forecast normalized power: turbine-1 0.003; turbine-2 1.000. Model changed.',
    'Данные неполные: 12 строк.',
    '',
    null,
  ]) assert.equal(localizeMessage(text), text);
});
