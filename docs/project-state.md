# Project State
## Product
Insurance Operations AI is becoming an AI front desk SaaS for small independent U.S. insurance agencies. The target product answers agency-approved FAQs, collects qualified leads, and routes requests for human follow-up through browser voice and inbound telephone calls. The current implementation includes development-only, synthetic-data browser and telephone foundations. The telephone slice is automated-test verified; live provider configuration and a synthetic call remain pending.

## Current Architecture
One repository contains a Next.js TypeScript frontend, FastAPI API, and separate Python worker. FastAPI and worker share SQLAlchemy 2 and psycopg 3 connections to Neon PostgreSQL; runtime uses bounded pooling and Alembic uses a direct connection. The verified database contains agencies, application users, memberships, customers, audit events, idempotency records, generic conversation sessions, immutable confirmed conversation intakes, receptionist settings, approved FAQs, leads, human-handoff requests, call policies, inbound numbers, calls, immutable call events, browser/phone session channels, call linkage, and immutable verbal-confirmation receipts. Provider-specific behavior is isolated in Twilio and ElevenLabs adapters while application call state remains provider-neutral. Development APIs resolve one deterministic active actor and agency without a production authentication system; hosted demo administration adds a development-only bearer token while its public status projection is content-minimizing.

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
- Use a separate private ElevenLabs phone agent. Twilio retains carrier and transfer authority; ElevenLabs register-call supplies the conversational media connection.
- Do not materialize phone-originated customers, confirmed intakes, leads, transcripts, or handoffs until an explicit verbal readback receipt exists and a signed post-call transcript finalizes the call.

## Verified Telephone and Demo Implementation
- Migration `20260808_0007` adds agency call policies, inbound-number routing, inbound calls, immutable call events, and one callback handoff per inbound call.
- Migration `20260819_0008` adds browser/phone conversation channels, one-to-one inbound-call linkage, and immutable structured verbal-confirmation receipts.
- Signed Twilio ingress now normalizes inbound calls, returns ElevenLabs register-call TwiML, executes carrier-side active-call transfers, and normalizes signed transfer results.
- Authenticated ElevenLabs tools gate consent, agency-approved FAQ lookup, structured intake readback confirmation, and transfer/callback requests. HMAC-verified post-call transcripts materialize confirmed customer, intake, lead, and handoff records exactly once; unconfirmed transcript content is discarded.
- Telephone provider configuration is development-only, limited to 180 seconds, synthetic data, a dedicated phone agent, and explicit privacy confirmation.
- A Harborline sandbox seed, protected hosted-demo administration, sanitized public call-status projection, `/phone-demo` showcase, Render Blueprint, Vercel configuration, and client-demo runbook are implemented.
- Automated verification covers provider signatures, tools, post-call materialization, idempotency, transfers, callback fallback, schema invariants, sandbox security, the public projection, and the production web build. Live provider dashboards and a real carrier call are not application-verifiable and remain pending.

## Deferred / Not Yet Implemented
DTMF, detailed usage/cost metering, durable notification outbox/delivery, production authentication, real customer use, billing, integrations, deployment controls, final operations UI, and production hardening remain deferred. Raw-audio storage remains out of scope by default.

## Risks / Watchouts
- The backend approved-FAQ, lead, and handoff services are verified, but the final lead inbox UI and complete browser acceptance workflow remain required for the Milestone 1 acceptance gate.
- The focused phone/migration suite passes 29 tests. The complete Python run reached 69 passes and one transient Neon read timeout; the timed-out schema-inspection test passed immediately on isolated retry. The disposable database was restored to `20260819_0008 (head)`, and Alembic reports no model drift.
- The owner reports clean migration, static-analysis, focused database/API, and Alembic drift results for the approved-FAQ and migration `20260808_0006` lead/handoff slices.
- Do not present the sandbox as live telephone support until the provider-dashboard and temporary-number checklist completes. Automated checks cannot verify Twilio routing, ElevenLabs dashboard privacy/audio settings, carrier transfer behavior, or end-to-end call quality.
- ElevenLabs register-call mode does not provide native transfers. The implementation deliberately commands the active Twilio call and consumes Twilio's signed Dial result; this behavior requires a live synthetic-call check.
- The web workspace uses pinned Next.js 16.2.12 and ElevenLabs React 1.12.0 dependencies; both are installed and verified under Node.js 26.
- Provider dashboard privacy settings and the agent prompt/tool must be verified manually; the application cannot prove provider-side retention from its API response.
- The synthetic-demo disclosure is implemented; provider region, LLM, STT, TTS, voice, privacy controls, and billing controls still require owner selection and dashboard verification before enabling the feature flags.
- Browser transcript callbacks can contain evolving recognition text; the UI de-duplicates adjacent updates and explicit review remains mandatory.
- The development actor is deliberately not production authentication and the routes are hidden unless development-only flags and seed data agree.
- Never run database downgrade/rebuild commands unless `TEST_DATABASE_URL` is confirmed disposable and isolated.
- Alembic drift detection currently warns about an unresolvable foreign-key cycle among `agency_leads`, `conversation_intakes`, `conversation_sessions`, and `inbound_calls`. It reports no drift today, but a future SQLAlchemy/Alembic release may make this warning fatal.

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
