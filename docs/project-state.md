# Project State
## Product
Release 1 is a document-first operations platform for small independent U.S. insurance agencies. It converts English-language personal auto declaration-page PDFs into traceable candidate records for human review. It is not an agency management system, quoting tool, coverage-verification service, or autonomous insurance agent.

## Current Architecture
The repository is a single coordinated codebase with three independently runnable identities: a Next.js TypeScript frontend, a FastAPI web service, and a separate Python worker process. The current foundation has no persistence or external-service integration. The approved future shape is a modular monolith with FastAPI as the business authority, asynchronous work outside web requests, and distinct source, candidate, review, and immutable approved records. Neon PostgreSQL replaces Supabase PostgreSQL as the planned primary relational database; it is not integrated yet.

## Non-Negotiable Rules
- Human approval is required before candidate data can affect approved policy data.
- Source documents, extracted artifacts, candidate values, reviewer decisions, and approved versions remain distinct.
- Approved policy versions are immutable, with explicit current-version selection.
- Release 1 supports one agency context and English-language U.S. personal auto declaration-page PDFs only.
- Backend rules, authorization, validation, idempotency, concurrency, cost limits, and audit behavior cannot be delegated to the browser.
- Use synthetic data only during development and demonstrations; never commit secrets or real insurance customer data.
- Provider choices for PDF parsing, OCR, and AI remain deferred until the controlled evaluation gate.

## Current Roadmap
Task 001 establishes repository memory, engineering guardrails, and runnable frontend, API, and worker identities. Later approved slices cover local services, persistence, authentication, customer workflow, private upload, durable jobs, provider-neutral candidates, evaluation, review, approval, recovery, audit, demo isolation, security, deployment, and release polish. Each later slice requires its own scoped task and verification.

## Completed Major Slices
- Task 001: repository memory system and minimal runnable foundation.

## Important Decisions
- Use one Git repository while keeping frontend, API, and worker runtime responsibilities separate.
- Use Next.js with TypeScript for the frontend and FastAPI with Python for server runtimes.
- Use Node.js 22 and Python 3.13 for the foundation.
- Use Neon PostgreSQL instead of Supabase PostgreSQL when database work is explicitly authorized.
- Keep PostgreSQL, authentication, private storage, email, OCR, and AI integrations out of Task 001.
- Avoid microservices, Redis, Kafka, Kubernetes, GraphQL, generalized workflow engines, and premature provider abstractions.

## Deferred / Not Yet Implemented
Authentication, authorization, database connectivity, migrations, business tables, private storage, document upload, job queues, domain APIs, customer records, AI, OCR, document processing, review, approval, audit, usage controls, email, demo sessions, and deployment configuration.

## Risks / Watchouts
- The approved PDFs name Supabase PostgreSQL; the later owner direction selecting Neon is authoritative for database hosting.
- Do not let foundation placeholders become unreviewed business or security decisions.
- Do not finalize parser, OCR, model, input strategy, provider retries, cost ceilings, or quality claims before evaluation approval.
- Preserve independently deployable web and worker behavior as shared backend code grows.

## Standard Verification
- `npm run verify:web`
- `ruff format --check .`
- `ruff check .`
- `mypy apps/backend/src tests`
- `pytest`
- `insurance-operations-worker --check`
