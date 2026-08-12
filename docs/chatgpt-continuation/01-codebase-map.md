# Codebase Map

## Execution spine

```text
Next.js route page
  -> typed client feature/API module
  -> FastAPI route in application.create_app
  -> development actor dependency
  -> domain service transaction/read session
  -> SQLAlchemy model
  -> PostgreSQL constraints/triggers from Alembic
  -> response parser/UI state

Browser Voice session only:
FastAPI ConversationService
  -> ConversationProvider protocol
  -> ElevenLabsConversationProvider (server credential)
  -> expiring WebRTC conversation token returned to browser
```

The provider does not write authoritative application state. `application.py` assembles services directly; there is no general dependency-injection container or router package.

## Runtime foundation and configuration

| Area | Purpose and spine | Important evidence | Tests | Status |
|---|---|---|---|---|
| API composition | Builds services, middleware, exception handling, dependencies, and every route. `api.py:main` creates `ApiSettings`, an engine, and `create_app()`. | `apps/backend/src/insurance_operations/api.py`; `application.py:create_app`, `default_conversation_provider`, `validate_idempotency_key`; `errors.py:ApiError` | `tests/test_api.py`, database API tests | PARTIAL — development API is broad; production auth and several operational adapters are absent. |
| Settings | Validates environment, PostgreSQL URLs/SSL, CORS origin, development actor, bounded Voice configuration, and ElevenLabs privacy/configuration. | `settings.py:RuntimeEnvironment`, `DatabaseSettings`, `ApiSettings`, `WorkerSettings`; root `.env.example`; `apps/web/.env.example` | `tests/test_settings.py`, `tests/database/test_connection_settings.py`, `apps/web/src/lib/environment.test.ts` | IMPLEMENTED—UNVERIFIED for the current dirty snapshot. |
| Errors/correlation | Converts domain errors and Pydantic failures to structured API errors; creates/exposes `X-Correlation-ID`. | `errors.py:ApiError`, `api_error_handler`; `application.py:add_correlation_id` | `tests/test_api.py` and focused API assertions | VERIFIED for earlier reported snapshots; current combined tree not rerun. |
| Development identity | Resolves one active development user and agency membership; all protected routes depend on it. | `actors.py:ActorContext`, `resolve_development_actor`; `application.py:development_actor`; seed constants/functions | database/API tests | VERIFIED for development only. Production identity is NOT IMPLEMENTED. |
| Worker | Checks database readiness, then blocks on an event. | `worker.py:WorkerRuntime`, `build_worker_runtime`, `main` | `tests/test_worker.py` | PARTIAL — process shell exists; durable jobs and processing do not. |
| CI/tooling | Node 26 web checks and Python checks against PostgreSQL 17 are declared. | `package.json`, `apps/web/package.json`, `pyproject.toml`, `.github/workflows/ci.yml` | Declared CI commands | IMPLEMENTED—UNVERIFIED for this working tree. |

## Frontend

| Surface/module | Purpose, callers, and dependencies | Routes/models/tests | Status |
|---|---|---|---|
| App shell/home | Server-loads health and receptionist settings, renders product entry points. | `app/layout.tsx`, `app/page.tsx`, `app/styles.css`; calls `lib/backend-health.ts:getBackendStatus` and `features/receptionist/api.ts:getReceptionistSettings`; route `/` | IMPLEMENTED—UNVERIFIED for current modifications. |
| Voice test | Consent gates, token authorization, ElevenLabs session controls, in-memory draft/transcript, bounded timer, explicit review/edit, confirmation. | `app/voice-test/page.tsx`; `features/conversation/voice-test.tsx:VoiceTest`; `api.ts`; `review.ts`; `lifecycle.ts`; `failures.ts`; shared TS contracts; tests in four `*.test.ts` files | PARTIAL — development browser flow exists; no production auth, lead inbox, phone reuse, or current whole-tree verification. |
| ElevenLabs boundary | Maps provider SDK events/tools to neutral UI contracts. | `configured-adapter.ts`; `elevenlabs-adapter.tsx:ElevenLabsConversationAdapter`; tools `lookup_approved_faq`, `submit_intake_draft`; `@elevenlabs/react` | Focused lifecycle/review/failure tests do not exercise a live provider | IMPLEMENTED—UNVERIFIED for current modifications. |
| Receptionist editor | Reads/replaces versioned agency receptionist settings with client validation. | route `/receptionist-settings`; `receptionist-settings.tsx:ReceptionistSettingsEditor`; `api.ts`; `contracts.ts`; `settings-form.ts` | `settings-form.test.ts` | VERIFIED for the owner-reported slice snapshot. |
| FAQ manager | Lists/creates/updates/activates/deactivates FAQs and previews deterministic lookup. | route `/approved-faqs`; `approved-faq-manager.tsx:ApprovedFaqManager`; FAQ `api.ts`/`contracts.ts` | `approved-faqs/api.test.ts` | VERIFIED for the owner-reported FAQ slice snapshot. |
| Lead/call/admin surfaces | No corresponding route or client feature package. | No `/leads` or telephony route under `apps/web/src/app` | None | NOT IMPLEMENTED. |

Public browser configuration is limited to `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_CONVERSATION_AI_ENABLED`; parsing is in `apps/web/src/lib/environment.ts:parsePublicEnvironment`. No server or provider credential is a public variable.

## Backend feature modules

### Conversations and Voice AI

- Purpose: authorize a bounded Voice session, classify its end state, and persist user-confirmed data.
- Files: `conversations/contracts.py`, `schemas.py`, `service.py`, `providers/elevenlabs.py`; `customers.py`; conversation/customer/lead/operations models; `application.py` routes.
- Important symbols: `ConversationProvider`; `ElevenLabsConversationProvider.authorize_session`; `ConversationService.authorize_session`, `end_session`, `confirm_intake`; `ConversationSessionStatus`; `ConversationIntakeConfirmationInput`.
- Callers: frontend `features/conversation/api.ts` and approved FAQ tool; `application.create_app`.
- Related models: `ConversationSession`, immutable `ConversationIntake`, `Customer`, `AgencyLead`, `AuditEvent`, `IdempotencyRecord`.
- Routes: session POST, session end POST, intake confirmation POST, session FAQ lookup POST. Full contracts are in `04-api-and-service-contracts.md`.
- Tests: `tests/test_conversation_provider.py`, `tests/database/test_conversation_api.py`, Voice frontend tests.
- Status: PARTIAL. The browser development path exists; provider-live behavior is not proven for the current snapshot, and telephone conversation/intake reuse is absent.

### Receptionist

- Purpose: agency-owned public identity, greeting, office hours, contact, categories, and escalation message.
- Files: `receptionist/schemas.py`, `receptionist/service.py`; `database/models/receptionist.py`; migrations `0003`/`0004`; frontend receptionist feature/page.
- Important symbols: `ReceptionistSettingsContent`, `ReceptionistSettingsService.get`, `replace`, `changed_setting_fields`.
- Callers: home and Voice pages read settings; editor replaces them; API routes call the service.
- Related model: `AgencyReceptionistSettings`; audit events store changed field names, not content.
- Tests: `tests/database/test_receptionist_settings_api.py`, frontend `settings-form.test.ts`, migration/ownership tests.
- Status: VERIFIED for the owner-reported slice snapshot.

### Approved FAQs

- Purpose: permit only explicitly approved, active agency answers and return a safe fallback on weak/ambiguous/no matches.
- Files: `approved_faqs/schemas.py`, `service.py`; `database/models/approved_faq.py`; migration `0005`; frontend FAQ feature/page; Voice adapter.
- Important symbols: `ApprovedFaqService`; `normalize_faq_question`; `select_faq_match`; `faq_match_score`; `ApprovedFaqLookupResponse`.
- Callers: management/preview frontend and `VoiceTest.handleApprovedFaqLookup`; ElevenLabs tool maps `answer` to provider-facing `approved_answer`.
- Related models: `AgencyApprovedFaq`, `ConversationSession`, `AgencyReceptionistSettings`, `AuditEvent`.
- Tests: `tests/test_approved_faq_matching.py`, `tests/database/test_approved_faq_api.py`, frontend parser test, migration/ownership tests.
- Status: VERIFIED for the owner-reported FAQ slice snapshot.

### Leads and handoffs

- Purpose: create a lead atomically from a confirmed intake; list/detail/update/version lead lifecycle; request and update callback/live-transfer handoffs.
- Files: `leads/schemas.py`, `leads/service.py`; `database/models/lead.py`; migration `0006` plus `0007` inbound-call extension; `docs/lead-handoff-api.md`.
- Important symbols: `LeadService.list`, `get`, `update`, `set_status`, `create_handoff`, `set_handoff_status`; `LEAD_TRANSITIONS`, `HANDOFF_TRANSITIONS`; `ConversationService.confirm_intake`.
- Callers: FastAPI routes and `TelephonyService.link_lead`; there is no frontend lead caller.
- Related models: `AgencyLead`, `LeadHandoffRequest`, `Customer`, `ConversationIntake`, `ConversationSession`, `InboundCall`, audit/idempotency records.
- Tests: lead lifecycle/handoff coverage in `tests/database/test_conversation_api.py`; migration/ownership tests; telephony callback test.
- Status: PARTIAL at product level: backend through `0006` is VERIFIED for its owner-reported slice; frontend lead management, user-requested Voice handoff tool, actual transfer, and delivery are missing.

### Telephony/inbound calls

- Purpose: provider-neutral policy/number/call/event persistence and deterministic transfer/callback decisions in development simulation.
- Files: `telephony/contracts.py`, `schemas.py`, `service.py`; `database/models/telephony.py`; migration `0007`; `docs/inbound-call-backend.md`; application routes.
- Important symbols: `TelephonyAdapter` protocol; `TelephonyService.receive_call`, `apply_event`, `link_lead`; `transition_call`, `enforce_call_limits`, `is_staff_available`; `InboundCallEventType`, `CallAction`.
- Callers: only development HTTP routes/tests. No concrete adapter calls the protocol, and no provider webhook route calls `verify_inbound_webhook`.
- Related models: `AgencyCallPolicy`, `AgencyInboundNumber`, `InboundCall`, immutable `InboundCallEvent`, `AgencyLead`, `LeadHandoffRequest`, `AuditEvent`.
- Tests: `tests/test_telephony_policy.py`; one integration scenario in `tests/database/test_telephony_api.py`; migration/ownership assertions.
- Status: PARTIAL. Neutral orchestration is IMPLEMENTED—UNVERIFIED. Signed ingress, concrete provider commands, normalization from provider payloads, DTMF, duration control, Voice/intake reuse, delivery, and usage metering are missing.

### Notifications

- Purpose stated by interface: handoff notification delivery.
- Files/symbols: `notifications/contracts.py:NotificationPort`, `HandoffNotification`, `NotificationDeliveryError`.
- Callers/models/routes/tests: none.
- Status: NOT IMPLEMENTED. A protocol alone is not a working capability.

## Database and migrations

- Models: `database/models/*.py`; exports and explicit `TABLE_OWNERSHIP` live in `database/models/__init__.py`.
- Connection: `database/connection.py:create_database_engine`, `create_migration_engine`, `check_database_readiness`.
- Alembic: `migrations/env.py`; linear revisions `20260802_0001` through `20260808_0007`.
- PostgreSQL-specific behavior: UUID/JSONB, restrictive FKs, CHECK/unique/index constraints, a shared mutable-row trigger, immutable-intake trigger, and immutable-call-event trigger.
- Tests: `tests/database/test_migrations.py`, `test_table_ownership.py`, `test_connection_settings.py`.
- Status: PARTIAL. Static head is `0007`; owner notes support verification through `0006`, while `0007` and the current combined tree are IMPLEMENTED—UNVERIFIED. See `03-database-and-migrations.md`.

## Audit, idempotency, and quotas

- Audit: `AuditEvent` plus content-minimized event creation in conversation, receptionist, FAQ, lead, and telephony services. Audit rows have no update route; unlike intakes/call events, the database does not have an audit immutability trigger. Status: PARTIAL.
- Idempotency: `IdempotencyRecord`; transactionally used by confirmation and handoff creation. Telephony receive dedupes by `(adapter_name, source_call_reference)` and events by `(inbound_call_id, event_key)` rather than the HTTP idempotency table. Status: PARTIAL.
- Quotas: Voice authorization enforces one concurrent and a daily setting; telephony receive enforces policy concurrent/daily counts. No durable usage/cost meter or entitlements exist. Status: PARTIAL.

## Tests and important documentation

Test presence does not establish execution. Python tests live in `tests/` and `tests/database/`; six frontend test files were statically observed under `apps/web/src`. Database fixture `tests/database/conftest.py:migrated_database` downgrades a disposable database to base, upgrades to head, then downgrades on teardown; the current session warns a previous run was interrupted during downgrade.

Read in this order:

1. `docs/project-state.md` and `docs/_local/current-session.md`.
2. This continuation pack.
3. Current feature docs: `docs/ai-receptionist-product-plan.md`, `docs/inbound-call-backend.md`, `docs/lead-handoff-api.md`, `docs/elevenlabs-agent-setup.md`, `docs/database-setup.md`.
4. Historical roadmap context in `07-remaining-build-plan.md`; the original PDFs and `implementation-backlog.md` are deleted in the working tree but were inspected from HEAD for this audit.
