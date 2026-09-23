# Three-person task split

The official case is [here](https://docs.google.com/document/d/1m-r31DH6Q__9OcN4WiP453CE6drlTTQ8Px3xi3IiVHk/edit). Each person works in this same repository, their own clone and branch, and their own Codex session. Backend/API is the integrator. Start from current `main` after this plan is merged.

| Owner | Branch | First deliverable | Done when |
|---|---|---|---|
| 1. Frontend and design | `feat/frontend` | `frontend/`: before/after upload, analysis progress/error, unit/function tables, finding cards with clickable source excerpts, conclusion | UI can demonstrate the contract with mock JSON and switch to `/api/analyze` without changing field names |
| 2. Backend/API and integration | `feat/backend-api` | `backend/`: upload endpoint, DOCX/PDF/XLSX/TXT text extraction with document/section anchors, API wiring and error handling; root README and run instructions | Two source documents can be uploaded, parsed, passed to agent, and returned in the agreed JSON; endpoint rejects unreadable input |
| 3. Backend agent and comparison | `feat/agent-core` | `agent/`: identify units/functions, match renamed or renumbered clauses, flag possible loss/duplication/conflict with cited evidence, draft conclusion | No finding lacks exact source; clause 5.8.7 → 5.7.7 is recognized as retained; ambiguous cases remain flagged for review |

Backend/API owner owns `docs/api-contract.md` and common configuration. Agent owner exposes a Python function such as `analyze(before_documents, after_documents) -> AnalysisReport`; agree on the normalized document model in the first 15 minutes. Frontend uses the JSON in the contract as its temporary mock. Keep inputs private and secrets local.

## Copyable Codex tasks

**Frontend:** “Read `AGENTS.md`, `docs/case-map.md` and `docs/api-contract.md`. Confirm branch `feat/frontend`. Build only `frontend/`: a document upload view, unit/function comparison, possible findings with exact source excerpts, and conclusion. Use the contract example until backend is ready. Show empty, loading and error states. Do not edit backend, agent or API field names. Report how you ran the UI.”

**Backend/API:** “Read `AGENTS.md`, `docs/case-map.md` and `docs/api-contract.md`. Confirm branch `feat/backend-api`. Own `backend/`, application run configuration and README. Accept before/after DOCX/PDF/XLSX/TXT files, extract anchored text, call the agreed agent interface, and return the contract JSON. Handle unreadable input and verify evidence excerpts against source text. Integrate teammates’ PRs after checks.”

**Agent/comparison:** “Read `AGENTS.md`, `docs/case-map.md` and `docs/api-contract.md`. Confirm branch `feat/agent-core`. Own `agent/`. Compare units and functions semantically while retaining exact clause evidence. Detect possible loss and duplication and potential conflicts only when supported. Confirm that edition 8 clause 5.8.7 and edition 9 clause 5.7.7 are the same retained function. Output contract-shaped data and explicit uncertainty. Do not edit API or UI.”

## Integration sequence

1. Agree on the normalized clause record and one JSON response; do not wait for all code to exist.
2. Frontend builds from the contract example while API and agent work in parallel.
3. Agent provides one small working analysis function; API connects it; frontend switches to live response.
4. Run the two editions end to end. Then use the organizers’ control set to check known reorganization, actual loss, duplication and cited sources.
5. Freeze features with enough time to write README, rerun the demo, inspect repository contents for secrets, and submit through the event platform.

Draft PRs make progress visible. Integrate early; do not leave the first full run until the final hour. A push to GitHub alone may not complete the platform submission.
