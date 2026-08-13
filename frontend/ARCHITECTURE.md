# Frontend Architecture

## Structure

- `src/components`: reusable design-system primitives and visualization shells.
- `src/layouts`: public, authentication, wizard, and authenticated application shells.
- `src/pages`: route-level compositions.
- `src/mock`: centralized, typed non-production view-model data.
- `src/services`: replaceable asynchronous integration boundaries.
- `src/types.ts`: account, subscription, authority, market, trade, performance, and security models.
- `src/styles.css`: semantic tokens, component styling, responsive behavior, and accessibility states.

## Principles

The application is a production-quality structure with temporary adapters. Pages do not call backend engine modules, contain secrets, or independently calculate trading/risk intelligence. Service interfaces can later be replaced with HTTP adapters without restructuring the layouts.

The authenticated shell is persistent across all flagship workspaces. Mobile uses a drawer and responsive content flow rather than shrinking the desktop layout. The Guided Evaluation is Explorer intelligence plus a Co-Pilot preview and never exposes Autopilot.

## Security boundary

Client validation improves UX but is not authorization. Registration, verification, MFA, payment, trusted devices, session timeout, plan entitlements, broker permissions, and step-up authentication must be enforced by future backend services. Payment UI is a provider-abstraction stub; it does not persist or submit raw card data.

## Development auth boundary

`VITE_ENABLE_DEV_AUTH=true` enables a local-only visual-QA authentication path.

The only accepted development sign-in values are:

- Email: `dev@structureiq.local`
- Password: `StructureIQ!Dev1`
- MFA: `123456`

When development auth is disabled, the frontend does not treat arbitrary credentials or arbitrary MFA codes as authenticated. It returns an integration-unavailable state because production authentication APIs are not implemented yet.

This bypass is intentionally environment-gated, deterministic, and non-secret. It must not be used as production authorization, and future server APIs must enforce identity, session, MFA, account state, subscription, billing, broker permissions, and AI Authority.

Authenticated workspace routes remain directly renderable in local development so visual QA can inspect Command Center, Market Intelligence, Trade Intelligence, and Performance Intelligence before the real customer-auth backend exists.
