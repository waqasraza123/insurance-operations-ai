# Lead and Handoff Backend

This backend-only slice turns each newly confirmed conversation intake into one agency-owned lead and provides the shared human-handoff workflow required by browser and telephone channels. All routes currently use the deterministic development actor; production authentication remains deferred.

## Persistence Contract

- `agency_leads` has exactly one record per immutable `conversation_intake`.
- Confirmation creates the customer, intake, lead, three audit events, and idempotency outcome in one transaction.
- Leads begin as `NEW` with `NORMAL` urgency unless confirmation supplies `LOW`, `NORMAL`, or `HIGH`.
- Lead summaries initially use the confirmed intake intent and can be updated with optimistic concurrency.
- `lead_handoff_requests` records either `CALLBACK` or `LIVE_TRANSFER` intent without provider identifiers.
- Handoff creation requires `Idempotency-Key`. Replaying the same key and body returns the original response; changing the body returns a conflict.
- Callback contact methods are validated against the confirmed customer contact information.
- Audit details contain resource IDs, status, and transition metadata but not callback reasons, availability, transcript text, or contact values.

## API Contract

- `GET /api/v1/development/leads?status=NEW&limit=25&offset=0`
  - Returns paginated lead summaries and open-handoff counts.
- `GET /api/v1/development/leads/{lead_id}`
  - Returns customer details, immutable intake intent/transcript, handoffs, and customer-scoped audit history.
- `PUT /api/v1/development/leads/{lead_id}`
  - Replaces `summary` and `urgency`; requires `expected_row_version`.
- `POST /api/v1/development/leads/{lead_id}/status`
  - Applies a guarded lifecycle transition and requires `expected_row_version`.
- `GET /api/v1/development/leads/{lead_id}/handoff-requests`
  - Lists the lead's handoff requests.
- `POST /api/v1/development/leads/{lead_id}/handoff-requests`
  - Creates an idempotent callback or live-transfer request.
- `POST /api/v1/development/handoff-requests/{handoff_id}/status`
  - Applies a guarded handoff transition and optionally records whether a live transfer was attempted.

Lead transitions:

- `NEW` → `CONTACTED`, `QUALIFIED`, `CLOSED`, or `ARCHIVED`
- `CONTACTED` → `QUALIFIED`, `CLOSED`, or `ARCHIVED`
- `QUALIFIED` → `CLOSED` or `ARCHIVED`
- `CLOSED` → `ARCHIVED`
- `ARCHIVED` is terminal

Handoff transitions:

- `REQUESTED` → `ACKNOWLEDGED`, `COMPLETED`, or `CANCELLED`
- `ACKNOWLEDGED` → `COMPLETED` or `CANCELLED`
- `COMPLETED` and `CANCELLED` are terminal

## Owner Verification

Restore the disposable test database first because the previously interrupted run may have left it below migration head:

```bash
set -a; source .env; set +a
APP_ENVIRONMENT=test .venv/bin/alembic upgrade head
APP_ENVIRONMENT=test .venv/bin/alembic current
```

Static and focused checks:

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy apps/backend/src tests
APP_ENVIRONMENT=test .venv/bin/pytest tests/database/test_migrations.py tests/database/test_table_ownership.py tests/database/test_conversation_api.py
```

Full backend checks after the focused checks pass:

```bash
APP_ENVIRONMENT=test .venv/bin/pytest
APP_ENVIRONMENT=test .venv/bin/alembic upgrade head
APP_ENVIRONMENT=test .venv/bin/alembic check
```

Manual API checks:

1. Authorize and end a synthetic conversation, then confirm its intake with an idempotency key.
2. Confirm that the response has `lead_id` and the lead list contains one `NEW` lead.
3. Read the lead detail and confirm the transcript and `LEAD_CREATED` audit event are present.
4. Update summary/urgency, then transition `NEW` → `CONTACTED` using each returned row version.
5. Retry a stale version and confirm HTTP 409.
6. Create a phone callback twice with the same key/body and confirm one resource plus `Idempotent-Replayed: true`.
7. Reuse that key with a changed body and confirm HTTP 409.
8. Confirm a phone callback fails when the customer has no phone and an email callback fails when the customer has no email.
9. Transition a handoff to `ACKNOWLEDGED`, then `COMPLETED`; confirm a terminal transition is rejected.
10. Inspect audit details and confirm they contain no transcript, contact value, reason, or availability text.

Do not apply migrations to the development database until these owner-run checks pass.
