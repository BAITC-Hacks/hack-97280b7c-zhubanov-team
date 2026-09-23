// Auditable snapshot from docs/model-validation.md, broad January diagnostic.
// Keep the UI caveat visible and update these values only with that report.
export const JANUARY_DIAGNOSTIC = Object.freeze({
  reportDate: '2026-09-23',
  horizonHours: 48,
  issueDays: [1, 4, 7, 10, 13, 16, 19, 22, 25, 28],
  scenarios: [
    { sourceTimezone: 'Asia/Almaty', modelMae: 0.173, persistenceMae: 0.337 },
    { sourceTimezone: 'UTC', modelMae: 0.206, persistenceMae: 0.295 },
  ],
});
