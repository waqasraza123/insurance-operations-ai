# API and Service Contracts

## Shared HTTP behavior

- Routes are assembled in `apps/backend/src/insurance_operations/application.py:create_app`; there are no separate FastAPI routers.
- `GET /health` and `GET /ready` are public. Every `/api/v1/development/*` route requires `application.py:development_actor`, which resolves one configured active app user/membership. Voice session/end/confirmation/live-FAQ routes additionally require `conversation_actor`, the development environment, the feature flag, and an available `ConversationService`.
- This is development actor resolution, not production authentication. Production authentication is **DECISION REQUIRED**.
- Agency-owned services derive `agency_id` from `ActorContext`; no request body chooses a tenant. Missing/cross-tenant resources normally return a domain 404 without exposing another tenant.
- Mutations use one service transaction and content-minimized audit unless a row below states otherwise. Reads use a read session. Voice provider authorization deliberately spans database/provider/database boundaries.
- Pydantic failures become `422 VALIDATION_FAILED`; domain failures use `ApiError`; all responses carry `X-Correlation-ID`.
- `Idempotency-Key` is required only for intake confirmation and handoff creation. Telephony receive/events use natural provider/event dedupe keys. All other routes have no explicit replay guarantee.
- CORS allows the configured web origin, GET/POST/PUT, content/correlation/idempotency headers, and no browser credentials.
- Every route below is present in the dirty working tree. Unless a narrower owner-reported snapshot is named, current verification status is IMPLEMENTED—UNVERIFIED.

## Health routes

| Method and path | Request -> response | Authority, behavior, transaction, errors | Caller/tests | Status |
|---|---|---|---|---|
| `GET /health` | none -> `HealthResponse` (`status`, `service`, `environment`) | Public, no ownership, no transaction, no idempotency; process liveness only | Home via `backend-health.ts`; `tests/test_api.py` | IMPLEMENTED—UNVERIFIED for current application composition; prior snapshot VERIFIED |
| `GET /ready` | none -> `ReadinessResponse` (health fields + `database`) | Public; calls `check_database_readiness`; no transaction/idempotency; returns sanitized 503 `database unavailable` | Operational/CI checks; `tests/test_api.py` | IMPLEMENTED—UNVERIFIED for current application composition; prior snapshot VERIFIED |

## Conversation and Voice routes

Focused evidence: `tests/database/test_conversation_api.py`, `tests/test_conversation_provider.py`, and frontend conversation tests. The core Voice slice has earlier VERIFIED evidence, but conversation/application files were subsequently modified; the aggregate current snapshot is IMPLEMENTED—UNVERIFIED.

| Method and path | Request -> response | Authority/ownership and transaction | Validations, transitions, idempotency, important errors | Caller | Status |
|---|---|---|---|---|---|
| `POST /api/v1/development/conversation-sessions` | `ConversationSessionCreateInput` (three booleans) -> `ConversationSessionResponse` (session ID, WebRTC credential, max duration, confirmation expiry), 201 | `conversation_actor`; actor agency/user owns session. Transaction A locks agency/admission and creates REQUESTING; provider call is outside DB transaction; transaction B marks AUTHORIZED, or error transaction marks FAILED. | All three acknowledgements true; concurrent/daily/duration configuration; errors include `AI_DISCLOSURE_REQUIRED`, `MICROPHONE_CONSENT_REQUIRED`, `SYNTHETIC_DATA_ACKNOWLEDGEMENT_REQUIRED`, `CONVERSATION_ALREADY_ACTIVE`, `CONVERSATION_DAILY_LIMIT_REACHED`, `CONVERSATION_PROVIDER_UNAVAILABLE`. No request idempotency. | `features/conversation/api.ts:authorizeConversationSession` | IMPLEMENTED—UNVERIFIED current snapshot |
| `POST /api/v1/development/conversation-sessions/{conversation_session_id}/end` | path UUID + `ConversationEndInput(outcome)` -> `ConversationEndResponse` | `conversation_actor`; requires same agency and initiating user; one locked transaction. | AUTHORIZED + COMPLETED -> REVIEW_PENDING; over-duration -> EXPIRED; INTERRUPTED/FAILED -> FAILED; idempotent only for the same already-recorded failure/review outcome, not a general key. Errors: not found, expired, state conflict. | `endConversationSession`; unload/failure/finalization paths | IMPLEMENTED—UNVERIFIED current snapshot |
| `POST /api/v1/development/conversation-intakes` | `ConversationIntakeConfirmationInput` (session, customer, intent, urgency, 2..60 transcript turns) + `Idempotency-Key` -> `ConversationIntakeResponse` (intake/session/customer/confirmed time/lead ID), 201 | `conversation_actor`; owned REVIEW_PENDING session. One transaction creates customer, immutable intake, unique lead, three audits, session CONFIRMED, and stored idempotent response. | Contact required; both USER/AGENT speakers; bounded text; unexpired window; key trimmed/1..128; request hash. Errors: session not found/expired/state conflict, `IDEMPOTENCY_KEY_REUSED`, `OPERATION_IN_PROGRESS`, validation. Successful replay sets `Idempotent-Replayed: true`. | `confirmConversationIntake` from explicit review UI | IMPLEMENTED—UNVERIFIED current snapshot; earlier Voice/lead slices owner-reported VERIFIED |

## Receptionist settings routes

Focused tests: `tests/database/test_receptionist_settings_api.py` and frontend settings-form tests. Owner-reported settings slice status: VERIFIED. Aggregate current application status: IMPLEMENTED—UNVERIFIED.

| Method and path | Request -> response | Authority/ownership and transaction | Validations/idempotency/errors | Caller | Status |
|---|---|---|---|---|---|
| `GET /api/v1/development/receptionist-settings` | none -> `ReceptionistSettingsResponse` | `development_actor`; reads exactly actor agency row; read session | No idempotency. `RECEPTIONIST_SETTINGS_NOT_FOUND` if absent. | Home, Voice page, editor through `getReceptionistSettings` | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |
| `PUT /api/v1/development/receptionist-settings` | Full `ReceptionistSettingsInput` + `expected_row_version` -> response | `development_actor`; locks one agency row; create at expected version 0 or replace; mutation+audit transaction | Contact required; bounded public name/greeting/hours/contact/categories/escalation; unique categories; `RECEPTIONIST_SETTINGS_VERSION_CONFLICT`. No request idempotency; optimistic concurrency prevents silent overwrite. | `replaceReceptionistSettings` | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |

## Approved FAQ routes

Focused tests: `tests/test_approved_faq_matching.py`, `tests/database/test_approved_faq_api.py`, and `apps/web/src/features/approved-faqs/api.test.ts`. Owner-reported FAQ slice status: VERIFIED. Aggregate current application status: IMPLEMENTED—UNVERIFIED.

| Method and path | Request -> response | Authority/ownership and transaction | Validations/idempotency/errors | Caller | Status |
|---|---|---|---|---|---|
| `GET /api/v1/development/approved-faqs` | none -> `list[ApprovedFaqResponse]` | `development_actor`; agency-filtered read | No idempotency. Includes active/inactive rows, never other agencies. | FAQ manager `listApprovedFaqs` | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |
| `POST /api/v1/development/approved-faqs` | `ApprovedFaqCreateInput(question, approved_answer, status default INACTIVE)` -> response, 201 | `development_actor`; insert+audit transaction | Content bounds; normalized question unique within agency; `APPROVED_FAQ_ALREADY_EXISTS`. No idempotency. | `createApprovedFaq` | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |
| `PUT /api/v1/development/approved-faqs/{faq_id}` | path UUID + `ApprovedFaqUpdateInput` with expected version -> response | `development_actor`; locks agency-owned FAQ; update+audit transaction | Normalization/content bounds; expected version; errors not found, already exists, `APPROVED_FAQ_VERSION_CONFLICT`. | `updateApprovedFaq` | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |
| `POST /api/v1/development/approved-faqs/{faq_id}/activate` | path UUID + `ApprovedFaqStatusInput(expected_row_version)` -> response | Same ownership/lock; status+audit transaction | Expected version; not found/version conflict. Replay without fresh version conflicts. | `setApprovedFaqStatus` | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |
| `POST /api/v1/development/approved-faqs/{faq_id}/deactivate` | same status input -> response | Same as activate | Same as activate; transition is direct ACTIVE/INACTIVE, with no separate transition matrix. | `setApprovedFaqStatus` | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |
| `POST /api/v1/development/approved-faqs/lookup` | `ApprovedFaqLookupInput(query)` -> `ApprovedFaqLookupResponse` | `development_actor`; agency active-FAQ/settings read; no write transaction | Query <=500; only a strong, unambiguous active match returns `answer`+source; otherwise fallback. Requires receptionist settings (`RECEPTIONIST_SETTINGS_REQUIRED`). No idempotency/audit for preview. | `previewApprovedFaqLookup` | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |
| `POST /api/v1/development/conversation-sessions/{conversation_session_id}/approved-faq-lookup` | path UUID + lookup input -> lookup response | `conversation_actor`; same agency+initiator and active/unexpired AUTHORIZED session; one transaction because successful source use is audited | Same safe matcher; `CONVERSATION_SESSION_NOT_ACTIVE`, settings required. Audit stores source/session IDs/version, not content. Natural repeats can create repeated audit rows; no request key. | ElevenLabs client tool via `lookupConversationApprovedFaq` | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |

## Lead and handoff routes

Focused evidence is in the lead scenario within `tests/database/test_conversation_api.py` and `docs/lead-handoff-api.md`. Owner-reported `0006` slice status: VERIFIED. No frontend caller exists.

| Method and path | Request -> response | Authority/ownership and transaction | Validations, transitions, idempotency, errors | Caller | Status |
|---|---|---|---|---|---|
| `GET /api/v1/development/leads` | query `status?`, `limit` 1..100, `offset>=0` -> `LeadListResponse` | `development_actor`; agency-filtered read | No idempotency; summary includes customer and open-handoff count. | No production/frontend caller; tests | IMPLEMENTED—UNVERIFIED current aggregate; `0006` slice VERIFIED |
| `GET /api/v1/development/leads/{lead_id}` | path UUID -> `LeadDetailResponse` | `development_actor`; agency-filtered read joins customer/intake/handoffs/audit | `LEAD_NOT_FOUND`; returns confirmed transcript and selected lead-related audit projection. | Tests/manual API only | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |
| `PUT /api/v1/development/leads/{lead_id}` | `LeadUpdateInput(summary, urgency, expected_row_version)` -> detail | `development_actor`; locks agency-owned lead; update+audit transaction | Bounded summary, urgency enum, `LEAD_VERSION_CONFLICT`, not found. No request idempotency. | Tests/manual API only | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |
| `POST /api/v1/development/leads/{lead_id}/status` | `LeadStatusInput(status, expected_row_version)` -> detail | Same lock/transaction | Allow-list in `LEAD_TRANSITIONS`; `LEAD_STATUS_TRANSITION_INVALID`, version conflict, not found. | Tests/manual API only | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |
| `GET /api/v1/development/leads/{lead_id}/handoff-requests` | path UUID -> `list[HandoffRequestResponse]` | `development_actor`; verifies agency-owned lead then reads its handoffs | `LEAD_NOT_FOUND`; no idempotency. | Tests/manual API only | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |
| `POST /api/v1/development/leads/{lead_id}/handoff-requests` | `HandoffRequestCreateInput` + `Idempotency-Key` -> response, 201 | `development_actor`; agency lead/customer read+lock, idempotency record, handoff and audit in one transaction | CALLBACK/LIVE_TRANSFER; contact availability; phone/email must exist for matching callback method; rejects incompatible key reuse/in-progress/open duplicate; successful replay header. | Tests/manual API only | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |
| `POST /api/v1/development/handoff-requests/{handoff_id}/status` | `HandoffStatusInput(status, transfer_attempted?, expected_row_version)` -> response | `development_actor`; locks agency-owned handoff and lead; mutation+audit transaction | Allow-list in `HANDOFF_TRANSITIONS`; terminal timestamps; `HANDOFF_STATUS_TRANSITION_INVALID`, `HANDOFF_REQUEST_VERSION_CONFLICT`, `TRANSFER_NOT_APPLICABLE`, not found. No request idempotency. | Tests/manual API only | IMPLEMENTED—UNVERIFIED current aggregate; slice VERIFIED |

## Telephony development routes

These routes accept normalized simulation input from a development actor. They are not a signed provider API. Focused tests are `tests/test_telephony_policy.py` and `tests/database/test_telephony_api.py`. Current status for every route is IMPLEMENTED—UNVERIFIED.

| Method and path | Request -> response | Authority/ownership and transaction | Validations, transitions, idempotency, errors | Caller | Status |
|---|---|---|---|---|---|
| `GET /api/v1/development/call-policy` | none -> `CallPolicyResponse` | `development_actor`; agency row read | `CALL_POLICY_NOT_FOUND`; no idempotency. | Tests/manual API only | IMPLEMENTED—UNVERIFIED |
| `PUT /api/v1/development/call-policy` | Full `CallPolicyInput` + expected version -> response | Actor agency; lock/create/replace+audit transaction | Valid IANA timezone; non-overlap/same-day windows; transfer destination when enabled; ring/concurrency/daily/content bounds; `CALL_POLICY_VERSION_CONFLICT`. | Tests/manual API only | IMPLEMENTED—UNVERIFIED |
| `GET /api/v1/development/inbound-numbers` | none -> `list[InboundNumberResponse]` | Actor agency read | No idempotency. | Tests/manual API only | IMPLEMENTED—UNVERIFIED |
| `POST /api/v1/development/inbound-numbers` | `InboundNumberCreateInput(E.164,label,status)` -> response, 201 | Actor agency; insert+audit transaction | Strict E.164, label/status; global phone uniqueness; `INBOUND_NUMBER_ALREADY_EXISTS`. No idempotency. | Tests/manual API only | IMPLEMENTED—UNVERIFIED |
| `POST /api/v1/development/inbound-numbers/{number_id}/status` | path UUID + status/expected version -> response | Locks actor-agency number; update+audit transaction | ACTIVE/INACTIVE; `INBOUND_NUMBER_NOT_FOUND`, `INBOUND_NUMBER_VERSION_CONFLICT`. | Tests/manual API only | IMPLEMENTED—UNVERIFIED |
| `POST /api/v1/development/inbound-calls` | `InboundCallReceiveInput(adapter name/version, source reference, called/caller E.164, aware occurred_at)` -> `InboundCallActionResponse`, 201 | Development actor supplies neutral fields; finds active number in actor agency, locks policy, creates call/event/audit transaction | Policy enabled; concurrent/daily limits; unique adapter/reference with consistent natural replay. Errors include route not found, disabled, limits, `INBOUND_CALL_REFERENCE_REUSED`. Returns `ANSWER_AI`; it does not answer a provider call. | Tests/manual simulation only | IMPLEMENTED—UNVERIFIED |
| `GET /api/v1/development/inbound-calls` | query status?, limit 1..100, offset>=0 -> `InboundCallListResponse` | Actor-agency filtered read | No idempotency. | Tests/manual API only | IMPLEMENTED—UNVERIFIED |
| `GET /api/v1/development/inbound-calls/{call_id}` | path UUID -> `InboundCallResponse` | Actor-agency filtered read | `INBOUND_CALL_NOT_FOUND`; no idempotency. | Tests/manual API only | IMPLEMENTED—UNVERIFIED |
| `POST /api/v1/development/inbound-calls/{call_id}/events` | `InboundCallEventInput(event_key,type,aware occurred_at,failure_code?)` -> action response | Locks actor-agency call; state transition+immutable event+audit transaction | Neutral types ANSWERED/TRANSFER_REQUESTED/TRANSFER_SUCCEEDED/TRANSFER_FAILED/CALL_ENDED/PROVIDER_FAILED; failure code only for provider failure; event time >= received; consistent key replay; state allow-list. Errors include key reused, time invalid, transition invalid. | Tests/manual simulation only | IMPLEMENTED—UNVERIFIED |
| `POST /api/v1/development/inbound-calls/{call_id}/lead` | `InboundCallLinkLeadInput(lead_id, expected_row_version)` -> action response | Locks actor-agency call; agency-filtered lead/customer/intake query; call link, optional callback handoff, event, audit in one transaction | Existing link replay only for same lead; version check; allowed call states; `INBOUND_CALL_LEAD_CONFLICT`, `LEAD_NOT_FOUND`, state/version conflict. At CALLBACK_PENDING creates one callback handoff. | Telephony test/manual simulation only | IMPLEMENTED—UNVERIFIED |

## Non-HTTP service and adapter contracts

### `ConversationProvider`

File: `conversations/contracts.py`.

- `authorize_session() -> ConnectionGrant`: must return neutral transport `webrtc`, an ephemeral credential, and `ProviderSessionMetadata` suitable for sanitized storage.
- `close()`: releases client resources.
- `ConversationProviderError`: converted by `ConversationService` to a sanitized 503 and FAILED session.
- Concrete implementation: `providers/elevenlabs.py:ElevenLabsConversationProvider`; calls ElevenLabs using server-only key and validates the response with `ConversationTokenResponse`.
- Status: IMPLEMENTED—UNVERIFIED for current snapshot; provider unit tests have older VERIFIED evidence.

### Browser `ConversationClient`

File: `apps/web/src/features/conversation/contracts.ts`.

- Neutral `status`, `mode`, `isMuted`, `start(credential)`, `end()`, and `setMuted()` contract consumed by `VoiceTest`.
- `ElevenLabsConversationAdapter` contains SDK-specific event/tool mapping.
- Status: IMPLEMENTED—UNVERIFIED for current snapshot.

### `TelephonyAdapter`

File: `telephony/contracts.py`.

- `verify_inbound_webhook(headers, body) -> VerifiedInboundCall`: intended boundary for signature validation and normalized receive data.
- `request_transfer(source_call_reference, TransferInstruction)`: intended provider command boundary.
- `close()` and `TelephonyAdapterError`.
- There is no concrete implementation, configuration, factory, route caller, provider event normalizer, or test double wired through the application.
- Status: PARTIAL as a contract; provider integration is NOT IMPLEMENTED.

### `NotificationPort`

File: `notifications/contracts.py`.

- `send_handoff_notification(HandoffNotification)` and `close()`.
- There is no caller, adapter, outbox, delivery model, or test.
- Status: NOT IMPLEMENTED.

### Development actor and persistence services

- `actors.py:resolve_development_actor(session, user_id) -> ActorContext` requires one active user and membership. Status: VERIFIED for development snapshot.
- `ReceptionistSettingsService`, `ApprovedFaqService`, `LeadService`, `TelephonyService`, and `ConversationService` accept a SQLAlchemy `sessionmaker`, preserving explicit transaction ownership inside service methods.
- Do not let a provider adapter construct `ActorContext`, select `agency_id`, or commit domain state. Provider ingress must resolve an inbound number to an agency through backend-owned data after signature verification.
