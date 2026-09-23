# Codex instructions for the HackAlem team

This repository implements the official case [AI Agent: Organizational Structure and Functions Analysis](https://docs.google.com/document/d/1m-r31DH6Q__9OcN4WiP453CE6drlTTQ8Px3xi3IiVHk/edit). Read [docs/case-map.md](docs/case-map.md), [docs/api-contract.md](docs/api-contract.md), and [docs/team-tasks.md](docs/team-tasks.md) before changing code.

The product compares organization documents before and after reorganization. It identifies retained, reorganized, and new units; possible lost or duplicate functions and potential conflicts of interest; and an analytical conclusion. Every substantive finding must point to an exact supplied document and clause, paragraph, page, or sheet row. Conclusions are advisory and require a responsible employee's review.

## Shared rules

- Follow the official case and provided control documents. Do not invent a lost function, duplication, conflict, requirement, source quote, or successful action.
- A changed clause number or department name alone is not a lost function. Compare meaning and ownership, and show both before and after evidence where available.
- Separate observed facts from potential risks. When evidence is missing or ambiguous, say so in the result.
- Keep the document set local unless its sharing rights are confirmed. Never commit API keys, `.env`, downloaded private documents, generated caches, or personal information.
- Use [docs/api-contract.md](docs/api-contract.md) as the shared interface. The integration owner updates it before changing shared fields.
- Prefer one reliable path: upload documents, extract cited functions, compare, review findings, export/read conclusion. Add optional legislation and benchmarking only after all mandatory behavior works.

## Ownership and Git

- Frontend/design: `frontend/` on `feat/frontend`.
- Backend/API and integration: `backend/`, dependency and run configuration, `README.md`, shared contract, and merge coordination on `feat/backend-api`.
- Agent/comparison logic: `agent/` and its focused checks on `feat/agent-core`.
- Each person uses their own clone and Codex session. Start each task by checking the branch and reading this file. Do not edit another owner's files without a team agreement.
- Make reviewable commits and pull requests into `main`; keep `main` runnable. Avoid force-push and secret exposure.

## Definition of done

The documented control scenario shows the changed units, a supported function comparison, potential losses/duplications/conflicts when present, clickable exact source fragments, and a readable conclusion. It handles unsupported or unreadable input without inventing findings. Run the documented end-to-end path and state any limits in the README.
