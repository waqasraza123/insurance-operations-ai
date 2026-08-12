# Insurance Operations AI

Next.js frontend, FastAPI API, separate Python worker, and shared Neon PostgreSQL persistence. The active product slice provides an agency-configurable, synthetic AI receptionist with consent-gated browser voice, explicit review, and audited intake confirmation.

## Setup

Requires Node.js 26 and Python 3.13.

```bash
cp .env.example .env
cp apps/web/.env.example apps/web/.env
set -a
source .env
set +a
npm install --package-lock-only --ignore-scripts --workspace @insurance-operations/web
npm ci
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Use a Neon pooled URL for `DATABASE_URL`, a direct URL for `DIRECT_DATABASE_URL`, and a separate disposable database for `TEST_DATABASE_URL`. Never commit `.env` or a connection string. See [database setup](docs/database-setup.md).

## Development Database

```bash
alembic upgrade head
insurance-operations-seed-development
```

The idempotent seed creates one development agency, deterministic synthetic actor, active membership, and synthetic receptionist profile. It refuses test and production environments.

## Voice AI Configuration

Follow [the agent setup contract](docs/elevenlabs-agent-setup.md), then set the server-only `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, and privacy attestation in the repository-root `.env`. Enable the backend feature flag only for development:

Keep both feature flags `false` until the owner completes the provider privacy and billing checklist. The owner must explicitly select the LLM, STT, TTS, and voice in ElevenLabs; the application does not silently select substitutes.

```dotenv
APP_ENVIRONMENT=development
CONVERSATION_AI_ENABLED=true
ELEVENLABS_PRIVACY_CONFIRMED=true
```

Enable the public feature flag separately in `apps/web/.env`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_CONVERSATION_AI_ENABLED=true
```

Do not use real customer data. The browser receives only a short-lived WebRTC token, never the API key.

## Run

Use separate configured shells:

```bash
npm run dev:web
```

```bash
uvicorn insurance_operations.api:app --host "$API_HOST" --port "$API_PORT" --reload
```

```bash
insurance-operations-worker
```

Open `http://localhost:3000`. Use **Configure receptionist** to review the seeded agency profile, then select **Talk to the receptionist**. Accept all three acknowledgements, speak with the assistant, finish within three minutes, edit the transcript/details, then confirm. Only confirmation persists the transcript and creates a customer.

## Verify

The web workspace loads public values from `apps/web/.env`; backend and worker commands load the repository-root `.env`. Confirm `TEST_DATABASE_URL` points only to an isolated disposable database before the downgrade:

```bash
npm run verify:web
ruff format --check .
ruff check .
mypy apps/backend/src tests
APP_ENVIRONMENT=test alembic downgrade base
APP_ENVIRONMENT=test alembic upgrade head
APP_ENVIRONMENT=test alembic current
APP_ENVIRONMENT=test alembic check
APP_ENVIRONMENT=test pytest
insurance-operations-worker --check
```

Manual QA: verify disabled flags hide the route; deny microphone permission; force a disconnect while connecting and while active; confirm the ending state prevents retry until cleanup finishes; observe the 3:00 countdown; test mute/unmute; confirm the 11th daily authorization is rejected with clear guidance; retry one transient confirmation with the same idempotency key; confirm an expired session requires a new conversation; inspect that no raw audio or draft transcript exists in PostgreSQL or logs; and verify provider audio saving/retention settings in the dashboard.

Follow the [AI receptionist product plan](docs/ai-receptionist-product-plan.md). Read `AGENTS.md` and `docs/project-state.md` before changing architecture or scope.
