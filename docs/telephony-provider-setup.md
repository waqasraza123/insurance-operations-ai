# Telephony Provider Setup

## Provider

Twilio is the first concrete telephone carrier.

Twilio-specific authentication, webhook fields, call identifiers, and transfer commands stay inside the Twilio adapter. Application business services remain provider-neutral.

## Implemented flow

The current slice implements:

- signed Twilio webhook verification
- inbound request normalization
- called-number to agency routing
- call-policy enforcement
- inbound call persistence
- provider webhook replay protection
- SYSTEM audit identity
- Twilio active-call transfer mapping
- ElevenLabs register-call execution and validated TwiML responses
- a separate authenticated ElevenLabs phone-agent tool contract
- explicit phone disclosure/consent gating
- immutable verbal-confirmation receipts
- signed post-call transcript finalization into customer, intake, and lead records
- signed Twilio transfer-result normalization
- development telephony management routes

The provider ingress route is:

`POST /api/v1/providers/twilio/inbound`

## Configuration

Provider execution remains disabled by default:

```dotenv
TELEPHONY_PROVIDER_ENABLED=false
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_INBOUND_WEBHOOK_URL=
TWILIO_TRANSFER_CALLBACK_URL=
ELEVENLABS_API_KEY=
ELEVENLABS_PHONE_AGENT_ID=
ELEVENLABS_PHONE_TOOL_SECRET=
ELEVENLABS_POST_CALL_WEBHOOK_SECRET=
ELEVENLABS_PRIVACY_CONFIRMED=false
PHONE_MAX_DURATION_SECONDS=180
PHONE_CONFIRMATION_WINDOW_MINUTES=30
```

Never commit Twilio credentials.

Both configured Twilio URLs must exactly match the externally visible HTTPS URLs
because each URL participates in signature verification.

## Responsibility boundary

Twilio owns:

- telephone connectivity
- webhook authentication
- provider call identifiers
- carrier-side call transfer execution

The application owns:

- inbound number mapping
- agency routing
- call policy
- concurrency limits
- daily limits
- application call state
- lead linkage
- callback fallback
- audit history

ElevenLabs remains the conversational AI provider and does not become the source
of truth for business call state. Follow
`docs/elevenlabs-phone-agent-setup.md` for the separate phone-agent contract.

## Not live yet

The implementation and migration `20260819_0008` have passed automated checks.
Attach only a temporary demo number until the provider-dashboard and fictional-call
acceptance checklist in `docs/client-phone-demo-runbook.md` passes.

The owner must verify:

```bash
ruff format --check .
ruff check .
mypy apps/backend/src tests

APP_ENVIRONMENT=test alembic current
APP_ENVIRONMENT=test alembic upgrade head
APP_ENVIRONMENT=test alembic current
APP_ENVIRONMENT=test alembic check
APP_ENVIRONMENT=test pytest \
  tests/test_phone_conversation_provider.py \
  tests/test_telephony_provider.py \
  tests/database/test_phone_receptionist_flow.py \
  tests/database/test_telephony_provider_ingress.py \
  tests/database/test_telephony_api.py \
  tests/database/test_migrations.py \
  tests/database/test_table_ownership.py
APP_ENVIRONMENT=test pytest
```

Confirm `TEST_DATABASE_URL` is disposable and isolated before any database
command. Do not run a downgrade or rebuild against an unconfirmed database.

After automated verification, use a temporary development Twilio number and
fictional data to check consent decline, approved FAQ lookup, confirmed intake,
exactly-once lead creation, open-hours transfer, failed/after-hours callback,
webhook replay, the 180-second stop, and the absence of stored raw audio.
