# Insurance Operations AI

Task 001 provides the runnable engineering foundation for the Release 1 document-first insurance operations platform. It contains a Next.js frontend, a FastAPI health service, and a separate Python worker runtime. Product features and external-service integrations are intentionally deferred.

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

Open `http://localhost:3000` and query API health with:

```bash
curl http://127.0.0.1:8000/health
```

## Verify

```bash
npm run verify:web
ruff format --check .
ruff check .
mypy apps/backend/src tests
pytest
insurance-operations-worker --check
```

The seven approved Release 1 planning PDFs are retained in `docs/release1/`. Read `AGENTS.md` and `docs/project-state.md` before extending the system.
