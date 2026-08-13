# StructureIQ Frontend

Phase 1 implements the public website, customer-entry wizard, authentication support screens, persistent authenticated application shell, and visual shells for all four flagship workspaces.

## Stack

- React and TypeScript
- Vite
- React Router
- Vitest and Testing Library
- Semantic CSS with centralized design tokens

## Run locally

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open the local URL printed by Vite.

## Development visual QA auth

Production authentication, billing, and MFA APIs are not connected in this frontend foundation. The frontend therefore includes an explicit local-only development auth mode for visual review.

Copy `.env.example` to `.env.local` and enable:

```text
VITE_ENABLE_DEV_AUTH=true
```

Development credentials:

```text
Email: dev@structureiq.local
Password: StructureIQ!Dev1
MFA: 123456
```

These values are intentionally non-secret and must never be treated as production authentication. They exist only so developers can inspect approved frontend routes before server-enforced customer auth exists.

When `VITE_ENABLE_DEV_AUTH` is not `true`, arbitrary credentials are not accepted. Sign-in and MFA show an integration-unavailable message instead of pretending the user is authenticated.

Development review routes:

- `/`
- `/signin`
- `/evaluation/create-account`
- `/evaluation/payment`
- `/evaluation/verify`
- `/evaluation/welcome`
- `/app`
- `/app/markets`
- `/app/trades`
- `/app/performance`

## Build and test

```powershell
npm.cmd run build
npm.cmd test
```

## Routes

Public: `/`, `/pricing`, `/signin`, `/forgot-password`, `/reset-password`, `/reset-confirmation`.

Guided Evaluation: `/evaluation/create-account`, `/evaluation/payment`, `/evaluation/verify`, `/evaluation/welcome`.

Authenticated: `/app` (Command Center), `/app/markets`, `/app/trades`, `/app/performance`.

`/onboarding` is intentionally a placeholder for the later mission-based onboarding phase.

## Data and integration boundary

UI pages consume typed view models from `src/mock/data.ts` through interfaces in `src/services/index.ts`. Mock values are illustrative and non-production. Authentication, authorization, payment tokenization, MFA enrollment, market intelligence, trading, and performance integrations remain server-side implementation work.

Frontend route guards are UX controls only. Future APIs must enforce account state, subscription, AI Authority, and security status. Raw passwords and raw card details must never be stored in frontend state beyond transient controlled inputs or persisted in browser storage.

Environment keys belong in local `.env` files based on `.env.example`; never commit secrets.
