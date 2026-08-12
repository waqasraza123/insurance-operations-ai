# Business and Safety Invariants

An invariant may be approved in documentation, mechanically enforced in code/database, or both. This file states the difference. Prompt/UI copy is not treated as equivalent to backend enforcement.

## Platform and authority

| Invariant | Documentation evidence | Code evidence and enforcement | Status |
|---|---|---|---|
| Neon PostgreSQL only | `docs/project-state.md`; `README.md`; `docs/database-setup.md` | `settings.py:DatabaseSettings` accepts PostgreSQL URLs and validates Neon-safe SSL/pooling; `database/connection.py`; SQLAlchemy/psycopg/Alembic dependencies. | VERIFIED for the recorded foundation snapshot |
| No Supabase runtime or authentication | Current project state explicitly supersedes the historical Supabase choice | No Supabase package, client, runtime settings, or auth resolver exists; actor is `resolve_development_actor`. | VERIFIED as an architecture fact in the current tree |
| Backend authority | Project-state/AI-receptionist plan require backend-owned rules | FastAPI resolves actor; services scope ownership, validate transitions, enforce quotas/idempotency, and own transactions. Browser feature modules only call routes and manage ephemeral UI state. | PARTIAL — development authority exists; provider webhook and production actor paths do not |
| Do not trust the provider as system of record | Provider-isolation decisions in current docs | `ConversationProvider` returns only authorization; `ConversationService` owns state. `TelephonyAdapter` protocol is separate from `TelephonyService`. | PARTIAL — Voice boundary exists; telephony integration does not |

Historical Release 1 documents selected Supabase PostgreSQL/Auth/Storage. That is superseded, not an alternative current architecture. Do not reintroduce it without an explicit owner reversal.

## Data and consent boundaries

| Invariant | Code evidence | Enforcement caveat | Status |
|---|---|---|---|
| Synthetic data only in development | `ConversationSessionCreateInput.synthetic_data_acknowledged`; `ConversationService.authorize_session`; Voice checkbox/copy in `voice-test.tsx`; synthetic seed; `docs/elevenlabs-agent-setup.md` prompt | Backend records acknowledgement but cannot determine whether typed/spoken content is real. No real-data policy or automated sensitive-data filter exists. | PARTIAL |
| Explicit AI disclosure | `ai_disclosure_accepted` is required before session creation and timestamped in `ConversationSession.disclosure_accepted_at`; Voice UI requires checkbox | Wording/legal adequacy and telephone disclosure are not implemented/verified. | VERIFIED for development browser gate; telephony NOT IMPLEMENTED |
| Explicit microphone consent | `microphone_consent_granted` required and timestamped before provider token issuance; browser checkbox precedes `client.start` | Browser sends all three booleans as true only after local UI gating; telephone consent rules are unresolved. | VERIFIED for development browser gate |
| Explicit confirmation before durable derived data | Browser ends into review, allows edits, then calls confirmation; service requires owned REVIEW_PENDING session; DB stores only confirmed transcript | Provider-side retention remains an external dashboard control; no phone confirmation design exists. | VERIFIED for recorded browser snapshot; phone path DECISION REQUIRED |
| No raw-audio retention | No model, migration, schema, service, or frontend upload path stores audio; setup doc requires provider audio saving disabled | Repository inspection cannot prove external provider settings or logs. No runtime assertion can prevent a provider account from retaining audio. | PARTIAL |
| Draft transcript stays ephemeral | `VoiceTest` keeps `transcript` and form in React state; `submit_intake_draft` says no data saved; `ConversationSession` has no draft/transcript column | Browser memory and provider processing are not a formal retention guarantee; provider dashboard must be checked. | IMPLEMENTED—UNVERIFIED current snapshot |
| Confirmed transcript retention | `ConversationIntake.confirmed_transcript` is inserted only in `confirm_intake`; database immutability trigger prevents mutation/deletion | There is no application retention/deletion schedule or customer deletion workflow; the record is effectively indefinite until policy/implementation exists. | PARTIAL; retention policy is DECISION REQUIRED |
| Never store secrets or sensitive content in notes/code | AGENTS instructions, setup docs, `.gitignore`/env pattern | `SecretStr` protects configured key display; adapters use server settings; this audit did not copy env values. Preventing all accidental logs/content requires operational review. | PARTIAL |

## Insurance and answer safety

The approved product boundary is: no quotes, advice, binding, coverage verification/recommendation, eligibility/underwriting/claims decisions, or autonomous insurance decisions. Unsupported/regulatory requests go to a licensed human.

Evidence:

- `docs/project-state.md` and `docs/ai-receptionist-product-plan.md` state the boundary.
- `docs/elevenlabs-agent-setup.md` provides the required provider prompt and requires a human escalation.
- `voice-test.tsx` discloses that the assistant cannot quote, advise, bind/verify coverage, or make decisions.
- Synthetic receptionist seed escalation and quote FAQ direct the user to a licensed team member.
- FAQ code can return only a stored active approved answer or escalation fallback.

Enforcement assessment:

| Invariant | Mechanical evidence | Status |
|---|---|---|
| Agency-specific answers must come from approved FAQs | `ApprovedFaqService._lookup` filters active rows; deterministic strong/non-ambiguous matching; `conversation_lookup` verifies active owned session; ElevenLabs prompt/tool contract requires the lookup. | PARTIAL — backend lookup is enforced when called, but no backend control guarantees the LLM always calls it or speaks the returned answer verbatim |
| No hallucinated fallback | Weak/ambiguous/no match returns receptionist escalation; Voice wrapper fails closed on API error. | IMPLEMENTED—UNVERIFIED current aggregate; FAQ slice owner-reported VERIFIED |
| No quoting | Documentation/prompt/UI/seed only; no quote endpoint/model/calculation exists. | PARTIAL — absence of quote code is strong, but arbitrary provider speech is prompt-governed rather than backend-filtered |
| No binding | No binding model/route/service; prompt/UI prohibit it. | PARTIAL for the same reason |
| No coverage recommendations or verification | No recommendation/coverage engine; prompt/UI prohibit it. | PARTIAL for the same reason |
| No autonomous underwriting/eligibility/claims/insurance decisions | No such models/routes/services; prompt prohibits them. | PARTIAL for the same reason |
| Human escalation | Receptionist settings require an escalation message; unmatched FAQ returns it; handoff request records exist. | PARTIAL — no Voice handoff tool/UI, provider transfer, or delivery exists |

Do not claim the product is mechanically compliant merely because the provider prompt contains restrictions. Any production safety gate requires an explicit evaluation/monitoring decision and evidence.

## Tenancy and ownership

- `TABLE_OWNERSHIP` assigns all 16 current tables; every domain record except global agency/user roots carries `agency_id`.
- All FKs use RESTRICT; services include `actor.agency_id` in reads/locks. Conversation session operations additionally require `initiated_by`.
- `resolve_development_actor` requires active user and active membership.
- Cross-tenant resources resolve to not found rather than exposing existence.
- Database FKs are not composite agency FKs, so background jobs/provider handlers must preserve service-level agency checks.

Status: VERIFIED for earlier ownership test snapshots through `0006`; `0007` ownership and the current aggregate tree are IMPLEMENTED—UNVERIFIED. Production tenancy is PARTIAL until production identity/onboarding exists.

## Idempotency, lifecycle, and transaction integrity

| Invariant | Code evidence | Status |
|---|---|---|
| One confirmed intake per session | Unique `conversation_intakes.conversation_session_id`; confirmation locks session and requires REVIEW_PENDING | VERIFIED for recorded Voice snapshot |
| Confirmation replay safety | `IdempotencyRecord`; actor/route/key unique; hashed canonical request; durable stored response in same transaction | VERIFIED for recorded Voice snapshot; current aggregate unverified |
| One lead per confirmed intake | Unique `agency_leads.conversation_intake_id`; lead created in confirmation transaction | VERIFIED for owner-reported `0006` snapshot |
| Handoff replay safety | `LeadService.create_handoff`; same idempotency pattern and open-request rules | VERIFIED for owner-reported `0006` snapshot |
| Telephony receive/event replay safety | Unique adapter/reference and call/event key; replay consistency checks; race recovery | IMPLEMENTED—UNVERIFIED |
| Optimistic concurrency | Expected row versions plus DB increment trigger for settings, FAQ, lead/handoff, policy/number/call link | VERIFIED through recorded `0006`; `0007` IMPLEMENTED—UNVERIFIED |
| State transitions are allow-listed | Conversation service state checks; `LEAD_TRANSITIONS`, `HANDOFF_TRANSITIONS`, `transition_call` | PARTIAL because phone lifecycle is unverified/incomplete |
| Durable effects and audit commit together | Service transaction scopes documented in `02-runtime-and-data-flows.md` | VERIFIED in recorded earlier slices; `0007` IMPLEMENTED—UNVERIFIED |
| Immutable confirmed/event records | PostgreSQL triggers for `conversation_intakes` and `inbound_call_events` | Intake VERIFIED; call events IMPLEMENTED—UNVERIFIED |

Never add external notification/provider side effects inside a database transaction. A durable outbox/retry design is required before delivery, and is **DECISION REQUIRED** at the provider/mechanism level.

## Audit

- Conversation confirmation emits CUSTOMER_CREATED, CONVERSATION_INTAKE_CONFIRMED, and LEAD_CREATED events with IDs/status, not raw audio.
- Receptionist audit stores changed field names rather than setting contents.
- FAQ management audit stores IDs/status/version; live answer-use audit stores session/source ID/version, not query/answer.
- Lead/handoff and telephony mutations emit domain events with identifiers/state.
- Correlation IDs come from middleware and are stored with audits.

Status: PARTIAL. Audit coverage exists for current mutations, but `audit_events` has no database immutability trigger, there is no general audit API/export/retention policy, and future job/notification/billing/document domains are absent.

## Quotas and usage

- Voice session admission is bounded by configured maximum duration, a UTC daily authorization limit, and one active session per agency.
- Telephony policy contains concurrent and UTC daily received-call limits; `enforce_call_limits` applies them at simulated receive.
- Provider setup requires a finite billing guard and 180-second provider maximum, but those are external manual settings.

Status: PARTIAL. Admission quotas exist. Durable usage/cost records, duration metering for phone calls, provider reconciliation, entitlements, and billing are NOT IMPLEMENTED.

## Provider and credential isolation

| Boundary | Evidence | Status |
|---|---|---|
| ElevenLabs server credential | `ElevenLabsConversationProvider` alone receives the secret and mints a token; browser gets token only; tests assert API key absence | IMPLEMENTED—UNVERIFIED current snapshot; provider unit snapshot VERIFIED |
| Browser public config | Only API base URL and feature flag are parsed from `NEXT_PUBLIC_*`; no provider key/agent ID is public | VERIFIED as static architecture fact |
| Stored provider metadata | Neutral adapter/version/reference dictionaries; no credentials/raw provider payloads | IMPLEMENTED—UNVERIFIED current aggregate |
| Telephony provider | Neutral `TelephonyAdapter` protocol only; no concrete provider/config | NOT IMPLEMENTED |
| Provider signature verification | Protocol method exists but no route/caller/implementation | NOT IMPLEMENTED |
| Notification provider | Neutral `NotificationPort` only; no adapter/outbox | NOT IMPLEMENTED |

## Production authentication

Every current business route is development-only and resolves `DEVELOPMENT_ACTOR_USER_ID`. Conversation routes are hidden unless development Voice configuration is enabled, while receptionist/FAQ/lead/telephony development routes require development environment/actor but not the Voice feature flag. There are no bearer/cookie/session validators, invitations, role checks, production actor dependency, or tenant switch.

Status: DECISION REQUIRED. Production authentication design must be selected before production-facing routes or real tenant data. Do not implement until owner decides.

## Telephony-specific boundaries

- Do not expose development simulation routes as provider ingress.
- Verify signature/timestamp/replay against the raw body before parsing/mutating.
- Resolve the called number through backend-owned active-number data; never accept agency ID from a provider payload.
- Normalize provider events inside the concrete adapter, then call neutral core services.
- Keep signing secrets/provider credentials out of browser, models, audit, logs, and error bodies.
- Current call policy snapshot must remain immutable for the accepted call.
- Real-number configuration/real callers are forbidden until adapter, signed ingress, production auth, privacy review, and operations controls are separately verified.
- DTMF, maximum duration, interruption/silence, phone consent/disclosure, transcript confirmation, provider transfer execution, and usage accounting are not defined/implemented. Do not guess them.

Status: PARTIAL; concrete provider behavior is DECISION REQUIRED.

## Notification boundaries

`NotificationPort` accepts only agency, lead, handoff, and event IDs. Approved documentation requires payload construction, credentials, retry, and delivery status to stay in an adapter plus durable outbox. There is no caller or implementation.

Status: DECISION REQUIRED for mechanism/provider and NOT IMPLEMENTED for delivery. Do not implement until owner decides.
