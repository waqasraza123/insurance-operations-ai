# Insurance Operations AI

The repository contains the Release 1 foundation for the document-first insurance operations platform: a Next.js frontend, FastAPI web service, Python worker, and a shared Neon-compatible PostgreSQL persistence layer. Product workflows remain intentionally deferred.

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

## Verify

```bash
npm run verify:web
ruff format --check .
ruff check .
mypy apps/backend/src tests
pytest
alembic check
insurance-operations-worker --check
```

Database tests downgrade and rebuild only the database selected by `TEST_DATABASE_URL`; never point it at development, preview, or production. The seven approved Release 1 planning PDFs are retained in `docs/release1/`. Read `AGENTS.md` and `docs/project-state.md` before extending the system.
