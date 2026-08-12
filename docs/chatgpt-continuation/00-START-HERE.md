# Code-Evidenced Continuation Specification

## Mandatory evidence rule

> **Treat the repository as primary evidence and this continuation specification as its index. Before changing a feature, inspect every referenced implementation, migration, schema, test, and caller. Never infer an unresolved product or architecture decision. When evidence conflicts, report the conflict and ask before implementing.**

This pack indexes the dirty working tree inspected on 2026-08-09. It is not a substitute for inspecting code, and it does not assert that the current tree passes verification.

## Project and product direction

Insurance Operations AI is evolving into a multi-tenant AI front-desk SaaS for independent insurance agencies. The present demonstrable path is a development-only, synthetic-data receptionist that can conduct a browser Voice AI conversation, answer only agency-approved FAQs, place an editable intake draft in front of the user, and persist a customer, confirmed intake, and lead only after explicit confirmation. The next product expansion is inbound telephone orchestration with human transfer/callback behavior, followed by production tenancy/authentication, operational delivery, and the deferred Document AI workflow.

Repository status: **PARTIAL**. The browser foundation and several backend slices exist; a production-capable end-to-end application does not.

## Repository snapshot

- Audit date: 2026-08-09, Asia/Karachi.
- Branch: `main`.
- HEAD/latest commit: `7f2f505f3b3d8b882e29904b624d83fa04dcc8e6` (`7f2f505 chore: upgrade web runtime to Node 26`).
- Upstream relation observed: `origin/main` pointed to the same commit.
- Working tree: dirty, with substantial tracked modifications, tracked deletions, and untracked implementation files. The latest commit does **not** contain the latest implementation.
- Tracked diff observed before this pack: 32 files, 2,199 insertions, 281 deletions; untracked files were additional and were not counted by that statistic.
- Verification for the entire present working tree: **IMPLEMENTED—UNVERIFIED** where code exists. No verification command was run during this audit.

### Working-tree capability map

The following summarizes the pre-pack working tree. It deliberately points to files rather than copying diffs.

| Capability | Working-tree evidence | Meaning |
|---|---|---|
| Receptionist | Modified `apps/backend/src/insurance_operations/application.py`, `apps/backend/src/insurance_operations/database/seed.py`, frontend shell/styles; untracked `receptionist/`, `database/models/receptionist.py`, receptionist page/features, migrations `0003`/`0004`, and focused tests | Versioned settings, audit, development API, seed, and editor were added. Owner-reported focused verification exists for an earlier slice snapshot. |
| FAQ | Modified application, seed, Voice adapter/UI, setup docs; untracked `approved_faqs/`, model, FAQ page/features, migration `0005`, and tests | Approved-content CRUD, deterministic safe lookup, conversation tool, and manager were added. Owner-reported focused verification exists for the FAQ slice snapshot. |
| Lead/handoff | Modified conversation schemas/service and application; untracked `leads/`, lead model, migration `0006`, handoff doc, and expanded conversation tests | Confirmation now creates a lead transactionally; tenant-filtered lead/handoff APIs exist. No lead frontend or notification delivery exists. |
| Telephony/inbound calls | Modified application/model exports/tests/DB docs; untracked `telephony/`, telephony model, notification protocol, migration `0007`, telephony docs/tests | Provider-neutral persistence and a development simulation API exist. The entire `0007` slice remains **IMPLEMENTED—UNVERIFIED**; no concrete provider, signature ingress, DTMF, duration enforcement, or delivery adapter exists. |
| Conversations/Voice AI | Modified schemas/service, frontend contracts/adapter/test surface, setup docs | Confirmed intake returns a lead ID; the Voice tool can query approved FAQs. ElevenLabs token issuance remains behind the backend adapter. |
| Database/migrations | Modified model exports, seed, migration/ownership tests; untracked models and `0003` through `0007` | The static Alembic chain ends at `20260808_0007`. File existence does not prove application to any database. |
| Frontend | Modified layout/home/styles/Voice page and untracked receptionist/FAQ surfaces | Routes exist for `/`, `/voice-test`, `/receptionist-settings`, and `/approved-faqs`. Lead and telephony surfaces do not exist. |
| Tests | Modified conversation/migration/ownership/settings tests; untracked receptionist/FAQ/telephony tests | Test code is evidence of intended behavior, not evidence that the current tree passes. Telephony coverage is narrow relative to its manual checklist. |
| Documentation | Modified README/setup/project state; deleted old backlog, Voice scope, and seven Release 1 PDFs; untracked current product/API docs | Historical planning was inspected from HEAD where needed. Deleted files must not be mistaken for absent history. |

Other pre-existing tracked changes include `.env.example`, `AGENTS.md`, `pyproject.toml`, `README.md`, and setup docs. Exact paths are recorded in `01-codebase-map.md` and `09-verification-ledger.md`.

## Architecture and runtime spine

This is a monorepo with four current runtime layers:

1. Next.js App Router frontend under `apps/web/src`, using server page entry points and client feature modules.
2. FastAPI backend under `apps/backend/src/insurance_operations`; `api.py` builds settings/engine and calls `application.create_app()`.
3. SQLAlchemy 2 models plus PostgreSQL-specific constraints/triggers; Alembic revisions are under `migrations/versions`.
4. A Python worker entry point in `worker.py` that performs readiness and then waits. It has no durable-job implementation.

The browser talks only to FastAPI. FastAPI is authoritative for actor resolution, ownership, consent, lifecycle, confirmation, idempotency, audit, limits, and persistence. The browser never receives provider API credentials; it receives an expiring provider conversation token. PostgreSQL is the only current persistence runtime. There is no Supabase runtime or Supabase Auth code.

Primary runtime entry points:

- API: `apps/backend/src/insurance_operations/api.py:main` and `application.py:create_app`.
- Worker: `apps/backend/src/insurance_operations/worker.py:main`.
- Web: `apps/web/src/app/layout.tsx`, `app/page.tsx`, and route pages under `app/`.
- Migration configuration: `alembic.ini`, `migrations/env.py`, and `migrations/versions/*.py`.
- Development seed: `database/seed.py:seed_development_foundation`.

## Major capabilities

| Capability | Status | Evidence-based summary |
|---|---|---|
| Runtime/database foundation through migration `0002` | VERIFIED | Repository notes record prior checks for the Neon-only foundation; current files still show the architecture. This is not a claim that the full dirty tree was rechecked. |
| Development actor and synthetic seed | VERIFIED | `actors.py:resolve_development_actor` and `database/seed.py`; prior owner-reported foundation verification. Production identity is absent. |
| Browser Voice AI, consent, review, and confirmed persistence | PARTIAL | End-to-end development implementation exists with prior slice verification, but current Voice/confirmation files were later modified and the present dirty tree was not rechecked. Production auth/data policy and phone reuse remain absent. |
| Receptionist settings | VERIFIED | Owner-reported focused and full-suite evidence is recorded for the relevant slice snapshot; code exists in backend and frontend. |
| Approved FAQs | VERIFIED | Owner-reported migration/static/focused/drift checks for the FAQ slice; active-only safe lookup and browser tool exist. |
| Lead capture and backend handoff | VERIFIED | Owner-reported migration/static/focused/drift checks for the `0006` slice; no lead UI or delivery mechanism. |
| Inbound telephone orchestration foundation | PARTIAL | Neutral models, policy, simulated receive/events, transfer/callback decisions, and lead linking exist, all **IMPLEMENTED—UNVERIFIED** for `0007`; signed provider ingress and real phone conversation behavior are absent. |
| Notification delivery | NOT IMPLEMENTED | Only `notifications/contracts.py:NotificationPort` exists and has no caller or adapter. |
| Usage metering | NOT IMPLEMENTED | Bounded conversation/call counts exist, but no durable usage/cost ledger exists. |
| Document AI/OCR/review/durable jobs | NOT IMPLEMENTED | Historical roadmap work was deferred; the current worker is only a readiness shell. |
| Production authentication/deployment/billing | DECISION REQUIRED | Owner-controlled designs/providers are unresolved and production implementations are absent. |

## Active objective and exact next step

Current active objective: make the backend-only inbound-call foundation trustworthy, then cross the provider boundary without weakening ownership, idempotency, audit, or insurance-safety rules.

The next repository activity is not new application code:

1. Inspect/restore the disposable test database interrupted during the prior FAQ downgrade, then have the owner run the `0007` migration/static/focused/full verification listed in `09-verification-ledger.md`.
2. If it passes, capture the result and snapshot in `docs/_local/current-session.md` and this ledger.
3. Owner selects the telephony provider and confirms its webhook-signature/replay contract. This is **DECISION REQUIRED**.

The one next highest-leverage implementation slice after those gates is: implement one concrete telephony adapter, a raw-body signed provider webhook ingress, and provider-payload-to-neutral-event normalization as one backend-only slice. Do not include DTMF, phone-conversation persistence, duration controls, usage metering, notifications, or frontend work in that first adapter slice.

Before changing that area, read:

- `docs/project-state.md`
- `docs/_local/current-session.md`
- `docs/chatgpt-continuation/00-START-HERE.md`
- `docs/inbound-call-backend.md`
- `apps/backend/src/insurance_operations/application.py`
- `apps/backend/src/insurance_operations/telephony/contracts.py`
- `apps/backend/src/insurance_operations/telephony/schemas.py`
- `apps/backend/src/insurance_operations/telephony/service.py`
- `apps/backend/src/insurance_operations/database/models/telephony.py`
- `apps/backend/src/insurance_operations/database/models/lead.py`
- `migrations/versions/20260808_0007_inbound_call_orchestration.py`
- `tests/database/test_telephony_api.py`
- `tests/test_telephony_policy.py`
- the selected provider's official webhook/signature documentation, once selected

## Strongest invariants

- Neon PostgreSQL is the only approved database runtime; no Supabase runtime/auth.
- FastAPI is the authority. Do not place ownership, lifecycle, idempotency, audit, quota, or durable confirmation authority in the browser or provider.
- Require explicit AI disclosure, microphone consent, and synthetic-data acknowledgement before browser Voice authorization.
- Do not persist raw audio. Persist a transcript/intake only after explicit review and confirmation.
- Answer only from active agency-approved FAQ records; fallback/escalate when no unambiguous match exists.
- Never quote, bind, recommend coverage, interpret policy, determine eligibility, or make autonomous insurance decisions.
- Every agency-owned query and mutation must constrain `agency_id`; do not reveal cross-tenant existence.
- Confirmation and handoff creation remain idempotent and transactionally coupled to their durable effects/audit.
- Provider credentials and signing secrets never reach the browser or durable metadata.
- Keep provider payload parsing, signature verification, and provider commands inside concrete adapters. Core schemas/services stay provider-neutral.

See `05-business-and-safety-invariants.md` for code evidence.

## Decisions that must not be guessed

The telephony provider/signature contract, production authentication, billing provider, entitlement rules, notification delivery, retention/deletion policy, deployment platform, production operations, real-customer-data policy, provider region/configuration, and several phone/receptionist/handoff behaviors are **DECISION REQUIRED**. Each is scoped in `08-decisions-and-unknowns.md` and carries the instruction: "Do not implement until owner decides."

## Verification state

Prior reported checks apply only to the snapshots/slices recorded in `09-verification-ledger.md`. They do not establish that the current dirty tree is green. In particular, migration `20260808_0007`, current telephony code, the full migration chain including `0007`, and the combined frontend/backend working tree are **IMPLEMENTED—UNVERIFIED**. No verification command was executed while creating this pack.

## How to use this pack

1. Read this file, then `docs/project-state.md` and `docs/_local/current-session.md`.
2. Use `01` for execution-spine orientation, `02` for flows, `03` for persistence, `04` for route/service contracts, and `05` for invariants.
3. Check `06` before describing status and `09` before claiming verification.
4. Use `07` to select one dependency-ordered slice and `08` to stop at owner-controlled decisions.
5. Follow `10-chatgpt-working-instructions.md` for every implementation response.
6. Reinspect the current working tree and referenced code immediately before any patch; this snapshot will age.
