# Insurance Operations AI

The repository contains a Next.js frontend, FastAPI web service, Python worker, and shared Neon-compatible PostgreSQL persistence. The current task branch adds the protected actor and minimal customer foundation required before browser Voice AI intake.

## Requirements

- Node.js 22
- Python 3.13

## Setup

```bash
cp .env.example .env
set -a
source .env
set +a
npm ci
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Set `DATABASE_URL` to the Neon pooled runtime URL and `DIRECT_DATABASE_URL` to the direct Neon URL used by Alembic. Set `TEST_DATABASE_URL` to a separate disposable database. See `docs/database-setup.md` for SSL, migration, and isolation requirements.

Set `SUPABASE_AUTH_ISSUER` and `SUPABASE_AUTH_JWKS_URL` from the approved Supabase project. The API accepts only asymmetric Supabase access tokens with the configured issuer and audience. Never add a service-role key or access token to repository files.

The two authentication-slice dependencies are narrow: PyJWT's cryptographic extra validates asymmetric JWT/JWKS signatures and `email-validator` supplies standards-based validation for optional customer email addresses.

## Database

Apply the current migration and seed the single development agency:

```bash
alembic upgrade head
insurance-operations-seed-development
```

The seed is idempotent, creates the approved development agency identity, and refuses to run unless `APP_ENVIRONMENT=development`.

## Start

Run each command in a separate configured shell:

```bash
npm run dev:web
```

```bash
uvicorn insurance_operations.api:app --host "$API_HOST" --port "$API_PORT" --reload
```

```bash
insurance-operations-worker
```

Open `http://localhost:3000`. API liveness does not depend on PostgreSQL; readiness does:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

Protected API examples require an existing Supabase user mapped to one active `app_users` row and one active `agency_memberships` row:

```bash
curl -H "Authorization: Bearer <access-token>" \
  http://127.0.0.1:8000/api/v1/me

curl -X POST http://127.0.0.1:8000/api/v1/customers \
  -H "Authorization: Bearer <access-token>" \
  -H "Idempotency-Key: <unique-key>" \
  -H "Content-Type: application/json" \
  --data '{"full_name":"Synthetic Customer","email":"synthetic@example.test"}'
```

`/app` is only a protected shell, not a sign-in flow. It expects the future server-side authentication integration to set the cookie named by `AUTH_ACCESS_TOKEN_COOKIE_NAME` with `HttpOnly`, `Secure`, and `SameSite=Lax` protections. Do not expose an access token through client JavaScript.

## Verify

```bash
npm run verify:web
ruff format --check .
ruff check .
mypy apps/backend/src tests
APP_ENVIRONMENT=test pytest
alembic check
insurance-operations-worker --check
```

For focused verification of this slice:

```bash
pytest tests/test_authentication.py tests/test_api.py -vv
APP_ENVIRONMENT=test pytest tests/database/test_customer_api.py -vv
```

Database tests downgrade and rebuild only the database selected by `TEST_DATABASE_URL`; never point it at development, preview, or production. The seven approved Release 1 planning PDFs are retained in `docs/release1/`. Read `AGENTS.md` and `docs/project-state.md` before extending the system.
