# Project State
## Product
Insurance Operations AI is becoming an AI front desk SaaS for small independent U.S. insurance agencies. The target product answers agency-approved FAQs, collects qualified leads, and routes requests for human follow-up through browser voice and, after the browser workflow is complete, inbound telephone calls. The current implementation remains a development-only, synthetic-data browser voice foundation.

## Current Architecture
One repository contains a Next.js TypeScript frontend, FastAPI API, and separate Python worker. FastAPI and worker share SQLAlchemy 2 and psycopg 3 connections to Neon PostgreSQL; runtime uses bounded pooling and Alembic uses a direct connection. The verified database contains agencies, application users, memberships, customers, audit events, idempotency records, generic conversation sessions, immutable confirmed conversation intakes, receptionist settings, approved FAQs, leads, and human-handoff requests. The repository also defines an unverified migration and backend contracts for agency call policies, inbound numbers, inbound calls, and immutable call events. Voice provider details are isolated behind provider-neutral contracts and adapters. Development APIs resolve one deterministic active actor and agency without a production authentication system.

## Non-Negotiable Rules
- Neon PostgreSQL is the only database; no Supabase runtime or authentication code.
- Backend rules, ownership, validation, idempotency, quotas, audit, and transaction boundaries are authoritative.
- Voice use requires disclosure acceptance, microphone consent, synthetic-data acknowledgement, and explicit transcript confirmation.
- Never retain raw audio; keep drafts in browser memory and persist transcript text only after confirmation.
- Voice AI cannot quote, advise, bind, verify coverage, recommend limits, or make autonomous decisions.
- Use synthetic data only in development; never commit secrets or real customer data.
- Keep provider-specific SDKs, credentials, request mapping, and metadata inside adapters.
- Unsupported, uncertain, regulated, or sensitive requests must be escalated to agency staff instead of improvised.

## Current Roadmap
Backend/API completion is the active execution strategy: finish approved knowledge, leads, handoff, inbound-call orchestration, telephony adapters, and backend hardening before resuming frontend work. The final operations UI will be built against stable APIs. Product acceptance gates remain mandatory before production claims. `docs/ai-receptionist-product-plan.md` is the authoritative roadmap.

## Completed Major Slices
- Task 001: repository memory and minimal frontend, API, and worker runtimes.
- Tasks 002–004: verified Neon connection, migrations, six approved foundation tables, ownership, readiness, CI PostgreSQL, and development agency seed.
- Task 005: prior authentication/customer prerequisite merged; its Supabase implementation is removed by the current owner decision.
- Task 006 working branch: generic conversation persistence, deterministic development actor, ElevenLabs adapters, browser demo, confirmation transaction, focused tests, Release 1A disclosure, and setup documentation are implemented; the latest disclosure/documentation slice is not yet owner-verified.
- Milestone 1 first slice: the public product is repositioned as an AI receptionist; agency-owned receptionist settings, optimistic concurrency, audit events, development APIs/UI, migration, and synthetic seed are implemented and verified against the development database.
- Backend approved-FAQ and lead/handoff slices are owner-verified: confirmed intakes create one lead transactionally; deterministic source-backed FAQ lookup, lead lifecycle/detail APIs, and idempotent callback/live-transfer request APIs are present behind development actor resolution.

## Important Decisions
- Use Next.js/TypeScript, FastAPI/Python 3.13, SQLAlchemy 2, psycopg 3, Alembic, and Neon PostgreSQL.
- Require Node.js 26 for the web workspace and CI; the pinned Next.js 16.2.12 package supports Node.js >=20.9.0 and the pinned ElevenLabs React 1.12.0 package has no restrictive Node.js engine.
- Use one repository with independently runnable web, API, and worker identities; avoid unnecessary monorepo tooling.
- Seed one deterministic development agency, actor, and active membership only in development.
- Use `conversation_sessions` and `conversation_intakes`; provider names never appear in business table or API names.
- Use ElevenLabs two-way WebRTC with a server-minted short-lived token and server-only API key.
- Require explicit owner selection of the provider LLM, STT, TTS, and voice; unavailable selections stop setup instead of silently falling back.
- Limit each session to 180 seconds, each agency to one concurrent session, and each UTC day to ten authorizations.
- Enable ElevenLabs ZRM when the account supports it. Its absence is acceptable only for the synthetic development demo and blocks every real-data and production mode.
- Bound browser conversation API requests to 15 seconds; connection failures enter a cleanup state before retry and terminal confirmation failures require a new session.
- Make confirmed intakes immutable and confirmation idempotent; customer, intake, audit, and session confirmation share one transaction.
- Use a forward Alembic revision for conversation tables because the verified initial migration is an established baseline.
- Keep production identity/authentication deferred to a separately approved specification.
- Keep browser and telephone channels thin: both must reuse the same backend FAQ, intake, lead, handoff, quota, and audit services through provider-neutral ports.
- Freeze new frontend work until backend browser and telephone capabilities are complete and owner-verified; build the final UI against stable API contracts.
- Answer only from active agency-approved FAQs and retain a source reference for each supported answer.

## Implementation Pending Owner Verification
- Migration `20260808_0007` adds agency call policies, inbound-number routing, inbound calls, immutable call events, and one callback handoff per inbound call.
- Development APIs simulate provider-neutral call reception, event transitions, open-hours transfer decisions, after-hours/failed-transfer callback fallback, lead linking, concurrency limits, and daily limits.
- Telephony and notification ports define vendor boundaries; no concrete telephone adapter, signed webhook ingress, or external notification delivery is connected.

## Deferred / Not Yet Implemented
Concrete telephony adapter, signed provider webhook ingress, DTMF, enforced call duration, detailed usage/cost metering, durable notification outbox/delivery, production authentication, real customer use, billing, integrations, deployment controls, final operations UI, and production hardening remain deferred. Raw-audio storage remains out of scope by default.

## Risks / Watchouts
- The backend approved-FAQ, lead, and handoff services are verified, but the final lead inbox UI and complete browser acceptance workflow remain required for the Milestone 1 acceptance gate.
- The disposable test database rebuild and full 44-test Python suite pass. A follow-up migration shortens one receptionist check-constraint identifier to avoid PostgreSQL's identifier-length truncation; development is at the new head and Alembic reports no model drift.
- The owner reports clean migration, static-analysis, focused database/API, and Alembic drift results for the approved-FAQ and migration `20260808_0006` lead/handoff slices.
- The inbound-call migration and backend orchestration are implemented but unverified; do not claim real telephone support until the owner reports clean checks and a concrete signed adapter is implemented.
- The web workspace uses pinned Next.js 16.2.12 and ElevenLabs React 1.12.0 dependencies; both are installed and verified under Node.js 26.
- Provider dashboard privacy settings and the agent prompt/tool must be verified manually; the application cannot prove provider-side retention from its API response.
- The synthetic-demo disclosure is implemented; provider region, LLM, STT, TTS, voice, privacy controls, and billing controls still require owner selection and dashboard verification before enabling the feature flags.
- Browser transcript callbacks can contain evolving recognition text; the UI de-duplicates adjacent updates and explicit review remains mandatory.
- The development actor is deliberately not production authentication and the routes are hidden unless development-only flags and seed data agree.
- Never run database downgrade/rebuild commands unless `TEST_DATABASE_URL` is confirmed disposable and isolated.

## Standard Verification
- `npm install --package-lock-only --ignore-scripts --workspace @insurance-operations/web`
- `npm ci`
- `npm run verify:web`
- `ruff format --check .`
- `ruff check .`
- `mypy apps/backend/src tests`
- `APP_ENVIRONMENT=test alembic downgrade base`
- `APP_ENVIRONMENT=test alembic upgrade head`
- `APP_ENVIRONMENT=test alembic current`
- `APP_ENVIRONMENT=test alembic check`
- `APP_ENVIRONMENT=test pytest`
- `insurance-operations-worker --check`
