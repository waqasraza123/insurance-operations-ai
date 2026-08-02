# Database Setup

## Dependencies

- SQLAlchemy 2 owns typed models, engine construction, and transaction boundaries.
- Alembic owns forward database migrations; application startup never creates tables.
- psycopg 3 is the only PostgreSQL driver. The binary extra keeps local and CI setup small and does not add another database abstraction.

No database helper framework, async driver, container wrapper, or seed framework is included.

## Environments

Use separate databases or Neon branches for development and tests.

- `DATABASE_URL`: pooled runtime connection used by FastAPI and worker.
- `DIRECT_DATABASE_URL`: direct connection used by Alembic. It may fall back to `DATABASE_URL` outside tests, but Neon should provide a direct URL.
- `TEST_DATABASE_URL`: isolated disposable database required when `APP_ENVIRONMENT=test`.
- `DATABASE_SSL_MODE`: `require`, `verify-ca`, or `verify-full` for Neon. `disable` is permitted only for local or CI PostgreSQL and rejected in production.

Runtime engines use pre-ping, bounded local pooling, LIFO reuse, a short pool timeout, and connection recycling. Alembic uses `NullPool` so migrations do not retain application connections. Do not commit any connection URL.

## Development Setup

1. Create a Neon project or development branch and database.
2. Copy `.env.example` to `.env`.
3. Put the pooled Neon URL in `DATABASE_URL` and the direct Neon URL in `DIRECT_DATABASE_URL`.
4. Create a separate disposable database or Neon branch and put it in `TEST_DATABASE_URL`.
5. Export the environment values before running backend commands.

Neon URLs may use either `postgresql://` or `postgresql+psycopg://`; the application normalizes them to psycopg 3.

## Migrations

Apply all migrations:

```bash
alembic upgrade head
```

Inspect the current revision:

```bash
alembic current
```

Check model and migration agreement after intentional model changes:

```bash
alembic check
```

Only create a revision after an approved schema change:

```bash
alembic revision --autogenerate -m "describe approved change"
```

Review every generated migration. Never run a destructive migration against shared data without explicit owner approval.

## Development Seed

After migrating a development database:

```bash
insurance-operations-seed-development
```

The command creates only `Development Agency` with slug `development-agency`, environment kind `DEVELOPMENT`, and UUID `00000000-0000-4000-8000-000000000001`. Repeated execution is safe. It creates no users, memberships, customers, or demo data and refuses non-development environments.

## Foundation Tables

- `agencies`: root agency identity.
- `app_users`: global application identity profile keyed by a future authentication subject.
- `agency_memberships`: restrictive ownership link between an agency and application user.
- `customers`: agency-owned contact aggregate with normalized search fields and structured address.
- `audit_events`: append-only, agency-owned business history with explicit resource references.
- `idempotency_records`: agency-owned request outcome protection scoped by actor type, actor identity, route, and key.

All primary keys are UUIDs. Mutable aggregates use UTC timestamps and a database trigger that updates `updated_at` and increments a positive `row_version`. Business ownership foreign keys use `RESTRICT`; no cascade deletion is introduced. Nullable demo and future-resource UUIDs receive foreign keys only when their approved parent tables are added in migration order.

## Test Database

Database tests intentionally downgrade and rebuild the database selected by `TEST_DATABASE_URL`. Confirm the database is disposable before running:

```bash
APP_ENVIRONMENT=test pytest tests/database
```

CI uses PostgreSQL 17 with SSL disabled only inside the isolated job service.
