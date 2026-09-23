import test from 'node:test';
import assert from 'node:assert/strict';
import { forecastCsv, forecastPassport, forecastFilename } from './export.js';

// Explicitly synthetic contract fixture; no organizer data is included.
function fixture(horizon = 48) {
  const issue = '2026-01-31T12:00:00Z';
  return {
    origin: 'api', horizon_hours: horizon, issue_time_utc: issue, training_cutoff_utc: issue,
    weather: { source: 'Synthetic test source', model: 'test-model', run_time_utc: '2026-01-31T00:00:00Z', availability_buffer_hours: 12 },
    turbines: ['turbine-1', 'turbine-2'].map((id) => ({
      id, training_cutoff_utc: issue, latest_training_time_utc: '2026-01-31T11:50:00Z',
      source_timezone_assumption: 'UTC', model: 'test-power-curve',
      hourly: Array.from({ length: horizon }, (_, index) => ({
        valid_time_utc: new Date(Date.parse(issue) + (index + 1) * 3600000).toISOString(),
        predicted_normalized_power: index / horizon, forecast_wind_speed_ms: 4.5, forecast_temperature_c: -6.5,
      })),
    })),
    analysis: ['Synthetic fixture only'], warnings: ['Timezone is an assumption'],
  };
}

test('CSV includes both turbines, continuous requested hours and original provenance for 24/48h', () => {
  for (const horizon of [24, 48]) {
    const csv = forecastCsv(fixture(horizon));
    assert.ok(csv.startsWith('\uFEFF'));
    const lines = csv.slice(1).trimEnd().split('\r\n');
    assert.equal(lines.length, horizon * 2 + 1);
    assert.match(lines[0], /availability_buffer_hours_assumed/);
    assert.match(lines[1], /"2026-01-31T13:00:00.000Z","turbine-1","0","4.5","-6.5"/);
    assert.match(lines.at(-1), /"turbine-2"/);
    assert.match(csv, /"Synthetic test source","test-model","2026-01-31T00:00:00Z","12"/);
    assert.match(csv, /"2026-01-31T11:50:00Z","UTC","test-power-curve"/);
  }
});

test('synthetic UI mode and invalid/temporally unsafe responses cannot be exported', () => {
  const mutations = [
    (f) => { f.origin = 'demo'; },
    (f) => { f.turbines.pop(); },
    (f) => { f.turbines[0].hourly[0].predicted_normalized_power = 1.5; },
    (f) => { f.turbines[0].hourly[0].valid_time_utc = f.issue_time_utc; },
    (f) => { f.weather.availability_buffer_hours = 24; },
    (f) => { f.turbines[0].latest_training_time_utc = '2026-02-01T00:00:00Z'; },
  ];
  for (const mutate of mutations) {
    const f = fixture(); mutate(f);
    assert.throws(() => forecastCsv(f));
    assert.throws(() => forecastPassport(f));
  }
});

test('CSV quotes delimiters and neutralizes spreadsheet formulas without changing numeric negatives', () => {
  const f = fixture();
  f.weather.source = '=HYPERLINK("https://example.test","x")';
  const csv = forecastCsv(f);
  assert.ok(csv.includes('"\'=HYPERLINK(""https://example.test"",""x"")"'));
  assert.ok(csv.includes('"-6.5"'));
  f.weather.source = 'source, with "quotes"\nsecond line';
  assert.ok(forecastCsv(f).includes('"source, with ""quotes""\nsecond line"'));
});

test('passport preserves warnings, data and only comparison belonging to this issue', () => {
  const f = fixture();
  const comparison = { previous_issue_time_utc: '2026-01-30T12:00:00Z', current_issue_time_utc: f.issue_time_utc, turbines: [] };
  const passport = JSON.parse(forecastPassport(f, comparison));
  assert.equal(passport.row_count, 96);
  assert.equal(passport.target_unit, 'dimensionless [0,1]');
  assert.deepEqual(passport.forecast.warnings, f.warnings);
  assert.deepEqual(passport.recalculation, comparison);
  assert.ok(passport.limitations.some((text) => text.includes('actual publication time was not verified')));
  assert.equal(JSON.parse(forecastPassport(f, { ...comparison, current_issue_time_utc: '2026-02-01T12:00:00Z' })).recalculation, null);
  assert.equal(forecastFilename(f, 'csv'), 'wind-forecast-20260131T120000000Z-48h.csv');
});

test('missing optional metadata stays empty rather than acquiring invented values', () => {
  const f = fixture();
  delete f.weather.availability_buffer_hours;
  delete f.turbines[0].source_timezone_assumption;
  delete f.turbines[0].latest_training_time_utc;
  const csv = forecastCsv(f);
  assert.match(csv, /"2026-01-31T00:00:00Z","","2026-01-31T12:00:00Z","","","test-power-curve"/);
});
