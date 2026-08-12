# Runtime and Data Flows

Status statements below describe the current working tree. “Intended” behavior is never presented as current execution.

## Browser to backend and database

```text
Next.js server page/client component
  -> typed fetch wrapper (15-second timeout for feature APIs)
  -> FastAPI route
  -> development_actor dependency
       -> active AppUser + active AgencyMembership lookup
  -> service method
       -> agency-scoped reads OR one SQLAlchemy transaction
       -> PostgreSQL constraints/triggers
  -> Pydantic response
  -> defensive TypeScript parser/UI
```

- Implemented: health, receptionist, FAQ, Voice session/confirmation, lead/handoff, and simulated telephony routes.
- Authority: FastAPI resolves the actor and applies ownership/state rules. The browser supplies expected row versions and explicit idempotency keys where required; it does not select an agency.
- Authentication limitation: the actor is a configured development user, not a production credential. Production access is **DECISION REQUIRED**.
- Transaction boundary: each mutating service method uses `with session, session.begin()` unless the Voice provider call requires an external boundary described below.
- Status: PARTIAL.

## Backend and worker to database

`api.py` creates a pooled runtime engine. `database/connection.py` validates PostgreSQL URLs and supplies separate runtime and direct migration engines; migrations disable application-side pooling. `check_database_readiness` performs a simple identity/readiness query and sanitizes failures at the HTTP boundary.

The worker builds settings/engine, checks readiness, and waits on a process event. It does not poll, claim, execute, retry, or dead-letter durable jobs. Worker-to-database business flow is therefore NOT IMPLEMENTED; only readiness is IMPLEMENTED—UNVERIFIED for the present snapshot.

## Voice authorization, session, review, and confirmation

```text
User checks disclosure + microphone + synthetic-data acknowledgements
  -> POST conversation-sessions
  -> transaction A: lock agency; expire stale sessions; enforce daily/concurrent
                    create REQUESTING ConversationSession
  -> external call outside DB transaction:
       ConversationProvider.authorize_session()
       ElevenLabs adapter uses server API key to mint WebRTC token
  -> transaction B: lock session; mark AUTHORIZED; store sanitized metadata
     OR transaction C on provider error: mark FAILED/PROVIDER_UNAVAILABLE
  -> browser starts ElevenLabs WebRTC with token
  -> transcript/draft remain React memory
  -> POST session/end(COMPLETED)
  -> one transaction marks REVIEW_PENDING, or EXPIRED if over duration
  -> user edits and confirms
  -> POST conversation-intakes + Idempotency-Key
  -> one transaction creates Customer + immutable ConversationIntake + AgencyLead
                     + three AuditEvents; marks session CONFIRMED;
                     completes IdempotencyRecord
```

Implemented behavior and boundaries:

- `ConversationService.authorize_session` rejects any missing acknowledgement before persistence/provider access.
- The agency row lock serializes daily/concurrent admission. Current default/bounds include one active session, ten daily sessions, and a maximum of 180 seconds as configured/validated.
- The provider secret is used only by `ElevenLabsConversationProvider`; the response includes a token and sanitized adapter metadata, not the API key.
- `VoiceTest` and `ElevenLabsConversationAdapter` keep unconfirmed transcript and draft only in browser memory. `submit_intake_draft` explicitly reports that nothing was saved.
- The end route is required before confirmation. A completed authorized session becomes `REVIEW_PENDING`; interrupted/provider-error outcomes become `FAILED`; late completion becomes `EXPIRED`.
- Confirmation requires a contact method, user and agent transcript turns, bounded text/turn counts, an owned `REVIEW_PENDING` session, and an unexpired confirmation window.
- Confirmation idempotency scope is actor + route + key with a canonical request hash. Same key/different request returns a conflict; successful replay returns the stored response.
- The customer, intake, lead, audits, session transition, and idempotency completion commit or roll back together.
- `conversation_intakes` are immutable by a PostgreSQL trigger. Raw audio is never modeled or written.
- Status: PARTIAL. The development browser flow exists and prior slice evidence exists, but current combined changes were not verified and telephone sessions do not reuse this flow.

## Receptionist settings flow

```text
Home/Voice/editor GET receptionist-settings
  -> agency-scoped read

Editor PUT receptionist-settings(expected_row_version, full replacement)
  -> transaction locks agency's settings row
  -> create at expected version 0 OR compare optimistic row_version
  -> validate contact/category/content bounds
  -> add content-minimized AuditEvent with changed field names
  -> PostgreSQL trigger updates updated_at and increments row_version
```

Settings are used to label the experience, inform categories, and provide escalation/fallback copy. There is no call-specific receptionist prompt builder or phone provider configuration. Status: VERIFIED for the owner-reported settings slice; phone behavior remains PARTIAL.

## Approved FAQ answer flow

```text
Management: list/create/update/status -> agency-scoped FAQ rows + audit

Preview: POST approved-faqs/lookup(query)
  -> read active agency FAQs + receptionist escalation
  -> normalize and score deterministically
  -> answer only one sufficiently strong, non-ambiguous match
  -> otherwise fallback

Live Voice tool: lookup_approved_faq(query)
  -> POST session/{id}/approved-faq-lookup
  -> transaction verifies active session belongs to actor/agency
  -> same matcher
  -> audit source ID/version and match result, not query/answer content
  -> frontend maps API `answer` to tool `approved_answer`
```

Inactive records never answer. Weak and ambiguous questions receive the receptionist escalation message. The current matcher is lexical/deterministic; no embedding/model/provider call exists. Status: VERIFIED for the owner-reported FAQ slice snapshot.

## Lead creation and handoff flow

Lead creation is not an independent public route. `ConversationService.confirm_intake` creates exactly one `AgencyLead` for the unique conversation intake in the same transaction as customer/intake confirmation. The default status is `NEW`; urgency is supplied by the confirmation contract and the current browser effectively uses `NORMAL`.

```text
Confirmed browser intake -> Customer -> ConversationIntake -> AgencyLead
                                          \-> audit events

Staff development API -> list/detail/update/status agency-owned lead
                      -> create handoff + Idempotency-Key
                      -> transition handoff status

Telephony callback path (current limitation):
existing confirmed lead -> link to inbound call
  -> if call is CALLBACK_PENDING, create one callback LeadHandoffRequest
  -> mark CALLBACK_REQUESTED + append call event/audit
```

- Lead and handoff mutations lock rows and compare `expected_row_version`.
- State transitions are allow-listed in `LeadService.LEAD_TRANSITIONS` and `HANDOFF_TRANSITIONS`.
- Handoff creation uses the idempotency table; an open duplicate is also rejected.
- Callback contact preference is validated against actual customer email/phone. A live-transfer request does not itself invoke a provider.
- Telephony cannot create a new customer/intake/lead. It can only link an existing agency lead. The browser has no lead inbox or handoff-request tool/UI.
- Status: PARTIAL at product level; the backend `0006` slice is VERIFIED for its owner-reported snapshot.

## Inbound telephony event flow

The only current ingress is a development route accepting already-normalized, caller-supplied adapter fields. It is not a provider webhook.

```text
POST /development/inbound-calls (simulated normalized receive)
  -> dedupe adapter_name + source_call_reference
  -> find active called number for actor agency
  -> lock active call policy; enforce enabled/concurrent/daily
  -> snapshot policy; create RECEIVED call
  -> append immutable CALL_RECEIVED event + audit
  -> return ANSWER_AI directive

POST call/{id}/events (simulated normalized event)
  -> lock agency-owned call
  -> dedupe event_key; reject different replay
  -> transition_call allow-list
  -> append immutable neutral event + audit in same transaction
  -> return CONTINUE_AI / TRANSFER / COLLECT_CALLBACK / END
```

Current transitions include answered, transfer requested/succeeded/failed, call ended, and provider failed. Transfer requested evaluates the stored policy snapshot and IANA-timezone availability. It returns a transfer destination/ring timeout but does not call `TelephonyAdapter.request_transfer`. Callback creation occurs only after an existing lead is linked.

Idempotency boundaries:

- Receive: unique `(adapter_name, source_call_reference)`, with replay payload consistency checks and a nested transaction for race recovery.
- Event: unique `(inbound_call_id, event_key)`, with event content consistency checks.
- Callback: unique nullable `LeadHandoffRequest.inbound_call_id`, plus the locked call state.

Status: PARTIAL. The neutral persistence/orchestration code is IMPLEMENTED—UNVERIFIED. The following intended path is NOT IMPLEMENTED:

```text
provider HTTP request raw body/headers
  -> concrete adapter verifies signature and timestamp/replay window
  -> adapter maps provider payload to VerifiedInboundCall/neutral events
  -> core TelephonyService
  -> adapter executes answer/transfer/provider response
```

DTMF, silence/interruption events, maximum call duration, provider call control, phone transcript/intake/lead creation, and durable usage/cost records are also NOT IMPLEMENTED.

## Provider adapter boundaries

- Voice: `ConversationProvider` is neutral; `ElevenLabsConversationProvider` alone knows the ElevenLabs token endpoint, headers, agent identifier, and response. `elevenlabs-adapter.tsx` alone knows the React SDK and tool envelope. This boundary is IMPLEMENTED—UNVERIFIED for the current snapshot.
- Telephony: `TelephonyAdapter` defines verified inbound-call and transfer operations. No concrete adapter, provider configuration, or caller exists. The boundary design is PARTIAL; functioning provider isolation is NOT IMPLEMENTED.
- Notifications: `NotificationPort` defines a handoff event. It has no concrete adapter or caller. Status: NOT IMPLEMENTED.

Never put provider payload fields into core request schemas merely to avoid an adapter. Neutral storage may retain sanitized adapter name/version/reference/metadata, never credentials or unrestricted sensitive payloads.

## Notification flow

No notification is sent when a lead or handoff is created or changes state. There is no outbox table, durable job, retry state, delivery record, or email/SMS adapter. `NotificationPort.send_handoff_notification` is unreferenced. Status: NOT IMPLEMENTED.

## Audit creation

Mutating services add `AuditEvent` rows inside the same SQL transaction as the authoritative change. Conversation confirmation records customer/intake/lead events. Receptionist, FAQ, lead/handoff, number/policy/call/event/link operations also emit events. FAQ live lookup records source identity/version without query/answer content. This is content-minimized application behavior.

Audit is PARTIAL: relevant current domains emit events, but no database immutability trigger protects `audit_events`, no production actor exists, no delivery/document domains exist, and no audit-query API is exposed beyond the lead detail projection.

## Quota and usage flow

- Voice authorization: agency lock, stale-session expiry, concurrent active-session rejection, and UTC daily authorization count.
- Telephony receive: locked call policy plus active-call and UTC daily received-call counts.
- HTTP responses use bounded 409/429 errors; Voice daily limit supplies `Retry-After`.

These are admission limits, not usage metering. There is no append-only usage ledger, duration/cost accounting, provider reconciliation, entitlement check, or billing export. Quota controls are PARTIAL; usage metering is NOT IMPLEMENTED.
