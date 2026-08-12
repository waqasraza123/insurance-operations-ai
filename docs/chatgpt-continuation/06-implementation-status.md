# Implementation Status

## Status rules

- **VERIFIED**: implementation exists and explicit evidence says the required verification passed for the named snapshot.
- **IMPLEMENTED—UNVERIFIED**: implementation exists, but current required verification is absent.
- **PARTIAL**: only the listed parts exist.
- **NOT IMPLEMENTED**: static inspection found no implementation supporting the capability.
- **DECISION REQUIRED**: work must stop until an owner decision.

The matrix describes the dirty working tree audited on 2026-08-09. A VERIFIED row names its scope; it is never a claim that the entire dirty tree passes.

## Capability matrix

| Capability | Status | What exists | What is missing / scope qualification |
|---|---|---|---|
| Repository/runtime foundation | VERIFIED | Monorepo, Next.js web, FastAPI API, Python worker identity, Node 26/Python 3.13 constraints, CI declarations, health/readiness; prior foundation evidence | The current aggregate dirty tree has not been rerun; the worker has no business jobs |
| Database foundation | PARTIAL | Neon-safe SQLAlchemy/psycopg connection, Alembic, 16 modeled tables, linear static head `0007`; owner evidence through `0006` | `0007` application/current/drift and aggregate current migrations are unverified; no production DB evidence |
| Development actor | VERIFIED | Deterministic seeded app user/membership and `resolve_development_actor` with active checks | Production identity, roles, invitations, tenant switching |
| Customer foundation | VERIFIED | Agency-owned versioned customer model, normalization/view construction, creation during confirmation | General customer management/export/deletion UI/API |
| Generic conversations | PARTIAL | Provider-neutral session/intake names, protocol, lifecycle, session metadata, confirmation | Phone channel does not reuse conversation/intake contract; latest disclosure/documentation/current aggregate unverified |
| ElevenLabs Voice AI | PARTIAL | Server token adapter, React SDK adapter, private authenticated WebRTC design, tools, failure handling; provider unit evidence | Live current-snapshot/provider-dashboard behavior, exact external model/STT/TTS/voice/region/privacy controls remain owner/manual verification |
| Voice review/confirmation | VERIFIED | Browser in-memory draft/transcript, explicit end/review/edit/confirm, schema bounds, owned REVIEW_PENDING requirement; earlier tests/report | Current aggregate tree and live provider behavior not rerun |
| Voice persistence | VERIFIED | Customer + immutable intake + lead + audits + session CONFIRMED + idempotency response in one transaction; owner-reported lead slice checks | Retention/deletion and phone-origin persistence |
| Voice lifecycle hardening | PARTIAL | 15-second API timeout, disconnect/error cleanup, confirmation expiry, 180-second backend/client bound, one concurrent/ten daily, retry classifications | Current live-provider evaluation, server termination of an active provider call, broader failure/evaluation corpus, production observability |
| FAQ system | VERIFIED | Versioned agency FAQ CRUD/status, deterministic active-only unambiguous lookup, fallback, source audit, manager, Voice tool; owner-reported slice checks | Semantic retrieval/evaluation is not required/selected; phone caller integration and aggregate rerun absent |
| Receptionist | VERIFIED | Versioned agency settings, validation, seed, audit, homepage/Voice/editor consumption; owner-reported focused/full/live checks | Phone prompt/disclosure behavior and production tenant management |
| Lead capture | VERIFIED | One lead per confirmed intake, urgency/status/summary, list/detail/update, audit, ownership/versioning; owner-reported `0006` checks | Phone-originated lead creation and frontend lead inbox |
| Lead handoff | PARTIAL | Callback/live-transfer request records, idempotent creation, validation, lifecycle/audit; owner-reported `0006` checks | Browser handoff tool/UI, actual live transfer execution, delivery/acknowledgement workflow |
| Inbound telephony | PARTIAL | `0007` neutral policy/number/call/event models, simulation APIs, availability, transfer/callback directives, lead linking | All current telephony code is unverified; no real provider ingress/call control/conversation/intake/transcript/new-lead path |
| Telephony signature verification | NOT IMPLEMENTED | `TelephonyAdapter.verify_inbound_webhook` signature exists as an interface only | Concrete verification, raw-body route, timestamp/replay enforcement, tests |
| Normalized provider events | PARTIAL | Neutral `InboundCallEventType`, immutable event storage, state machine, dedupe | No concrete provider payload parser/mapping or callback ingress |
| DTMF | NOT IMPLEMENTED | No schema/event/service/adapter behavior | Provider mapping, neutral events, business semantics, tests |
| Duration controls | PARTIAL | Browser Voice has configured/client/backend maximum; call policy has ring timeout only | No maximum telephone-call duration, termination command, or duration event/meter |
| Notification delivery | NOT IMPLEMENTED | `NotificationPort`/`HandoffNotification` interface only | Caller, outbox, job, provider adapter, retry/status/audit, recipient policy |
| Usage metering | NOT IMPLEMENTED | Admission quotas/counts exist but are not a meter | Append-only usage/duration/cost ledger, idempotent recording, reconciliation, reporting |
| Quota controls | PARTIAL | Voice concurrent/daily/duration admission; telephony concurrent/daily receive logic | Telephony verification, entitlement coupling, cost/provider limits |
| Audit | PARTIAL | Domain audit creation for current mutations; correlation IDs; selected lead audit projection | DB immutability, general read/export/retention, future domains, production actors |
| Frontend surfaces | PARTIAL | `/`, `/voice-test`, `/receptionist-settings`, `/approved-faqs` | Lead inbox/detail/handoff, call policy/number/call UI, production shell/onboarding/billing/document/review surfaces |
| Document upload | NOT IMPLEMENTED | No upload route/storage model/UI | Storage/provider decision, signed flow, validation, scanning, lifecycle |
| Durable jobs | NOT IMPLEMENTED | Worker process/readiness shell only | Job table/claim/lease/retry/dead-letter/handlers/observability |
| Document AI | NOT IMPLEMENTED | Historical specifications only, deleted from working tree | Evaluation gate, selected parser/OCR/model pipeline, evidence/candidate publishing |
| OCR | NOT IMPLEMENTED | No provider/adapter/evaluation/runtime code | Provider selection, strategy, quality/latency/cost evaluation |
| Human review workflow | NOT IMPLEMENTED | Lead review is not the historical policy-document review workflow | Review queue/workspace, validation, approval, correction/reprocessing |
| Production authentication | DECISION REQUIRED | Identity/membership tables and development actor provide prerequisites | Auth provider/protocol, session/token validation, invitations, roles, production actor/onboarding. Do not implement until owner decides. |
| Real-customer-data operation | DECISION REQUIRED | Synthetic-only gates/copy and minimal confirmed customer storage | Legal/privacy/security/retention/deletion/vendor controls. Do not implement until owner decides. |
| Deployment | DECISION REQUIRED | CI and runnable process entry points | Platform selection, manifests, environments, secrets, networking, migration/release/rollback/monitoring. Do not implement until owner decides. |
| Billing/entitlements | DECISION REQUIRED | Provider dashboard billing guard is documented only | Billing provider, plans, limits, webhook idempotency, backend entitlement checks. Do not implement until owner decides. |
| CRM/external integrations | DECISION REQUIRED | Neutral notification boundary only | Providers, data contracts, authorization, retry/reconciliation. Do not implement until owner decides. |

## Current acceptance gap

The repository can support a synthetic browser demonstration and backend API inspection. It cannot truthfully claim a real inbound-phone receptionist, production multi-tenancy, external handoff delivery, metered SaaS billing, Document AI, or production deployment. Those capabilities are PARTIAL, NOT IMPLEMENTED, or DECISION REQUIRED exactly as shown above.
