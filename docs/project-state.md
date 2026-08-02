# Project State
## Product
Release 1 is a document-first operations platform for small independent U.S. insurance agencies. It converts English-language personal auto declaration-page PDFs into traceable candidate records for human review. It is not an agency management system, quoting tool, coverage-verification service, or autonomous insurance agent.

## Current Architecture
The repository is a single coordinated codebase with three independently runnable identities: a Next.js TypeScript frontend, a FastAPI web service, and a separate Python worker process. FastAPI and worker share a synchronous SQLAlchemy 2 and psycopg 3 connection foundation for Neon PostgreSQL. Runtime traffic uses a bounded pooled URL; Alembic uses a direct, non-pooled migration connection. The first migration contains agencies, application users, memberships, customers, audit events, and idempotency records. No authentication or product API is integrated.

## Non-Negotiable Rules
- Human approval is required before candidate data can affect approved policy data.
- Source documents, extracted artifacts, candidate values, reviewer decisions, and approved versions remain distinct.
- Approved policy versions are immutable, with explicit current-version selection.
- Release 1 supports one agency context and English-language U.S. personal auto declaration-page PDFs only.
- Backend rules, authorization, validation, idempotency, concurrency, cost limits, and audit behavior cannot be delegated to the browser.
- Use synthetic data only during development and demonstrations; never commit secrets or real insurance customer data.
- Provider choices for PDF parsing, OCR, and AI remain deferred until the controlled evaluation gate.

## Current Roadmap
Task 001 established repository guardrails and the three runtime identities. The Tasks 002–003 implementation adds Neon connection handling, migrations, and the first approved persistence tables; owner-run verification remains required before the slice is complete. Later approved slices cover authentication, customer behavior, private upload, durable jobs, provider-neutral candidates, evaluation, review, approval, recovery, audit behavior, demo isolation, security, deployment, and release polish.

## Completed Major Slices
- Task 001: repository memory system and minimal runnable foundation.

## Important Decisions
- Use one Git repository while keeping frontend, API, and worker runtime responsibilities separate.
- Use Next.js with TypeScript for the frontend and FastAPI with Python for server runtimes.
- Use Node.js 22 and Python 3.13 for the foundation.
- Use Neon PostgreSQL instead of Supabase PostgreSQL when database work is explicitly authorized.
- Use SQLAlchemy 2 with psycopg 3 for shared synchronous web/worker persistence and Alembic for migration-only schema changes.
- Use pooled Neon connections for runtime work, direct `NullPool` connections for migrations, and an isolated required test database.
- Seed only one deterministic development agency; do not seed users, customers, or business workflows.
- Keep authentication, private storage, email, OCR, and AI integrations deferred.
- Avoid microservices, Redis, Kafka, Kubernetes, GraphQL, generalized workflow engines, and premature provider abstractions.

## Deferred / Not Yet Implemented
Authentication flows, authorization behavior, customer APIs and UI, private storage, document upload, remaining business tables, durable jobs, AI, OCR, document processing, review, approval transactions, audit presentation, usage controls, email, demo sessions, and deployment configuration.

## Risks / Watchouts
- The approved PDFs name Supabase PostgreSQL; the later owner direction selecting Neon is authoritative for database hosting.
- Tasks 002–003 were committed without local tests, migrations, builds, linting, or type checking under the active owner policy; run the documented verification before further schema work.
- Do not let foundation placeholders become unreviewed business or security decisions.
- Do not finalize parser, OCR, model, input strategy, provider retries, cost ceilings, or quality claims before evaluation approval.
- Preserve independently deployable web and worker behavior as shared backend code grows.

## Standard Verification
- `npm run verify:web`
- `alembic upgrade head`
- `alembic check`
- `ruff format --check .`
- `ruff check .`
- `mypy apps/backend/src tests`
- `pytest`
- `insurance-operations-worker --check`
