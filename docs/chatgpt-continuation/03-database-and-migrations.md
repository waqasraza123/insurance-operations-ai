# Database and Migrations

## Evidence boundary

The repository contains a linear Alembic chain whose static head is `20260808_0007`. That means **migration file exists**. It does not mean **migration has been applied and verified** on the owner's development, test, staging, or production database. Static inspection cannot determine an actual database's `alembic_version`.

Overall current persistence status: PARTIAL. Owner-reported evidence covers slices through `0006`; `0007` and the aggregate dirty tree are IMPLEMENTED—UNVERIFIED.

## Migration chain

| Order | Revision | File and purpose | Snapshot evidence | Current status |
|---:|---|---|---|---|
| 1 | `20260802_0001` | `migrations/versions/20260802_0001_persistence_foundation.py`: `pg_trgm`, identity, customers, audit, idempotency, indexes, shared mutable-record trigger | Historical repository notes report migration/static/runtime checks | VERIFIED for the recorded foundation snapshot |
| 2 | `20260802_0002` | `.../20260802_0002_conversation_foundation.py`: sessions, immutable confirmed intakes, indexes/triggers | Historical repository notes report Voice foundation checks | VERIFIED for the recorded Voice snapshot |
| 3 | `20260807_0003` | `.../20260807_0003_agency_receptionist_settings.py`: one versioned settings row per agency | Owner reported upgrade/downgrade/static/API checks | VERIFIED for the recorded settings slice snapshot |
| 4 | `20260808_0004` | `.../20260808_0004_shorten_receptionist_constraint_name.py`: rename the PostgreSQL-truncated categories constraint to a stable name | Owner reported migration/drift checks | VERIFIED for the recorded settings slice snapshot |
| 5 | `20260808_0005` | `.../20260808_0005_agency_approved_faqs.py`: versioned approved FAQ rows | Owner reported migration/static/focused/drift checks | VERIFIED for the recorded FAQ slice snapshot |
| 6 | `20260808_0006` | `.../20260808_0006_leads_and_handoffs.py`: leads and handoff requests | Owner reported migration/static/focused/drift checks | VERIFIED for the recorded lead/handoff slice snapshot |
| 7 | `20260808_0007` | `.../20260808_0007_inbound_call_orchestration.py`: call policies/numbers/calls/immutable events; handoff-call FK/unique constraint | Only static audit and unexecuted test files in the present handoff | IMPLEMENTED—UNVERIFIED |

The chain is linear: `0001 -> 0002 -> 0003 -> 0004 -> 0005 -> 0006 -> 0007`. There is no merge revision. `0007` is the current repository head, not a confirmed database head.

## Tables, ownership, and core constraints

All tables use UUID primary keys. `TABLE_OWNERSHIP` in `database/models/__init__.py` explicitly classifies all 16 current tables. All foreign keys declared here use `ON DELETE RESTRICT`; no cascade deletion is implemented.

| Table/model | Ownership and relationships | Important constraints/lifecycle | Status |
|---|---|---|---|
| `agencies` / `Agency` | Global tenant root | Unique lowercase `slug`; environment in DEVELOPMENT/DEMO/PRODUCTION; archivable; versioned | VERIFIED for foundation snapshot |
| `app_users` / `AppUser` | Global identity projection | Unique `auth_subject`; ACTIVE/DISABLED with `disabled_at` consistency; versioned | VERIFIED for foundation snapshot |
| `agency_memberships` / `AgencyMembership` | Agency-owned; FKs to agency and app user | Unique agency/user; ACTIVE/INACTIVE; versioned | VERIFIED for foundation snapshot |
| `customers` / `Customer` | Agency-owned; `created_by -> app_users`; optional non-FK demo session | Name/country/state bounds; normalized/search fields; archivable/versioned; trigram search index | VERIFIED for foundation snapshot |
| `audit_events` / `AuditEvent` | Agency-owned; optional actor/customer FKs; several future-domain UUID references are not FKs | Actor enum and positive event version; append-only by service convention only | PARTIAL |
| `idempotency_records` / `IdempotencyRecord` | Agency-owned; actor-scope UUID is deliberately generic | Unique actor scope + route + key; key length; IN_PROGRESS/COMPLETED/FAILED; expiry | VERIFIED for confirmation/handoff slice behavior |
| `conversation_sessions` / `ConversationSession` | Agency-owned; `initiated_by -> app_users` | REQUESTING/AUTHORIZED/REVIEW_PENDING/CONFIRMED/FAILED/EXPIRED; duration 1..180; confirmed timestamp consistency; provider metadata object; versioned | VERIFIED for recorded Voice snapshot; aggregate current tree unverified |
| `conversation_intakes` / `ConversationIntake` | Agency-owned; FKs to customer, unique session, creator | END_USER only; intent/transcript bounds; database trigger rejects UPDATE/DELETE; no row version | VERIFIED for recorded Voice snapshot |
| `agency_receptionist_settings` / `AgencyReceptionistSettings` | Agency-owned; creator/updater FKs | One per agency; content/contact/category bounds; at least one contact; versioned | VERIFIED for recorded settings slice |
| `agency_approved_faqs` / `AgencyApprovedFaq` | Agency-owned; creator/updater FKs | Unique agency + normalized question; ACTIVE/INACTIVE; content bounds; versioned | VERIFIED for recorded FAQ slice |
| `agency_leads` / `AgencyLead` | Agency-owned; FKs to customer and unique conversation intake | NEW/CONTACTED/QUALIFIED/CLOSED/ARCHIVED; LOW/NORMAL/HIGH; bounded summary; versioned | VERIFIED for recorded lead slice |
| `lead_handoff_requests` / `LeadHandoffRequest` | Agency-owned; FKs to lead, optional conversation session, optional inbound call | CALLBACK/LIVE_TRANSFER; contact method; REQUESTED/ACKNOWLEDGED/COMPLETED/CANCELLED with terminal timestamps; versioned; at most one row per non-null inbound call | `0006` behavior VERIFIED for recorded slice; `0007` call relation IMPLEMENTED—UNVERIFIED |
| `agency_call_policies` / `AgencyCallPolicy` | One agency-owned policy; creator/updater FKs | IANA timezone validated in schema; JSON array; transfer destination requirement; ring/concurrency/daily bounds; versioned | IMPLEMENTED—UNVERIFIED |
| `agency_inbound_numbers` / `AgencyInboundNumber` | Agency-owned; creator/updater FKs | Phone globally unique; ACTIVE/INACTIVE; versioned | IMPLEMENTED—UNVERIFIED |
| `inbound_calls` / `InboundCall` | Agency-owned; FKs to inbound number and optional lead | Unique adapter + source reference; allow-listed status; time/failure consistency; JSON metadata/snapshot objects; versioned | IMPLEMENTED—UNVERIFIED |
| `inbound_call_events` / `InboundCallEvent` | Agency-owned; FK to inbound call | Unique call + event key; bounded names/object details; database trigger rejects UPDATE/DELETE; no row version | IMPLEMENTED—UNVERIFIED |

Model files are under `apps/backend/src/insurance_operations/database/models/`. The matching table construction is distributed across the revision files above.

## Ownership relationships and enforcement

Every tenant-domain table has a non-null `agency_id` FK, except global `agencies`/`app_users`. Services constrain agency-owned lookups using the resolved `ActorContext.agency_id`; conversation session operations also require `initiated_by == actor.app_user_id`. Cross-tenant absence is returned as not found.

The database does not use composite `(agency_id, id)` foreign keys to prove that every linked record belongs to the same agency. For example, an inbound call's `lead_id` FK proves the lead exists but not that its `agency_id` matches the call. Current services perform that consistency check in agency-filtered queries. Therefore:

- Backend ownership authority: IMPLEMENTED—UNVERIFIED in the aggregate current tree.
- Database-enforced cross-agency relationship consistency: NOT IMPLEMENTED.
- Do not bypass services with unscoped repository helpers, background jobs, or provider callbacks.

## Row versions and mutable records

`VersionedMixin` begins `row_version` at 1. Migration `0001` creates `set_mutable_record_metadata()`, which assigns `updated_at = now()` and increments `row_version` on UPDATE. Later migrations attach it to each mutable versioned table.

Current trigger-protected mutable tables are agencies, app users, memberships, customers, conversation sessions, receptionist settings, approved FAQs, leads, handoff requests, call policies, inbound numbers, and inbound calls. Service schemas use `expected_row_version` for user-managed settings/FAQ/lead/handoff/telephony-policy/number/call-link mutations. Conversation state transitions instead lock owned rows and enforce lifecycle state.

`updated_at`/`row_version` server behavior was owner-reported VERIFIED for prior slices; `0007` trigger attachment is IMPLEMENTED—UNVERIFIED.

## Immutable and append-only records

- `conversation_intakes`: database-enforced immutable via `reject_conversation_intake_mutation()` from `0002`. VERIFIED for the recorded Voice snapshot.
- `inbound_call_events`: database-enforced immutable via `reject_inbound_call_event_mutation()` from `0007`. IMPLEMENTED—UNVERIFIED.
- `audit_events`: services only insert and expose no mutation route, but no database trigger prevents update/delete. PARTIAL.
- `idempotency_records`: not immutable; they intentionally transition from IN_PROGRESS to COMPLETED/FAILED inside the owning operation.

## Transaction-sensitive relationships

- Confirmation: idempotency claim, owned session lock, customer, immutable intake, unique lead, three audits, session CONFIRMED, and stored response share one transaction in `ConversationService.confirm_intake`.
- Handoff: idempotency claim, lead lock/validation, handoff, audit, and stored response share one transaction in `LeadService.create_handoff`.
- FAQ/receptionist/lead/telephony mutations: row mutation and audit share one transaction.
- Telephony receive: policy lock, limits, call, immutable received event, and audit share one outer transaction; a nested transaction handles unique-race recovery.
- Telephony event: call lock, transition, immutable event, and audit share one transaction.
- Callback link: owned call lock, agency-filtered lead/customer/intake lookup, call link, optional handoff, event, and audit share one transaction.

Do not move audit/idempotency/event writes outside these transactions without an explicit architecture decision.

## Provider-neutral versus provider-specific storage

Core tables are provider-neutral. `conversation_sessions.provider_metadata` stores a sanitized adapter name/version/external session reference. `inbound_calls` stores an adapter name, provider source reference, sanitized adapter metadata, and a neutral policy snapshot. `inbound_call_events` stores normalized event types/details.

No raw provider payload table, signing secret, API credential, or raw-audio column exists. Provider-specific request validation and commands belong in adapter code, not models. Provider-neutral storage is PARTIAL because phone payload normalization is not yet implemented by a concrete adapter.

## Static model/migration observations

No direct model-versus-migration structural contradiction was found during static inspection of the current chain. This statement is not an Alembic drift check.

Important enforcement layering differences:

- Pydantic enforces true E.164 syntax and IANA timezone/window structure; database CHECK constraints enforce only narrower length/object/array and numeric invariants.
- Pydantic/service code enforces unique receptionist categories and FAQ normalization/matching semantics; the database enforces stored shape and normalized-question uniqueness.
- Services enforce same-agency relationships; simple FKs do not.
- Audit is append-only by convention, whereas intake and call-event immutability are database-enforced.
- `AgencyCallPolicy.availability_windows` has an ORM-side empty-list default; the migration has no server default. `TelephonyService` supplies the field on writes, so this is an operational caveat rather than a detected contradiction.

## Migration conflicts and risk

CONFLICT:
- source A: static repository chain declares `20260808_0007` as head.
- source B: `docs/_local/current-session.md` states the owner still needs to verify `0007` and warns an earlier database test was interrupted while downgrading the disposable test database.
- repository evidence: the `0007` file/model/tests exist, but this audit did not inspect an actual database or run Alembic.
- impact: a test database may be at an unknown revision; running focused tests without restoring it may produce misleading or destructive failures.
- recommended resolution: inspect the disposable test database's revision/state, restore it deliberately, then run the owner-approved `0007` sequence.
- owner decision required: no

CONFLICT:
- source A: historical Release 1 documents selected Supabase PostgreSQL/Auth/Storage.
- source B: current `docs/project-state.md`, settings, dependencies, and connection code require Neon PostgreSQL and contain no Supabase runtime/auth.
- repository evidence: `settings.py` accepts PostgreSQL URLs and Neon-safe configuration; no Supabase package/runtime code exists.
- impact: reviving old Supabase designs would violate the current architecture.
- recommended resolution: retain old documents only as history; continue Neon-only unless the owner explicitly reverses the decision.
- owner decision required: yes
