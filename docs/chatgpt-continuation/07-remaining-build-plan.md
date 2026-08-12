# Remaining Build Plan

## Historical Release 1 roadmap

The original approved Release 1 roadmap contained 21 phases, Phase 0 through Phase 20. Its source PDF and related Release 1 PDFs are tracked at HEAD but deleted in the current working tree; they were inspected from commit `7f2f505` for historical continuity.

| Phase | Original phase name |
|---:|---|
| 0 | Final decisions and project preparation |
| 1 | Repository and engineering guardrails |
| 2 | Local development and environment foundation |
| 3 | Database migrations and core domain foundation |
| 4 | Authentication and authorization |
| 5 | Application shell, customer workflow, and basic UI system |
| 6 | Private Storage and signed upload flow |
| 7 | PostgreSQL job queue and worker foundation |
| 8 | Provider-neutral candidate fixture, benchmark corpus, and evaluation harness |
| 9 | Parser, OCR, model, and input-strategy evaluation spike |
| 10 | Provider-selection gate |
| 11 | Approved live Document AI pipeline |
| 12 | Candidate, evidence, validation, and warning publication |
| 13 | Review Queue and Human Review Workspace |
| 14 | Approval and immutable policy versions |
| 15 | Technical Retry, Reprocessing, Correction Review, and concurrency |
| 16 | Audit, usage controls, and acknowledgement email |
| 17 | Stored Results and isolated demo sessions |
| 18 | Security, observability, cleanup, and failure recovery |
| 19 | End-to-end testing and deployment |
| 20 | Loom-ready visual polish and public-demo release |

This is historical planning context, not the current execution order.

## Owner-approved deviations

1. The deleted `docs/implementation-backlog.md` explicitly recorded an owner-approved deviation to build browser Voice AI before Document AI. Generic conversation persistence, ElevenLabs WebRTC, consent/review/confirmation, and customer persistence were moved ahead of upload/jobs/OCR/evaluation.
2. The historical roadmap selected Supabase PostgreSQL/Auth/Storage and deployment platforms. The current owner decision removed Supabase runtime/auth and established Neon PostgreSQL only; production authentication and deployment were deferred to new decisions.
3. The product expanded from a document-policy workflow into an AI receptionist/front-desk product. Receptionist settings, approved FAQs, lead capture, handoff, and inbound-call orchestration were added after the original roadmap, which had intentionally excluded Voice AI, telephony, and billing from Release 1.
4. After the initial receptionist/FAQ surfaces, the owner froze further frontend work until backend browser/telephone contracts are stable. The final operations UI is therefore later than the early UI phase implied by the original plan.
5. Current owner-reported progress verifies the backend through the `0006` lead/handoff slice. The `0007` inbound-call foundation exists but remains unverified. This code state, not an old phase number, determines the next work.

CONFLICT:
- source A: original Release 1 phases prioritize private document storage, jobs, Document AI, review, and policy approval; they exclude Voice/telephony/billing.
- source B: current product and session docs prioritize an AI receptionist, Voice, leads/handoffs, then telephony while Document AI remains deferred.
- repository evidence: Voice/receptionist/FAQ/lead code exists; no upload/job/OCR/review implementation exists; telephony `0007` exists unverified.
- impact: treating the historical phase list as current would abandon the active product midway and invent dependencies that current code does not satisfy.
- recommended resolution: preserve the list as history and use the dependency-ordered plan below unless the owner explicitly reprioritizes.
- owner decision required: no

## Assessment of the current-session expected direction

The expected backend direction—concrete signed adapter, normalized provider events, DTMF/duration controls, and usage metering—is directionally valid but not sufficient as a direct sequence.

Repository evidence changes the immediate order:

1. `0007` and its tests have not been run; the disposable test database may be mid-downgrade. Verification/restoration is the first gate.
2. A concrete adapter cannot be selected without the telephony provider and signature/replay contract. That is **DECISION REQUIRED**.
3. Neutral event storage exists, but provider payload normalization does not; normalization belongs in the same initial signed-ingress slice as the adapter.
4. The current telephone flow cannot answer FAQs through a phone session or create a new confirmed intake/lead. It can only link an existing browser-created lead. The channel-neutral phone conversation/intake bridge must be designed before claiming telephone receptionist behavior.
5. DTMF and duration control should follow a verified provider event/command boundary. Usage metering should follow stable lifecycle/duration semantics so it does not meter ambiguous events.

## Current dependency-ordered plan

Every implementation slice remains IMPLEMENTED—UNVERIFIED until the owner reports its checks. Commands below are recommendations, not commands run during this audit.

### Gate 0 — Restore and verify the current `0007` slice

- Objective: establish a trustworthy database/test baseline for code already present.
- Why next: new work on an unknown migration/database state would compound failures and make status claims unreliable.
- Existing prerequisites: static chain through `0007`, telephony models/service/routes/tests, owner-confirmed disposable test URL.
- Files involved: `docs/inbound-call-backend.md`; `tests/database/conftest.py`; migration `0007`; telephony models/service/tests; migration/ownership tests.
- Contracts/invariants: never downgrade a non-disposable database; no real callers/numbers; no raw audio/secrets.
- Acceptance: owner confirms test DB state, upgrade/current/check pass, focused and full Python checks pass, database is restored to head, and manual contract checklist is recorded against a named snapshot.
- Targeted verification: use the exact commands under “Owner Verification” in `docs/inbound-call-backend.md`, including Ruff, mypy, focused pytest, full pytest, and Alembic current/check. Run nothing until `TEST_DATABASE_URL` is explicitly confirmed disposable.
- Manual QA: the ten checks in that document, including replay/limits/transfer/callback and database/log inspection.
- Exclusions: application changes, real provider configuration, frontend changes.
- Owner decisions: none beyond confirming the test target and authorizing execution.
- Status: IMPLEMENTED—UNVERIFIED.

### Gate 1 — Decide the initial telephony provider and phone contract

- Objective: select provider, account region, webhook signature/timestamp/replay rules, synchronous response vs command API, test credentials/environment, and the minimum phone disclosure/consent/confirmation behavior.
- Why next: concrete parsing, signature code, responses, transfer calls, and tests are provider-defined; phone persistence semantics affect the shared bridge.
- Existing prerequisites: `TelephonyAdapter`, neutral models/state machine, current safety rules.
- Files involved: `telephony/contracts.py`; `docs/inbound-call-backend.md`; `08-decisions-and-unknowns.md`; selected provider official documentation.
- Contracts/invariants: raw-body verification before parsing; provider credentials server-only; agency derived from called number; core remains neutral; no silent provider fallback.
- Acceptance: owner records an explicit provider/region/signature/replay/command decision and phone disclosure/confirmation boundary.
- Targeted verification: no code command; documentation review against official provider docs and threat model.
- Manual QA: confirm provider can enforce required privacy/audio controls and test-number isolation.
- Exclusions: implementation or account mutation before decision.
- Owner decisions: telephony provider and phone data/consent contract. **Do not implement until owner decides.**
- Status: DECISION REQUIRED.

### Slice 1 — Concrete signed telephony adapter and normalized ingress

**This is the ONE next highest-leverage implementation slice after Gates 0 and 1.**

- Objective: implement one provider adapter; verify raw signed requests and replay window; normalize provider receive/lifecycle callbacks into existing neutral inputs; wire a provider-only ingress route without exposing development simulation routes.
- Why next: it converts the neutral `0007` foundation into a real, authenticated boundary while keeping business state in `TelephonyService`.
- Existing prerequisites: verified `0007`, selected provider contract, active-number lookup, neutral state/dedupe.
- Likely files: new `telephony/providers/<provider>.py`; `telephony/contracts.py`; a provider ingress module or carefully isolated route in `application.py`; `settings.py`; `.env.example` names only; new provider adapter/route tests; existing telephony service/tests.
- Contracts/invariants: verify signature/timestamp on raw bytes before parsing; never accept agency ID/actor from payload; sanitize errors/metadata; idempotently map provider call/event IDs; no credentials in browser/database/audit/logs; no external side effect inside a DB transaction.
- Acceptance: invalid/expired/tampered/replayed signatures fail before mutation; valid duplicate callbacks replay safely; every supported provider event maps to one neutral event; unknown events fail safely or are explicitly ignored/audited by approved policy; called number resolves tenant; existing simulation API remains development-only.
- Targeted verification: Ruff format/check, mypy, new adapter unit tests, new ingress API tests, existing `tests/test_telephony_policy.py` and `tests/database/test_telephony_api.py`, migration/ownership tests, then full Python suite and Alembic check.
- Manual QA: provider sandbox signed request; tampered body/header/time; duplicate callback; unknown event; redacted logs; no mutation on verification failure.
- Exclusions: DTMF, phone transcript/intake, duration/metering, notification delivery, frontend, real customer calls.
- Owner decisions: Gate 1. If provider behavior requires asynchronous commands/outbox, stop and approve that boundary first.
- Status: DECISION REQUIRED until Gate 1, then NOT IMPLEMENTED.

### Slice 2 — Channel-neutral phone conversation, FAQ, and confirmation contract

- Objective: define and implement how an authenticated inbound call obtains safe FAQ answers and becomes a confirmed intake without weakening browser confirmation semantics.
- Why next: current telephony can only return directives and link an existing lead; it is not yet a receptionist workflow.
- Existing prerequisites: signed normalized ingress; approved FAQ service; immutable browser intake/lead transaction.
- Likely files: conversation/FAQ/telephony services and schemas; conversation/telephony/lead models; a forward migration; adapter orchestration; focused database/API tests; current feature docs.
- Contracts/invariants: approved FAQ only; no raw audio; explicit phone disclosure/consent; defined transcript confirmation; customer/intake/lead/audit commit together; provider-neutral channel model; cross-tenant absence hidden.
- Acceptance: a phone session can use the same core FAQ matcher and create at most one explicitly authorized immutable intake/lead; retries cannot duplicate business records; browser flow remains unchanged.
- Targeted verification: Ruff/mypy; focused FAQ/conversation/telephony/migration/ownership tests; new phone confirmation/idempotency/safety tests; full Python suite; Alembic upgrade/downgrade/current/check on disposable DB.
- Manual QA: matched/unmatched/prohibited questions; correction/confirmation; hang-up before confirmation; replay; sensitive/real-data refusal; database/log inspection.
- Exclusions: DTMF shortcuts, UI, notification provider, billing.
- Owner decisions: exact phone disclosure, consent, transcript confirmation, caller contact capture, hang-up semantics, and retention. **Do not implement until owner decides.**
- Status: DECISION REQUIRED.

### Slice 3 — Provider call-control and transfer execution

- Objective: convert neutral `CallAction` directives into safe provider answer/continue/transfer/end behavior with deterministic callback reporting.
- Why next: real transfer cannot be claimed merely because the service returns a destination.
- Existing prerequisites: signed adapter/ingress; provider command semantics; verified neutral state machine.
- Likely files: provider adapter/orchestrator; `telephony/contracts.py`; telephony service/event mapping; outbox/job files if commands are asynchronous; tests.
- Contracts/invariants: no side effects inside domain transaction; provider command idempotency; destination from policy snapshot only; bounded ring timeout; callback failure normalization; audited but credential-free outcomes.
- Acceptance: each transfer intent causes at most one provider command; success/failure callbacks drive legal transitions; retries/restarts reconcile without duplicate transfers.
- Targeted verification: adapter command unit tests, database idempotency/reconciliation tests, existing telephony tests, Ruff/mypy/full suite.
- Manual QA: sandbox answer, open-hours transfer, no-answer/failure fallback, duplicate callbacks, process interruption.
- Exclusions: external handoff notification, DTMF, billing/UI.
- Owner decisions: synchronous response versus durable command/outbox and transfer destination governance. **Do not implement until owner decides.**
- Status: DECISION REQUIRED.

### Slice 4 — DTMF, silence/interruption, and telephone duration controls

- Objective: extend neutral events/policy with bounded DTMF semantics, silence/interruption outcomes, and enforced maximum call duration.
- Why next: these controls depend on stable provider event/command mapping and phone lifecycle.
- Existing prerequisites: Slices 1–3.
- Likely files: telephony schemas/service/contracts/models; forward migration; provider adapter mappings; settings/policy API; tests; docs.
- Contracts/invariants: neutral event names; no provider fields in core; explicit legal state transitions; provider/server duration defense in depth; never treat DTMF as consent unless owner explicitly defines it.
- Acceptance: allowed digits/actions are finite; invalid/replayed input is safe; maximum duration terminates once and records a normalized outcome; silence/disconnect cannot create a confirmed intake accidentally.
- Targeted verification: focused state-machine/unit/provider/database tests, migration/ownership checks, Ruff/mypy/full suite.
- Manual QA: repeated/out-of-order DTMF, silence timeout, exact duration boundary, provider disconnect/race.
- Exclusions: usage billing calculations and frontend controls.
- Owner decisions: DTMF menu/actions, duration value, silence thresholds, interruption/callback messaging. **Do not implement until owner decides.**
- Status: DECISION REQUIRED.

### Slice 5 — Durable usage metering

- Objective: add an append-only, idempotent provider-neutral usage ledger for browser/phone sessions, duration, and selected cost/reconciliation dimensions.
- Why next: stable lifecycle and duration events are required before defining chargeable units.
- Existing prerequisites: verified Voice/phone terminal semantics and normalized provider identifiers.
- Likely files: new usage model/service/schema/migration; conversation/telephony terminal paths; provider metadata adapters; tests; project state.
- Contracts/invariants: append-only; agency-owned; no raw content; natural event dedupe; transactionally record internal usage; reconcile provider totals separately; quotas remain backend-owned.
- Acceptance: every accepted unit records once under replay/race; adjustments are new records, not mutation; reports separate internal measures/provider costs/entitlements.
- Targeted verification: migration/immutability/idempotency/concurrency tests, focused service tests, Ruff/mypy/full suite/Alembic check.
- Manual QA: duplicate terminal callbacks, missing provider cost, reconciliation mismatch, boundary durations.
- Exclusions: invoicing, plan enforcement, UI charts.
- Owner decisions: billable units, rounding, provider cost retention, reconciliation and retention. **Do not implement until owner decides.**
- Status: DECISION REQUIRED.

### Slice 6 — Durable jobs/outbox and notification delivery

- Objective: implement durable job claiming/retry and an outbox for handoff notifications, then one approved delivery adapter.
- Why next: external delivery must survive process failure and must not occur inside lead/call transactions.
- Existing prerequisites: stable handoff events and production-grade worker loop; notification mechanism decision.
- Likely files: worker runtime; new job/outbox/delivery models/migrations/services; `notifications/contracts.py`; lead/telephony handoff transaction; adapter; tests.
- Contracts/invariants: outbox row committed with handoff; lease/attempt/backoff/dead-letter; idempotent provider send/reconcile; payload built in adapter; credentials/content minimized.
- Acceptance: crash/retry cannot lose or duplicate a logical notification; delivery state/audit is queryable; recipient selection is tenant-safe.
- Targeted verification: migration/claim concurrency/retry/idempotency tests, worker tests, adapter unit tests, Ruff/mypy/full suite/worker check/Alembic check.
- Manual QA: worker crash before/after send, provider timeout, invalid recipient, retry exhaustion, redacted logs.
- Exclusions: multiple channels/CRM unless separately approved; billing/UI.
- Owner decisions: in-app/email/SMS/CRM mechanism, provider, recipients, retry/SLA/content. **Do not implement until owner decides.**
- Status: DECISION REQUIRED.

### Slice 7 — Backend safety and evaluation hardening

- Objective: close contract/failure/evaluation gaps across browser and phone before resuming UI.
- Why next: both channel paths and side effects must be stable before final surfaces.
- Existing prerequisites: completed backend channel/delivery slices.
- Likely files: all focused tests; new evaluation fixtures/harness; error/audit/ownership tests; CI; safety docs.
- Contracts/invariants: no insurance decisions; approved FAQ provenance; no raw audio/secrets; ownership/idempotency/transaction correctness; bounded failure behavior.
- Acceptance: explicit evaluation corpus covers prohibited/unsupported/ambiguous/sensitive prompts and provider failure/replay cases; all acceptance gates have recorded evidence.
- Targeted verification: complete web/Python/static/migration suites plus deterministic eval command to be introduced; worker check.
- Manual QA: live sandbox browser/phone matrix and database/log/privacy dashboard inspection.
- Exclusions: production real data and final visual polish.
- Owner decisions: evaluation thresholds and release gates. **Do not implement threshold-dependent release logic until owner decides.**
- Status: PARTIAL because scattered tests exist; cohesive evaluation is NOT IMPLEMENTED.

### Slice 8 — Production authentication and agency onboarding

- Objective: replace development actor resolution with authenticated identity, invitation/onboarding, roles, and tenant-safe production dependencies.
- Why next: production UI, data, billing, and provider routes require real identity/authorization.
- Existing prerequisites: current identity/membership tables and stable backend contracts.
- Likely files: auth adapter/protocol, settings, actor dependencies, identity models/migrations, application routes, web session integration, tests/docs.
- Contracts/invariants: no Supabase unless owner reverses architecture; backend verifies credentials and derives tenant/role; provider callbacks use separate machine auth; deny by default.
- Acceptance: invitation/account/session lifecycle and role/tenant tests; development actor cannot appear in production; cross-tenant matrix passes.
- Targeted verification: auth unit/integration/security tests, Ruff/mypy/web verify/full suite/migration check.
- Manual QA: invite/login/logout/expiry/revocation/role/cross-tenant attempts.
- Exclusions: billing provider and real-customer enablement.
- Owner decisions: authentication provider/protocol, session design, roles, onboarding. **Do not implement until owner decides.**
- Status: DECISION REQUIRED.

### Slice 9 — Final operations frontend

- Objective: build stable API-backed lead inbox/detail/handoff, call policy/number/call operations, and status/error/accessibility surfaces.
- Why next: frontend freeze ends only after backend contracts and auth are stable.
- Existing prerequisites: Slices 1–8 as applicable; owner-approved UX scope.
- Likely files: new `apps/web/src/app/*` routes and typed feature modules; shared styles/components; API parsers/tests.
- Contracts/invariants: no business authority in UI; optimistic versions/idempotency preserved; secrets absent; explicit status/error/accessibility states.
- Acceptance: browser and phone leads are visible/actionable; handoff and call administration match backend; no hidden hardcoded tenant/provider data.
- Targeted verification: focused Vitest tests and `npm run verify:web`; backend contract tests.
- Manual QA: responsive/accessibility/error/stale-version/replay flows across supported browsers.
- Exclusions: speculative dashboard analytics, billing/document UI unless approved.
- Owner decisions: final IA/roles/visual acceptance. **Do not implement final scope until owner decides.**
- Status: PARTIAL because only home/Voice/settings/FAQ surfaces exist.

### Slice 10 — Retention, deletion, privacy, and real-data gate

- Objective: define and implement data lifecycle, export/deletion, provider controls, security/observability, and a formal real-data enablement gate.
- Why next: production authentication/UI alone does not authorize real customer data.
- Existing prerequisites: stable domains/auth/deployment design and legal/operational decisions.
- Likely files: retention services/jobs/migrations; account/customer APIs; provider config checks/docs; audit/export; operations runbooks/tests.
- Contracts/invariants: immutable records require correction/tombstone policy, not silent mutation; raw audio remains disabled; tenant-scoped export/delete; logs/content minimized.
- Acceptance: owner-approved retention matrix and deletion/export behavior verified; provider privacy/region/subprocessor controls recorded; synthetic gate cannot be bypassed accidentally.
- Targeted verification: retention clock/job, export/ownership, deletion/FK, provider-config, security and recovery tests; full suites.
- Manual QA: account closure/export/deletion/recovery and provider-dashboard review.
- Exclusions: real pilot before gate passes.
- Owner decisions: all retention/deletion/legal/real-data requirements. **Do not implement until owner decides.**
- Status: DECISION REQUIRED.

### Slice 11 — Billing and entitlements

- Objective: add provider-neutral subscription/entitlement state, signed billing callbacks, idempotent reconciliation, and backend enforcement.
- Why next: depends on production tenants/auth and durable usage semantics.
- Existing prerequisites: Slices 5, 8, and deployment/operations foundation.
- Likely files: billing adapter/contracts, models/migrations/services/routes, webhook ingress, quota checks, worker/outbox, frontend billing surfaces, tests.
- Contracts/invariants: backend authority; signed/idempotent callbacks; provider isolation; entitlement changes audited; no browser trust.
- Acceptance: replay/order/failure/cancellation/grace-period behaviors match owner rules; usage and entitlement concepts remain distinct.
- Targeted verification: provider adapter/webhook/idempotency/state-machine/ownership tests, full suites/migrations/web verify.
- Manual QA: sandbox purchase/renew/fail/cancel/refund/replay.
- Exclusions: unsupported pricing experiments.
- Owner decisions: provider, plans, trial/grace/refund/limits. **Do not implement until owner decides.**
- Status: DECISION REQUIRED.

### Slice 12 — Deployment and operations release gate

- Objective: production environments, secrets, networking, migrations, rollout/rollback, monitoring, backup/recovery, cleanup, and incident runbooks.
- Why next: deploy only after the selected production capabilities and data policy are explicit.
- Existing prerequisites: production auth, provider adapters, privacy controls, approved platform.
- Likely files: platform manifests/config, CI/CD, health/readiness/observability, migration/release scripts, operations docs.
- Contracts/invariants: separate service identities; secrets server-side; migrations controlled; rollback does not corrupt immutable/idempotent state; no real data before gate.
- Acceptance: staging release/rollback/recovery and secret/network checks pass; monitoring alerts are actionable.
- Targeted verification: platform-specific pipeline plus all repository checks, migration preflight, smoke and recovery exercises.
- Manual QA: staging browser/phone flows, failed deploy/rollback, DB restore, provider outage.
- Exclusions: provider/platform chosen by assumption.
- Owner decisions: deployment platform/regions/SLOs/on-call/backups. **Do not implement until owner decides.**
- Status: DECISION REQUIRED.

### Slice 13 — Deferred Document AI roadmap

- Objective: resume the original document upload/jobs/evaluation/provider-selection/pipeline/review/approval sequence only after owner reprioritization.
- Why last in the current plan: no current implementation exists and the owner moved the receptionist/Voice product ahead of it.
- Existing prerequisites: decisions for storage, authentication, durable jobs, retention, provider evaluation, and product scope.
- Likely files: entirely new storage/document/job/candidate/evidence/review/policy-version modules, migrations, worker handlers, web surfaces, evaluation fixtures/tests.
- Contracts/invariants: evidence-backed extraction, human approval, immutable versions, correction/reprocessing, no autonomous insurance decision.
- Acceptance: must be re-derived from current owner-approved product specification; do not treat deleted historical PDFs as automatically current requirements.
- Targeted verification: phase-specific evaluation, migration, worker, API, UI, security, and end-to-end suites to be designed.
- Manual QA: upload/extraction/evidence/review/approval/retry/correction flows using approved fixtures.
- Exclusions: implementation from historical assumptions.
- Owner decisions: whether/when Document AI returns, storage/provider/scope/acceptance. **Do not implement until owner decides.**
- Status: DECISION REQUIRED.
