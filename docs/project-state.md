# Project State
## Product
Release 1 is a document-first operations platform for small independent U.S. insurance agencies. It converts English-language personal auto declaration-page PDFs into traceable candidate records for human review. It is not an agency management system, quoting tool, coverage-verification service, or autonomous insurance agent.

## Current Architecture
The repository is a single coordinated codebase with three independently runnable identities: a Next.js TypeScript frontend, a FastAPI web service, and a separate Python worker process. FastAPI and worker share a synchronous SQLAlchemy 2 and psycopg 3 connection foundation for Neon PostgreSQL. Runtime traffic uses a bounded pooled URL; Alembic uses a direct, non-pooled migration connection. The audited first migration contains agencies, application users, memberships, customers, audit events, and idempotency records with server-maintained timestamps and row versions where required. No authentication or product API is integrated.

## Non-Negotiable Rules
- Human approval is required before candidate data can affect approved policy data.
- Source documents, extracted artifacts, candidate values, reviewer decisions, and approved versions remain distinct.
- Approved policy versions are immutable, with explicit current-version selection.
- Release 1 supports one agency context and English-language U.S. personal auto declaration-page PDFs only.
- Backend rules, authorization, validation, idempotency, concurrency, cost limits, and audit behavior cannot be delegated to the browser.
- Use synthetic data only during development and demonstrations; never commit secrets or real insurance customer data.
- Provider choices for PDF parsing, OCR, and AI remain deferred until the controlled evaluation gate.

## Current Roadmap
Task 001 established repository guardrails and the three runtime identities. Tasks 002–003 added Neon connection handling and the initial persistence layer. Task 004 corrected that layer against Documents 4, 6, and 7; its database migration, constraints, isolation, seed, formatting, linting, and typing are verified against an isolated disposable Neon test database. The prioritized path is recorded in `docs/implementation-backlog.md`: authentication/customer, private PDF upload, durable worker, provider-neutral candidates, review/approval, controlled Document AI evaluation/integration, then a separately specified narrow Voice AI extension.

## Completed Major Slices
- Task 001: repository memory system and minimal runnable foundation.
- Tasks 002–004 database foundation: isolated Neon migration rebuild, 24 database tests, Alembic agreement, formatting, linting, and strict typing verified.

## Important Decisions
- Use one Git repository while keeping frontend, API, and worker runtime responsibilities separate.
- Use Next.js with TypeScript for the frontend and FastAPI with Python for server runtimes.
- Use Node.js 22 and Python 3.13 for the foundation.
- Use Neon PostgreSQL instead of Supabase PostgreSQL when database work is explicitly authorized.
- Use SQLAlchemy 2 with psycopg 3 for shared synchronous web/worker persistence and Alembic for migration-only schema changes.
- Use pooled Neon connections for runtime work, direct `NullPool` connections for migrations, and an isolated required test database.
- Seed only one deterministic development agency; do not seed users, customers, or business workflows.
- Before shared feature data exists, correct a flawed initial migration in place; after any shared application, use a forward-only migration.
- Add nullable demo and future-resource identifiers in dependency order, then add their foreign keys only when the approved parent tables exist.
- Use Document 6 section 67.1's full idempotency unique scope, including `actor_scope_type`; section 44's index summary abbreviates that scope.
- Keep authentication, private storage, email, OCR, and AI integrations deferred.
- Avoid microservices, Redis, Kafka, Kubernetes, GraphQL, generalized workflow engines, and premature provider abstractions.

## Deferred / Not Yet Implemented
Owner-run foundation verification; authentication flows; authorization behavior; customer APIs and UI; private storage; document upload; remaining business tables; durable jobs; AI; OCR; document processing; review; approval transactions; audit presentation; usage controls; email; demo sessions; deployment configuration; and every Voice AI capability.

## Risks / Watchouts
- The approved PDFs name Supabase PostgreSQL; the later owner direction selecting Neon is authoritative for database hosting.
- Task 004 database verification passed on 2026-08-02; frontend verification and live application workflow testing remain separate checks.
- `demo_session_id` and audit references to not-yet-created domain tables intentionally have no foreign keys until those approved parent-table migrations exist.
- If revision `20260802_0001` was already applied to shared data, do not apply the edited revision over it; create and review a forward correction migration instead.
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
