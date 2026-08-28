# CoverOps — Insurance Voice AI SaaS Starter Kit

A development-ready foundation for building an insurance agency Voice AI SaaS
with browser and telephone agents, approved knowledge, confirmed lead intake,
and human handoff.

CoverOps combines a **Next.js frontend**, **FastAPI backend**, **PostgreSQL**,
**ElevenLabs Voice AI**, and **Twilio telephony** behind provider-neutral
application services.

> **Important:** CoverOps is a starter architecture and synthetic-data
> demonstration. It is not a production-ready insurance SaaS and must not be
> used with real customer data without completing the production work described
> below.

## What ships

The current starter foundation includes:

- Browser Voice AI using authenticated ElevenLabs WebRTC.
- Inbound telephone AI through Twilio and a separate ElevenLabs phone agent.
- Agency-approved FAQ retrieval with source references.
- AI disclosure and consent gates.
- Structured insurance-interest intake.
- Explicit browser review and confirmation.
- Explicit verbal phone readback confirmation.
- Transactional customer, confirmed intake, and lead creation.
- Callback and live-transfer handoff foundations.
- Provider-neutral application state.
- Agency ownership foundations.
- Audit records and idempotency protections.
- Conversation and call quotas.
- Alembic-managed PostgreSQL migrations.
- Synthetic Harborline Insurance demo data.

## What you still add before production

This repository intentionally does not claim to be a finished production SaaS.

A production implementation still requires:

- Production authentication and agency onboarding.
- Roles and permissions.
- Billing, plans, and entitlements.
- Final lead and operations dashboards.
- Durable notification delivery.
- CRM and agency-management-system integrations.
- Usage and cost metering.
- Retention, export, and deletion workflows.
- Production observability and incident response.
- Deployment and operational hardening.
- Security, privacy, regulatory, and compliance review for the intended use.

## Safety boundaries

The receptionist is designed as a front-desk assistant.

It must not:

- quote insurance
- recommend coverage
- choose limits
- bind coverage
- verify coverage
- make underwriting decisions
- make claims decisions
- improvise answers outside approved agency knowledge

Unsupported or regulated requests should be handed to agency staff.

Raw audio is not retained by the application.

## Demo identity

**CoverOps** is the starter-kit product.

**Harborline Insurance** is the fictional agency used in demonstrations and
seed data.

The internal Python namespace remains `insurance_operations` to avoid
unnecessary code and migration churn.

See the [branding guide](docs/branding.md).

## Architecture

```text
Browser
   |
   | WebRTC
   v
ElevenLabs Voice AI
   |
   | approved application tools
   v
FastAPI ---------------- PostgreSQL
   |
   +---- FAQ / intake / lead / handoff services


Telephone caller
   |
   v
Twilio
   |
   v
ElevenLabs phone agent
   |
   | authenticated tools + signed callbacks
   v
FastAPI ---------------- PostgreSQL
```

FastAPI remains authoritative for business rules, ownership, validation,
confirmation, idempotency, quotas, audit records, and persistence.

Provider-specific behavior remains isolated inside adapters.

## Technology stack

### Web

- Next.js
- React
- TypeScript
- ElevenLabs React SDK

### Backend

- Python 3.13
- FastAPI
- SQLAlchemy 2
- Pydantic
- Alembic

### Data

- PostgreSQL
- Neon

### Voice and telephony

- ElevenLabs Voice AI
- WebRTC
- Twilio Voice

## Quickstart

Requirements:

- Node.js 26
- Python 3.13
- PostgreSQL-compatible Neon development database

Create local environment files:

```bash
cp .env.example .env
cp apps/web/.env.example apps/web/.env
```

Install dependencies:

```bash
npm ci

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Load backend environment variables:

```bash
set -a
source .env
set +a
```

Apply the development database:

```bash
alembic upgrade head
insurance-operations-seed-development
```

The seed creates the fictional Harborline Insurance agency and deterministic
development records.

Never use real customer information in the development environment.

## Run locally

Start the web application:

```bash
npm run dev:web
```

Start FastAPI in another configured shell:

```bash
source .venv/bin/activate
set -a
source .env
set +a

uvicorn insurance_operations.api:app \
  --host "$API_HOST" \
  --port "$API_PORT" \
  --reload
```

Start the worker separately when required:

```bash
insurance-operations-worker
```

Open:

```text
http://localhost:3000
```

## Setup tracks

### Foundation only

Keep Voice AI and telephone features disabled.

This lets you inspect the frontend, backend, database model, agency
configuration, FAQ system, lead foundations, and application architecture
without configuring a voice provider.

### Browser Voice AI

Follow:

[ElevenLabs browser agent setup](docs/elevenlabs-agent-setup.md)

The browser receives a short-lived WebRTC credential from FastAPI. The
ElevenLabs API key remains server-side.

### Inbound telephone AI

Follow:

- [ElevenLabs phone agent setup](docs/elevenlabs-phone-agent-setup.md)
- [Telephony provider setup](docs/telephony-provider-setup.md)
- [Client phone demo runbook](docs/client-phone-demo-runbook.md)

Telephone mode uses a separate ElevenLabs phone agent while Twilio retains
carrier and transfer responsibility.

Do not advertise the telephone demo as live until the provider dashboard and
synthetic carrier-call checklist have been completed.

## Environment configuration

The root `.env` contains backend, database, provider, and secret configuration.

`apps/web/.env` contains only browser-safe `NEXT_PUBLIC_*` configuration.

Never expose:

- database credentials
- ElevenLabs API keys
- Twilio credentials
- provider webhook secrets
- demo administrator secrets

Never commit `.env` files.

See [database setup](docs/database-setup.md).

## Verification

Before running database tests, confirm that `TEST_DATABASE_URL` points to a
separate disposable database.

```bash
npm run verify:web

ruff format --check .
ruff check .
mypy apps/backend/src tests

APP_ENVIRONMENT=test alembic upgrade head
APP_ENVIRONMENT=test alembic current
APP_ENVIRONMENT=test alembic check
APP_ENVIRONMENT=test pytest

insurance-operations-worker --check
```

Database downgrade or rebuild operations must only be run against a database
that has been explicitly confirmed as disposable.

## Current limitations

Production authentication, billing, real-customer-data operation, final
operations UI, durable notifications, CRM integrations, detailed usage
metering, retention/deletion workflows, and full production hardening remain
outside the current starter foundation.

The hosted and local demonstrations are intended for fictional data only.

## Project documentation

- [Brand identity](docs/branding.md)
- [Database setup](docs/database-setup.md)
- [Browser Voice AI setup](docs/elevenlabs-agent-setup.md)
- [Phone agent setup](docs/elevenlabs-phone-agent-setup.md)
- [Telephony provider setup](docs/telephony-provider-setup.md)
- [Lead and handoff API](docs/lead-handoff-api.md)
- [Client phone demo runbook](docs/client-phone-demo-runbook.md)

Additional architecture, customization, deployment, demo, and
production-readiness documentation will be added as part of the starter-kit
presentation pass.
