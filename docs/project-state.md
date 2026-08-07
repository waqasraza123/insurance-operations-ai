# Project State
## Product
Insurance Operations AI is a portfolio platform for small independent U.S. insurance agencies. The owner moved browser Voice AI ahead of Document AI. Voice Release 1A is a development-only, synthetic-data, two-way intake demo that collects contact details and intent, then requires editable review and explicit confirmation. It is not telephony, quoting, advice, coverage verification, binding, underwriting, claims handling, or autonomous decision-making.

## Current Architecture
One repository contains a Next.js TypeScript frontend, FastAPI API, and separate Python worker. FastAPI and worker share SQLAlchemy 2 and psycopg 3 connections to Neon PostgreSQL; runtime uses bounded pooling and Alembic uses a direct connection. The database foundation contains agencies, application users, memberships, customers, audit events, idempotency records, generic conversation sessions, and immutable confirmed conversation intakes. Voice provider details are isolated in provider metadata plus backend/frontend ElevenLabs adapters. Development APIs resolve one deterministic active actor and agency without a production authentication system.

## Non-Negotiable Rules
- Neon PostgreSQL is the only database; no Supabase runtime or authentication code.
- Backend rules, ownership, validation, idempotency, quotas, audit, and transaction boundaries are authoritative.
- Voice use requires disclosure acceptance, microphone consent, synthetic-data acknowledgement, and explicit transcript confirmation.
- Never retain raw audio; keep drafts in browser memory and persist transcript text only after confirmation.
- Voice AI cannot quote, advise, bind, verify coverage, recommend limits, or make autonomous decisions.
- Use synthetic data only in development; never commit secrets or real customer data.
- Keep provider-specific SDKs, credentials, request mapping, and metadata inside adapters.
- Human approval remains mandatory before future Document AI candidates affect approved policy data.

## Current Roadmap
Verified Neon foundation; Supabase removal and development actor; generic conversation foundation; ElevenLabs two-way Voice AI; confirmed intake and customer creation; Voice AI testing, privacy verification, polish, and portfolio demo; document upload and worker; Document AI evaluation and implementation; human review, approval, audit, and remaining features.

## Completed Major Slices
- Task 001: repository memory and minimal frontend, API, and worker runtimes.
- Tasks 002–004: verified Neon connection, migrations, six approved foundation tables, ownership, readiness, CI PostgreSQL, and development agency seed.
- Task 005: prior authentication/customer prerequisite merged; its Supabase implementation is removed by the current owner decision.
- Task 006 working branch: generic conversation persistence, deterministic development actor, ElevenLabs adapters, browser demo, confirmation transaction, focused tests, Release 1A disclosure, and setup documentation are implemented; the latest disclosure/documentation slice is not yet owner-verified.

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

## Deferred / Not Yet Implemented
Production authentication, real customer use, complete customer management, telephony, raw-audio storage, provider fallback, uploads, Storage, durable jobs, Document AI, OCR, review/approval UI, email, deployment configuration, and remaining business tables.

## Risks / Watchouts
- Backlog item 6 lifecycle hardening and its focused frontend tests are implemented but not yet owner-verified.
- Task 006 backend checks and migration remain unverified locally under the owner testing policy; `npm run verify:web` passes with the documented public environment values.
- The web workspace uses pinned Next.js 16.2.12 and ElevenLabs React 1.12.0 dependencies; both are installed and verified under Node.js 26.
- Provider dashboard privacy settings and the agent prompt/tool must be verified manually; the application cannot prove provider-side retention from its API response.
- The Release 1A synthetic-demo disclosure is owner-approved and implemented; provider region, LLM, STT, TTS, voice, privacy controls, and billing controls still require owner selection and dashboard verification before enabling the feature flags.
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
