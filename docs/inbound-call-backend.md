# Inbound Call Backend

This backend-only slice establishes provider-neutral telephone orchestration. It does not connect a real telephone vendor yet. A concrete adapter, signed webhook endpoint, and provider account configuration remain required before real calls can enter the system.

## Implemented Contracts

- One versioned `agency_call_policies` record per agency controls inbound enablement, IANA timezone, weekly availability windows, transfer destination, ring timeout, concurrency, daily usage, callback fallback, and safe messages.
- `agency_inbound_numbers` maps globally unique E.164 numbers to agencies without storing provider number identifiers in business APIs.
- `inbound_calls` stores provider-neutral state, a policy snapshot, bounded adapter metadata, optional caller number, and optional linked lead. It stores no raw audio.
- Immutable `inbound_call_events` deduplicate adapter events by call and event key.
- A callback fallback creates at most one `lead_handoff_request` per inbound call after a confirmed lead is linked.
- Telephony and notification protocols isolate webhook verification, transfer execution, and future notification delivery from business services.

## Call State Machine

Primary flow:

```text
RECEIVED -> CONNECTED -> COMPLETED
                     -> TRANSFER_PENDING -> TRANSFERRED
                                         -> CALLBACK_PENDING
                     -> CALLBACK_PENDING -> CALLBACK_REQUESTED
Any nonterminal state -> FAILED on provider failure
```

Rules:

- Reception requires an active number, enabled policy, available concurrency, and remaining daily usage.
- Every accepted call receives an immutable policy snapshot so policy edits cannot alter an active call unexpectedly.
- `TRANSFER_REQUESTED` evaluates the policy snapshot in the agency's local timezone.
- Available staff returns a transfer destination and bounded ring timeout.
- After-hours, disabled, or failed transfer returns callback collection when fallback is enabled.
- Linking a confirmed agency-owned lead while callback is pending creates one callback handoff and changes the call to `CALLBACK_REQUESTED`.
- Ending a call while callback collection is incomplete fails with `CALLBACK_NOT_CAPTURED` rather than claiming success.
- Exact receive and event retries return the existing result; reused keys with changed data conflict.

## Development APIs

- `GET|PUT /api/v1/development/call-policy`
- `GET|POST /api/v1/development/inbound-numbers`
- `POST /api/v1/development/inbound-numbers/{number_id}/status`
- `GET|POST /api/v1/development/inbound-calls`
- `GET /api/v1/development/inbound-calls/{call_id}`
- `POST /api/v1/development/inbound-calls/{call_id}/events`
- `POST /api/v1/development/inbound-calls/{call_id}/lead`

These routes are for deterministic backend development and simulation. A real adapter must use a separate signed ingress route and must never trust caller-supplied provider identity or event data.

## Provider Boundaries

`TelephonyAdapter` must:

1. Verify the provider webhook signature against the exact raw body.
2. Return a normalized `VerifiedInboundCall` without exposing credentials.
3. Execute transfer instructions supplied by the business service.
4. Convert provider callbacks into stable event keys and provider-neutral events.

`NotificationPort` receives only agency, lead, handoff, and event identifiers. External email/SMS payload construction, credentials, retry, and delivery status must remain in an adapter plus durable outbox implementation.

## Owner Verification

Apply and inspect the new disposable-test migration:

```bash
set -a; source .env; set +a
APP_ENVIRONMENT=test .venv/bin/alembic upgrade head
APP_ENVIRONMENT=test .venv/bin/alembic current
APP_ENVIRONMENT=test .venv/bin/alembic check
```

Run static and focused checks:

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy apps/backend/src tests
APP_ENVIRONMENT=test .venv/bin/pytest \
  tests/test_telephony_policy.py \
  tests/database/test_migrations.py \
  tests/database/test_table_ownership.py \
  tests/database/test_telephony_api.py
```

Then run the complete backend suite and restore head:

```bash
APP_ENVIRONMENT=test .venv/bin/pytest
APP_ENVIRONMENT=test .venv/bin/alembic upgrade head
APP_ENVIRONMENT=test .venv/bin/alembic check
```

Manual contract checks:

1. Reject invalid timezone, overlapping windows, non-E.164 numbers, missing transfer destination, and stale policy versions.
2. Reject calls for inactive/unmapped numbers and disabled policies.
3. Confirm duplicate adapter/source references do not create duplicate calls.
4. Confirm concurrency and daily limits return HTTP 429.
5. Confirm open-hours transfer returns `TRANSFER` with the configured destination and timeout.
6. Confirm after-hours and transfer-failure paths return `COLLECT_CALLBACK`.
7. Confirm event-key replay returns `replayed=true` and changing its type, timestamp, or failure code returns HTTP 409.
8. Link a confirmed lead while callback is pending and confirm exactly one handoff references the inbound call.
9. End a call before callback capture and confirm `CALLBACK_NOT_CAPTURED`.
10. Inspect PostgreSQL and logs for absence of raw audio, credentials, hidden prompts, and transcript drafts.

Do not configure real numbers, provider webhooks, or real caller data until a concrete adapter, signed ingress, production authentication, privacy review, and deployment controls are implemented and separately verified.
