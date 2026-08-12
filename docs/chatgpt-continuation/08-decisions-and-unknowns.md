# Decisions and Unknowns

## No-assumption rule

Every item in this register is owner-controlled and has status **DECISION REQUIRED**. An interface, placeholder, old roadmap choice, or likely industry default is not a decision.

### 1. Telephony provider and signature contract

- Decision: initial provider, product/API mode, official signature algorithm, signed fields/raw body, timestamp/replay window, callback ordering, sandbox strategy, and credentials.
- Why it matters: determines concrete adapter, ingress route, event mapping, error behavior, and test fixtures.
- Affected modules/files: `telephony/contracts.py`, new provider adapter/ingress, `application.py`, `settings.py`, `.env.example`, telephony tests/docs.
- What can safely proceed: verify/refine provider-neutral `0007`, generic threat model, neutral adapter contract.
- What must stop: concrete provider code, real webhooks/numbers/calls, signature implementation, provider response mapping.
- Current evidence: only `TelephonyAdapter` protocol and development simulation routes exist; no provider is named in current code/config.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 2. Phone disclosure, consent, and confirmation

- Decision: exact AI/call-recording disclosure, jurisdiction handling, consent evidence, whether/how spoken data is reviewed/confirmed, hang-up semantics, and what permits an immutable intake.
- Why it matters: browser confirmation cannot be silently reused for an unattended phone call; it controls lawful/safe persistence.
- Affected modules/files: conversation/telephony schemas, services/models/migrations, adapter prompts/events, safety docs/tests.
- What can safely proceed: signed provider ingress that persists neutral call metadata without transcript/intake.
- What must stop: phone transcript persistence, customer/intake/lead creation, real callers.
- Current evidence: browser has explicit three-part gate and review; telephone has no conversation/intake or consent fields.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 3. Inbound-call behavior

- Decision: answer/reject behavior for unknown/inactive numbers, after-hours flow, voicemail, caller-ID absence, duplicate/out-of-order events, unknown provider events, disconnect recovery, and terminal messaging.
- Why it matters: changes state machine, provider responses, audits, and customer experience.
- Affected modules/files: `telephony/schemas.py`, `service.py:transition_call`, call policy/model/migration, adapter/tests.
- What can safely proceed: current neutral state verification and explicit documentation of existing transitions.
- What must stop: adding new transitions or provider behavior not specified by the selected contract.
- Current evidence: current code implements one policy snapshot and six event types, but product docs describe broader intended phone behavior.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 4. DTMF, silence, interruption, and duration

- Decision: DTMF menu/actions, whether any digit can evidence confirmation, maximum phone duration, warnings, silence thresholds, barge-in/interruption rules, and termination ownership.
- Why it matters: affects safety, call cost, provider event mapping, persistence, and usage.
- Affected modules/files: telephony schemas/service/contracts/models/migrations, call policy, provider adapter, tests.
- What can safely proceed: signed receive and mapping of already-supported lifecycle events.
- What must stop: DTMF/duration/silence implementation and metering based on undefined terminal semantics.
- Current evidence: no DTMF or duration field/event exists; `transfer_ring_timeout_seconds` is only a transfer ring bound, not a call-duration limit.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 5. Transfer side-effect reliability

- Decision: synchronous provider response versus command API, whether transfer commands require durable outbox/jobs, provider idempotency key, retry/reconciliation, and destination governance.
- Why it matters: an external transfer cannot share a database transaction and must not duplicate under retries.
- Affected modules/files: `TelephonyAdapter.request_transfer`, telephony orchestration, possible job/outbox models/worker, audits/tests.
- What can safely proceed: neutral transfer decision and policy-snapshot verification.
- What must stop: wiring real transfer execution.
- Current evidence: core returns `CallAction.TRANSFER`; no code calls the adapter method.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 6. Receptionist behavior

- Decision: phone greeting/disclosure composition, supported languages, pronunciation, interruption style, after-hours phrasing, regulated/sensitive escalation, and whether agency staff may edit system safety text.
- Why it matters: prompt construction and editable settings can affect non-negotiable safety behavior.
- Affected modules/files: receptionist schemas/model/UI, provider prompt/adapter, call policy messages, FAQ fallback, tests/evals.
- What can safely proceed: current bounded agency profile and non-editable safety invariants.
- What must stop: new editable safety/prompt fields, multilingual or phone prompt builder.
- Current evidence: settings store identity/greeting/hours/contact/categories/escalation; current ElevenLabs system prompt is configured externally, not built from settings in backend.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 7. Handoff behavior

- Decision: who can request/acknowledge/complete/cancel, duplicate/open request policy across channels, live-transfer fallback, staff routing/SLA, recipient data, and customer promises.
- Why it matters: controls lifecycle, notifications, roles, and whether a lead is actionable.
- Affected modules/files: `leads/service.py`, lead schemas/models, telephony callback path, future auth/UI/notification modules, tests.
- What can safely proceed: current `0006` API behavior and static documentation; one call-linked callback path after verification.
- What must stop: external delivery, routing automation, browser handoff tool, expanded transitions.
- Current evidence: backend request/status records exist; no delivery, staff role, UI, or provider transfer exists.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 8. Notification delivery mechanism

- Decision: in-app/email/SMS/CRM channel, provider, recipients, content, consent, retry/SLA/dead-letter behavior, and delivery retention.
- Why it matters: determines adapter, outbox, durable jobs, credentials, privacy, and audit.
- Affected modules/files: `notifications/contracts.py`, worker, new models/migrations/services/adapters, lead/telephony transactions, settings/UI/tests.
- What can safely proceed: generic outbox/job architecture only if separately approved and provider-neutral.
- What must stop: notification calls, payload construction, provider dependency, recipient assumptions.
- Current evidence: only an unreferenced `NotificationPort` exists.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 9. Production authentication and authorization

- Decision: auth provider/protocol, web session/token model, invitations, agency creation, roles/permissions, tenant switching, account recovery, machine identities, and revocation.
- Why it matters: every current business route uses a deterministic development actor; real tenancy cannot rely on it.
- Affected modules/files: `actors.py`, identity models/migrations, `application.py`, settings, web session layer, all route tests/docs.
- What can safely proceed: development-only backend slices that remain hidden and synthetic.
- What must stop: production routes, real tenants/data, role-specific UI, billing/account management.
- Current evidence: identity/membership tables exist; no production credential validation exists; Supabase auth was explicitly removed.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 10. Billing provider

- Decision: billing provider, merchant/account model, supported regions/currencies/taxes, webhook verification, customer mapping, refunds/cancellation, and reconciliation.
- Why it matters: fixes provider adapter and financial event model.
- Affected modules/files: future billing adapters/models/migrations/routes/worker, settings, auth/onboarding, UI/tests.
- What can safely proceed: provider-neutral usage measurement after usage definitions are approved.
- What must stop: billing integration, checkout, webhook code, financial status claims.
- Current evidence: no billing code; ElevenLabs account guard is only a development cost-safety checklist.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 11. Entitlement and quota rules

- Decision: plans/features, included units, concurrency/daily/monthly limits, trial/grace/suspension behavior, overage, resets, admin overrides, and usage-to-entitlement mapping.
- Why it matters: backend enforcement and user-visible access depend on exact business rules.
- Affected modules/files: conversation/telephony admission services, future usage/billing/entitlement models, auth, UI/tests.
- What can safely proceed: current development safety quotas and a provider-neutral raw usage ledger after metering units are decided.
- What must stop: subscription enforcement, plan limits, pricing UI.
- Current evidence: fixed/configurable development admission limits exist; no plan or entitlement records exist.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 12. Usage and cost semantics

- Decision: meter units, start/end timestamps, rounding, abandoned/failed sessions, provider cost fields, corrections, reconciliation, retention, and reporting precision.
- Why it matters: a ledger built before lifecycle definitions could encode incorrect billable facts.
- Affected modules/files: new usage model/service/migration, conversation/telephony terminal paths, provider adapters, billing/analytics/tests.
- What can safely proceed: current admission count enforcement.
- What must stop: durable metering and billing calculations.
- Current evidence: no usage table; calls/sessions have some timestamps but phone duration termination is absent.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 13. Retention, deletion, export, and correction

- Decision: per-record retention, provider retention, transcript/customer/audit/idempotency/usage/outbox deletion, legal holds, exports, immutable-record correction/tombstones, and account closure.
- Why it matters: current confirmed intakes are immutable and otherwise indefinite; FKs restrict deletion.
- Affected modules/files: all models/migrations/services, worker/jobs, provider setup, account/customer APIs, audit/operations docs/tests.
- What can safely proceed: synthetic development only with shortest external retention and no raw audio.
- What must stop: real data, production deletion/export claims, retention automation.
- Current evidence: no retention/deletion workflow; idempotency expiry is recorded but no cleanup job exists; provider checklist requests shortest retention.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 14. Real-customer-data policy

- Decision: allowed data classes, prohibited sensitive data, privacy notice/consent, vendor/legal/security reviews, incident handling, support access, and pilot gate.
- Why it matters: current controls explicitly authorize synthetic data only and cannot detect all real/sensitive input.
- Affected modules/files: frontend disclosure, provider prompts/settings, auth, retention/export/delete, logging/observability, operations/security docs/tests.
- What can safely proceed: fictional/synthetic development fixtures only.
- What must stop: real numbers, real callers, real customer/policy data, production compliance claims.
- Current evidence: synthetic acknowledgement/prompt/seed exist; ZRM absence expressly blocks production/real data.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 15. Voice/provider region and configuration

- Decision: ElevenLabs workspace region, LLM/STT/TTS/voice, subprocessors, ZRM availability, retention/audio settings, fallback policy, billing guard, and acceptable live-evaluation evidence.
- Why it matters: provider behavior/privacy/cost cannot be proven from repository code.
- Affected modules/files: `docs/elevenlabs-agent-setup.md`, provider dashboard, settings/env flags, Voice manual/eval ledger.
- What can safely proceed: code inspection and disabled synthetic development configuration.
- What must stop: enabling flags without checklist; real data; production claims.
- Current evidence: code requires `ELEVENLABS_PRIVACY_CONFIRMED`; repository cannot inspect dashboard state.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 16. Deployment platform and regions

- Decision: web/API/worker/database regions/platforms, domains/TLS/networking, secrets, build/release model, migration execution, staging/prod separation, and rollback.
- Why it matters: shapes runtime configuration, latency, security, and release operations.
- Affected modules/files: CI/CD, platform manifests, settings, health/readiness, migration/runbooks, provider callbacks.
- What can safely proceed: local/CI-compatible code and platform-neutral process entry points.
- What must stop: deployment manifests and claims tied to an assumed platform; live provider webhook URLs.
- Current evidence: historical docs named platforms but current tree has no active deployment configuration and the old choice was part of superseded architecture.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 17. Production operational requirements

- Decision: SLOs, monitoring/logging/tracing, alerting/on-call, backups/RPO/RTO, restore drills, provider outage policy, rate limiting/abuse, incident response, support/admin access, and release approvals.
- Why it matters: determines hardening, observability, recovery, and whether deployment is supportable.
- Affected modules/files: API/worker middleware, jobs, CI/CD, platform config, runbooks/tests.
- What can safely proceed: correlation IDs, sanitized errors, health/readiness, local failure tests.
- What must stop: production-readiness claims and operationally sensitive rollout.
- Current evidence: only basic health/readiness/correlation/CI exist; no production observability or recovery system.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

### 18. Document AI priority, storage, and providers

- Decision: whether/when to resume Document AI, current scope/acceptance, private storage provider, OCR/parser/model evaluation, approval/correction rules, and policy versioning.
- Why it matters: the old roadmap was superseded in execution order and its Supabase/storage/provider assumptions are not current decisions.
- Affected modules/files: future document/storage/job/evaluation/review/policy modules; worker; migrations; frontend; current roadmap docs.
- What can safely proceed: preserve historical context and build reusable durable jobs only when independently required/approved.
- What must stop: implementing deleted PDF requirements as current requirements.
- Current evidence: no document upload/OCR/review code; historical specifications only.
- Status: DECISION REQUIRED.

**Do not implement until owner decides.**

## Evidence conflicts and stale narratives

CONFLICT:
- source A: `docs/project-state.md` says the current implementation remains a development-only synthetic browser Voice foundation.
- source B: the working tree also contains `0007` telephony models/services/development simulation routes.
- repository evidence: telephony code exists but has no provider and is unverified; it does not constitute a real phone runtime.
- impact: “browser foundation” understates code present, while “inbound telephone support” would overstate actual capability.
- recommended resolution: describe it as an unverified provider-neutral telephony orchestration foundation, not real telephone support.
- owner decision required: no

CONFLICT:
- source A: the final paragraph of `docs/ai-receptionist-product-plan.md` says the first implementation slice is product presentation plus receptionist settings.
- source B: the same document and current session mark settings, FAQ, and lead/handoff slices as implemented/owner-verified and put `0007` verification next.
- repository evidence: those later modules and migrations exist.
- impact: a future agent could repeat already-delivered settings work.
- recommended resolution: treat that paragraph as historical sequencing; use `00-START-HERE.md` and `07-remaining-build-plan.md` for current order.
- owner decision required: no

CONFLICT:
- source A: `README.md` says only confirmation persists the transcript and creates a customer.
- source B: `ConversationService.confirm_intake` also creates an `AgencyLead`, and the response includes `lead_id`.
- repository evidence: `conversations/service.py` inserts `AgencyLead` in the confirmation transaction.
- impact: README understates a durable side effect; callers must account for lead creation/idempotency.
- recommended resolution: update README in a later documentation cleanup after this pack review; do not change behavior.
- owner decision required: no

CONFLICT:
- source A: `docs/_local/current-session.md` records an interrupted FAQ integration test during migration downgrade.
- source B: the same session/project-state also says the owner reported clean FAQ migration/static/focused/drift checks.
- repository evidence: no exact command log, commit, or chronological snapshot is stored to prove whether clean results occurred before or after the interrupted run; the test database may still require restoration.
- impact: do not infer current DB state or current full FAQ verification from the narrative alone.
- recommended resolution: inspect/restore the disposable test DB, rerun the current verification set when authorized, and record exact snapshot/commands.
- owner decision required: no

CONFLICT:
- source A: telephony documentation has a ten-item manual contract checklist covering validation, routing, limits, replay, transfer/callback, and storage/log safety.
- source B: `tests/database/test_telephony_api.py` currently contains one broad integration test and `tests/test_telephony_policy.py` contains one availability test.
- repository evidence: migration tests add structural assertions, but dedicated automated coverage does not separately exercise every documented manual case.
- impact: passing the existing focused tests would not by itself prove every documented acceptance condition.
- recommended resolution: perform the manual checklist at Gate 0, then add focused automated cases as part of backend hardening without changing behavior accidentally.
- owner decision required: no
