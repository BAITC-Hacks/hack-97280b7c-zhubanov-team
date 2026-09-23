# Shared API and analysis contract (v1)

The backend integrator owns changes to this file. Frontend and agent owners agree on a proposed change before changing code that depends on it.

## Request

`POST /api/analyze` with `multipart/form-data` fields `before_files` and `after_files`, each accepting one or more Word (`.docx`), text PDF (`.pdf`), or Excel (`.xlsx`) files. Also accept `.txt` because the supplied edition No. 9 is exposed as plain text. The first demo may use the two supplied editions. The API may process synchronously for the prototype. A file that cannot be read must return a clear error; do not silently omit it.

`GET /api/health` returns `{"status":"ok"}` after backend startup.

## Successful response

```json
{
  "status": "completed",
  "documents": [
    {"id": "before-1", "filename": "edition-8.docx", "side": "before"},
    {"id": "after-1", "filename": "edition-9.docx", "side": "after"}
  ],
  "units": [
    {
      "before_name": null,
      "after_name": "Департамент ИТ-аудита и анализа данных",
      "change": "created",
      "evidence": [{"document_id": "after-1", "section": "3.4", "excerpt": "Департамент ИТ-аудита и анализа данных (ДИТААД)."}]
    }
  ],
  "functions": [
    {
      "description": "Мониторинг выполнения корректирующих мероприятий",
      "before_unit": "БВА",
      "after_unit": "БВА",
      "change": "retained",
      "before_evidence": [{"document_id": "before-1", "section": "5.8.7", "excerpt": "осуществлять мониторинг выполнения Руководителями объекта аудита мероприятий"}],
      "after_evidence": [{"document_id": "after-1", "section": "5.7.7", "excerpt": "осуществлять мониторинг выполнения Руководителями объекта аудита мероприятий"}]
    }
  ],
  "findings": [],
  "conclusion": "Структура изменилась; пример не утверждает неподтвержденных потерь или конфликтов.",
  "limitations": ["Выводы требуют проверки ответственным сотрудником."],
  "review_required": true
}
```

This is a **contract illustration**, not a completed analysis of the documents. Real fields must be generated from supplied files. `units[].change` uses `retained | reorganized | created`; `functions[].change` uses `retained | transferred | possibly_lost | added`. Each `findings[]` item uses `type` (`possible_loss | possible_duplication | potential_conflict`), `summary`, `explanation`, `evidence[]`, and `review_required: true`. Every substantial finding needs at least one exact source excerpt. A possible loss should include the before source and an explicit statement that the function was not found after review of the supplied after set.

Each evidence item has `document_id`, `section`, `excerpt`, and optional `page` or `sheet`/`row` where the file format provides them. Never fabricate a PDF page for DOCX or Excel. Backend should verify that returned excerpts actually occur in the extracted source. If no findings are supported, return an empty array and explain that result in `conclusion`.

Invalid input returns an HTTP 4xx response with `{"error":{"code":"...","message":"..."}}`. Unexpected processing failures return an HTTP 5xx response with a readable message that does not expose secrets. API keys remain on the server.
