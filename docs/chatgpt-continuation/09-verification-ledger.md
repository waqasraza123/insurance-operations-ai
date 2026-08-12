# Verification Ledger

## Interpretation rule

A passed command applies only to the recorded snapshot and scope. It does not make later working-tree changes VERIFIED. The current working tree is dirty and no test, build, lint, type-check, migration, server, browser, worker, or live-provider check was run while creating this ledger.

“Owner-reported” means repository notes preserve the owner's result, not that this audit independently reproduced it. Unknown snapshot identifiers remain unknown rather than being guessed.

## Historical evidence preserved in the repository

| Date | Command/check | Scope | Result | Reported by | Commit or working-tree snapshot | Notes |
|---|---|---|---|---|---|---|
| Date not recorded | Tasks 002–004 connection/migration/ownership/readiness/CI/seed checks | Neon foundation, six initial tables, development seed | Passed | `docs/project-state.md` | Earlier working snapshot; commit not recorded | Supports VERIFIED foundation only; not current aggregate tree |
| 2026-08-08 | `npm run verify:web` | First receptionist frontend slice | Passed: 5 files/16 tests and production build | Owner, recorded in current session | Working-tree slice before later FAQ/telephony aggregation; commit unknown | Build routes recorded as `/`, `/receptionist-settings`, `/voice-test`; current tree also has `/approved-faqs` |
| 2026-08-08 | `ruff format --check .` | First receptionist Python/repository slice | Passed | Owner/current session | Same unknown working snapshot | Later backend files were added |
| 2026-08-08 | `ruff check .` | First receptionist Python/repository slice | Passed | Owner/current session | Same unknown working snapshot | Later backend files were added |
| 2026-08-08 | `mypy apps/backend/src tests` | First receptionist backend/tests | Passed for 37 source files | Owner/current session | Same unknown working snapshot | Current source count differs |
| 2026-08-08 | `pytest tests --ignore=tests/database` | First receptionist non-database suite | Passed: 13 tests | Owner/current session | Same unknown working snapshot | Later unit tests were added |
| 2026-08-08 | `APP_ENVIRONMENT=test pytest` | First receptionist complete Python suite | Passed: 44 tests | Owner/current session | Same unknown working snapshot | Disposable remote DB reportedly restored to then-head; later migrations/tests exist |
| 2026-08-08 | `insurance-operations-worker --check` | Worker/readiness | Passed with database ready/network enabled | Owner/current session | Same unknown working snapshot | No durable-job behavior was tested because none exists |
| 2026-08-08 | `alembic check` | First receptionist model/migration drift | Passed, no new upgrade operations | Owner/current session | Head then included `0004`; exact snapshot unknown | Does not cover `0005`–`0007` |
| 2026-08-08 | Live HTTP/browser smoke | Receptionist settings API/home/settings/Voice routes | Passed: HTTP 200 and configured profile rendered | Owner/current session | Same unknown working snapshot | Does not cover FAQ page, leads, or telephony |
| 2026-08-08 | Documented migration/static/focused DB/API/Alembic drift sequence | Approved FAQ slice (`0005`) | Owner reported clean results | Owner/project-state/current-session | Working-tree slice; exact commands/order/commit not preserved | An interrupted FAQ DB run is also recorded; see conflict below |
| 2026-08-08 | Commands in `docs/lead-handoff-api.md` | `0006`, migrations/ownership/conversation lead/handoff, static analysis, full suite/drift | Owner reported clean results | Owner/current session | Working-tree `0006` slice; commit unknown | Supports VERIFIED `0006` slice, not later `0007` aggregate |
| 2026-08-08 | FAQ-focused database run/fixture teardown | Disposable test database downgrade | Interrupted after downgrades through `0003`, during that revision's downgrade | Current-session note | Exact command/snapshot unknown | Test DB state must be inspected/restored before another database suite |

## Static audit performed for this continuation pack

These are read-only repository inspections, not verification-suite results.

| Date | Command/check | Scope | Result | Reported by | Snapshot | Notes |
|---|---|---|---|---|---|---|
| 2026-08-09 | `git branch --show-current`, `git rev-parse HEAD`, `git log --oneline` | Git identity | Captured `main` and `7f2f505f3b3d8b882e29904b624d83fa04dcc8e6` | This static audit | Dirty working tree at audit time | `origin/main` observed at same commit |
| 2026-08-09 | `git status --short`, `git diff --name-status`, `git diff --stat` | Complete tracked/untracked/deleted inventory | Captured substantial uncommitted/untracked work | This static audit | Dirty working tree before this pack | Tracked stat: 32 files, +2,199/-281; untracked code not included in stat |
| 2026-08-09 | `rg --files`, targeted `rg`, `sed`, `git diff`, `git show`, static model/migration/route/test inspection | Architecture, runtime, database, API, frontend, tests, docs/history | Continuation claims linked to repository paths/symbols; conflicts recorded | This static audit | Same dirty working tree | No code execution or database/provider inspection |
| 2026-08-09 | Static revision-chain inspection | Alembic files `0001`–`0007` | Repository head file is `0007`; actual database head unknown | This static audit | Same dirty working tree | File existence is not migration application |
| 2026-08-09 | Test source inspection | Current Python/frontend test files | Intended coverage mapped; execution not inferred | This static audit | Same dirty working tree | Telephony automated coverage is narrower than manual checklist |

## Verification conflict

CONFLICT:
- source A: repository notes say the approved FAQ slice received clean migration/static/focused/drift results.
- source B: the current session also records an interrupted FAQ database fixture downgrade and requires test-database restoration.
- repository evidence: there is no exact chronological command log or database revision capture resolving the order.
- impact: current disposable database state and current aggregate verification remain unknown.
- recommended resolution: inspect the disposable target, restore to repository head, and run the current sequence below when explicitly authorized.
- owner decision required: no

## Current working-tree verification required

All items below are **UNVERIFIED (not run in this task)**. Confirm `.env` contains an isolated disposable `TEST_DATABASE_URL` before any Alembic/pytest database operation. Do not paste connection values into chat or notes.

### 1. Inspect and restore the disposable test database

```bash
set -a; source .env; set +a
APP_ENVIRONMENT=test .venv/bin/alembic current
APP_ENVIRONMENT=test .venv/bin/alembic upgrade head
APP_ENVIRONMENT=test .venv/bin/alembic current
APP_ENVIRONMENT=test .venv/bin/alembic check
```

Expected: the explicitly disposable test database reaches `20260808_0007 (head)` and model drift reports no new upgrade operations. Result: UNVERIFIED.

### 2. Static/backend checks

```bash
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy apps/backend/src tests
```

Expected: all commands exit zero. Result: UNVERIFIED.

### 3. Focused `0007` checks

```bash
APP_ENVIRONMENT=test .venv/bin/pytest \
  tests/test_telephony_policy.py \
  tests/database/test_migrations.py \
  tests/database/test_table_ownership.py \
  tests/database/test_telephony_api.py
```

Expected: focused tests pass and fixture restores the disposable database. Result: UNVERIFIED.

### 4. Complete backend and migration drift

```bash
APP_ENVIRONMENT=test .venv/bin/pytest
APP_ENVIRONMENT=test .venv/bin/alembic upgrade head
APP_ENVIRONMENT=test .venv/bin/alembic check
insurance-operations-worker --check
```

Expected: complete suite/worker check pass, DB ends at head, no model drift. Network/database access may be required for worker readiness. Result: UNVERIFIED.

### 5. Complete frontend checks

```bash
npm run verify:web
```

Expected: format, lint, typecheck, all current frontend tests, and production build pass; build includes `/`, `/approved-faqs`, `/receptionist-settings`, and `/voice-test`. Result: UNVERIFIED.

### 6. Manual current-snapshot checks

Use synthetic data only:

1. Complete all ten manual checks in `docs/inbound-call-backend.md` against development simulation APIs.
2. Run receptionist settings create/read/update/stale-version checks and FAQ CRUD/preview/live active-session lookup with safe fallback.
3. Run browser Voice consent denial, mic denial, provider failure/disconnect, 3-minute limit, FAQ matched/fallback, review/edit, confirmation replay, and lead creation checks.
4. Inspect the disposable database/logs for no raw audio, provider credentials, hidden prompt, or draft transcript.
5. Verify provider dashboard privacy/authentication/region/model/STT/TTS/voice/fallback/billing controls before enabling Voice flags.
6. Do not configure real telephony webhooks/numbers/callers; signed ingress does not exist.

Expected: observed behavior matches current contracts with no sensitive persistence/logging. Result: UNVERIFIED.

## Evidence recording template for the next owner run

For each executed command/check, append: exact date/time, exact command without secrets, scope, pass/fail/interrupted result, who ran/reported it, `git rev-parse HEAD`, full `git status --short` or a named diff snapshot, database revision where relevant, and concise failure notes. Never replace an older ledger row; distinguish the new snapshot.
