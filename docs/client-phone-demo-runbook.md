# Client Phone Demo Runbook

This runbook publishes the fictional Harborline phone-agent sandbox. It is not a
production pilot and must never receive real customer or insurance information.

## 1. Verification gate

Confirm `TEST_DATABASE_URL` is disposable and isolated, then run:

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
npm run verify:web
```

Do not continue until every result is clean and the disposable database has been
restored to Alembic head.

## 2. Render API

Create a Render Blueprint from `render.yaml`. Keep telephony disabled on the
first deploy by setting `TELEPHONY_PROVIDER_ENABLED=false`. Supply every
`sync: false` value in the Render dashboard; do not put secret values in Git.

Generate independent random values of at least 32 characters for
`DEMO_ADMIN_TOKEN` and `ELEVENLABS_PHONE_TOOL_SECRET`. Set
`DEMO_INBOUND_NUMBER_E164` to the temporary Twilio number and
`DEMO_TRANSFER_DESTINATION_E164` to an owner-controlled telephone number.

Set `WEB_ORIGIN` to the exact Vercel HTTPS origin. Use the Neon pooled URL for
`DATABASE_URL` and direct URL for `DIRECT_DATABASE_URL`.

Before enabling telephony, use the Render shell to run:

```bash
alembic upgrade head
alembic current
alembic check
insurance-operations-seed-development
```

Then confirm:

```bash
curl --fail --show-error https://<render-host>/health
curl --fail --show-error https://<render-host>/ready
curl --fail --show-error https://<render-host>/api/v1/demo/latest-phone-call
```

The demo endpoint must return `READY` and must not contain names, contact data,
transcripts, intake text, database IDs, provider IDs, or error details.

## 3. Vercel web

Create a Vercel project with `apps/web` as its root directory. Configure:

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://<render-host>
NEXT_PUBLIC_CONVERSATION_AI_ENABLED=false
NEXT_PUBLIC_DEMO_SANDBOX_ENABLED=true
NEXT_PUBLIC_DEMO_PHONE_NUMBER=+1XXXXXXXXXX
```

After deployment, replace Render's `WEB_ORIGIN` with the exact production Vercel
origin and redeploy the API. Confirm `/phone-demo` renders, is marked `noindex`,
and does not link to receptionist settings or FAQ administration.

## 4. ElevenLabs

Follow `docs/elevenlabs-phone-agent-setup.md`. Configure the private phone agent,
μ-law 8000 Hz input/output, 180-second maximum, privacy controls, four blocking
tools, and the signed post-call webhook:

```text
https://<render-host>/api/v1/providers/elevenlabs/post-call
```

Use the Render value of `ELEVENLABS_PHONE_TOOL_SECRET` as the bearer secret for
all four tools. Store it only in the ElevenLabs secrets manager.

## 5. Twilio and enablement

Configure the temporary number's incoming-call webhook as HTTP POST:

```text
https://<render-host>/api/v1/providers/twilio/inbound
```

Set these exact Render values because Twilio signature verification includes the
full URL:

```dotenv
TWILIO_INBOUND_WEBHOOK_URL=https://<render-host>/api/v1/providers/twilio/inbound
TWILIO_TRANSFER_CALLBACK_URL=https://<render-host>/api/v1/providers/twilio/transfer-result
```

Confirm the ElevenLabs model, voice, STT/TTS, retention, audio saving, region,
and billing guard. Set `ELEVENLABS_PRIVACY_CONFIRMED=true`, then set
`TELEPHONY_PROVIDER_ENABLED=true` and redeploy Render.

Restrict Twilio geographic permissions to required destinations, set low balance
and usage alerts, and keep the application limits at two concurrent calls, ten
calls per day, and 180 seconds.

## 6. Acceptance and rollback

Use fictional data for every check:

- decline consent and confirm that no customer, intake, lead, or transcript exists
- answer an office-hours question only from an approved FAQ
- confirm a fictional intake and observe exactly one lead on `/phone-demo`
- replay tool/webhook deliveries and confirm no duplicate lead
- complete a live transfer and observe `TRANSFERRED`
- reject or ignore a transfer and observe callback fallback
- confirm the 180-second cutoff
- inspect application/provider logs and the database for raw audio or secrets
- wait 15 minutes and confirm the public result returns to `READY`

To roll back, set `TELEPHONY_PROVIDER_ENABLED=false` first, redeploy Render, and
then detach the Twilio webhook. Do not delete database records during rollback.
