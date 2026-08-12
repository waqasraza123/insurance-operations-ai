# ChatGPT Working Instructions

## Start every repository task here

1. Read `AGENTS.md`.
2. Read `docs/project-state.md` first as durable shared memory.
3. Read `docs/_local/current-session.md` when it exists as current local working memory.
4. Read `docs/chatgpt-continuation/00-START-HERE.md`.
5. Inspect the current branch, HEAD, complete working-tree status, modified/deleted/untracked files, and relevant diffs.
6. Read the continuation files for the affected domain, then inspect every referenced implementation, migration, model/schema, test, and caller before proposing a patch.

The repository is primary evidence. This pack is an index. Narrative documentation, test names, file existence, an older green commit, and prior chat statements never outrank current code.

## Evidence and status discipline

- Do not assume the repository is green.
- Do not assume previous changes landed, were committed, or remain unchanged.
- Do not mark a feature VERIFIED because files/tests exist. Require explicit passed evidence for the relevant snapshot.
- Use only these implementation status labels: VERIFIED, IMPLEMENTED—UNVERIFIED, PARTIAL, NOT IMPLEMENTED, DECISION REQUIRED.
- For PARTIAL, list exactly what exists and what does not.
- If documentation, code, migrations, tests, or callers conflict, do not silently choose. Report:

```text
CONFLICT:
- source A:
- source B:
- repository evidence:
- impact:
- recommended resolution:
- owner decision required: yes/no
```

- Request exact file contents when attached repository evidence is unavailable, truncated, stale, generated, or insufficient. Do not fill the gap from memory.
- Use Codex only for current code inspection when needed, not as the primary architect. The current owner decisions, repository evidence, and explicit acceptance contract govern architecture.

## Scope and execution

- Work one meaningful cohesive step at a time. Respect the current backend/frontend freeze and dependency order in `07-remaining-build-plan.md`.
- Do not guess unresolved product, architecture, provider, security, legal, operational, or business requirements. Check `08-decisions-and-unknowns.md`; stop at DECISION REQUIRED and ask the owner.
- Do not broaden a task into refactors, bug fixes, dependencies, migrations, provider/account changes, or deployment unless those actions are necessary, approved, and in scope.
- Preserve unrelated user changes in a dirty tree. Never overwrite or delete them to simplify a patch.
- Do not add application code during an audit/review request. Diagnose/report without implementing unless the owner asks for implementation.
- Follow `AGENTS.md`: do not run tests, builds, linters, type checks, migrations, seeds, readiness checks, smoke tests, live services, browser automation, background terminals, or verification commands unless the owner explicitly asks for that specific execution.
- After implementation, provide exact owner-run commands/manual checks and keep the change IMPLEMENTED—UNVERIFIED until results are reported.
- Never use real customer data or copy secrets, environment values, credentials, database URLs, personal data, hidden prompts, or sensitive document contents into chat, code, tests, commits, or notes.

## Code quality contract

- Production-grade code only, even for development routes.
- Follow the existing architecture, naming, package layout, validation/error format, and conventions.
- Use descriptive names, strong typing, small focused functions, and modular reusable services/adapters.
- Validate inputs and configuration and return clear, sanitized errors.
- Do not add unnecessary comments or comments that restate code.
- Do not introduce hardcoded hacks, inferred defaults, silent fallback, or provider leakage into core domains.
- Keep provider SDKs, payload parsing, request signing, credentials, provider commands, and provider-specific metadata inside the actual adapter boundary.
- The browser and providers are thin clients. Preserve backend authority for actors, tenancy, ownership, validation, lifecycle, quotas, idempotency, audit, and durable confirmation.
- Preserve transaction boundaries: authoritative mutation, audit, idempotency completion, and append-only domain event must commit together where the existing service contract requires it.
- Never perform an external provider/notification side effect inside a database transaction. Use the approved response/command/outbox design.
- Preserve immutable confirmed intakes and immutable normalized call events; never mutate history to simulate correction.
- Require agency scoping on every tenant-owned query, including background/provider paths; do not reveal cross-tenant existence.
- Keep credentials and signing secrets server-side and out of browser responses, metadata, audit, and logs.
- Preserve consent/confirmation, synthetic-only, no-raw-audio, approved-FAQ-only, and no-insurance-decision restrictions in `05-business-and-safety-invariants.md`.

## Implementation workflow

Before code:

1. State the single objective and exact acceptance criteria.
2. Identify current status and verification evidence.
3. Trace callers -> route -> schema -> service -> model/migration -> tests.
4. List ownership, transaction, idempotency, audit, quota, provider, privacy, and compatibility implications.
5. Surface conflicts and DECISION REQUIRED items. Ask rather than assume.

While coding:

1. Keep the patch focused and reversible.
2. Add/update schemas, service behavior, persistence/migration, callers, tests, and docs only when required by the cohesive slice.
3. For a migration, inspect the full chain, model metadata, downgrade behavior, ownership registry, triggers, constraints, and test fixture safety.
4. For a route, document actor/auth, ownership, validation, transaction, idempotency, state changes, errors, callers, and focused tests.
5. For a provider, test signature/error/mapping behavior using synthetic fixtures and official provider documentation; never infer undocumented payloads.

After coding:

1. Inspect the final diff and status; ensure no unrelated or generated/sensitive files were added.
2. Update `docs/project-state.md` only for verified architecture, decisions, milestones, risks, or commands. Do not write speculation or claim unrun verification.
3. Update `docs/_local/current-session.md` after every meaningful task and whenever the active handoff changes.
4. Provide exact targeted/full verification and manual QA for the owner. Include database safety warnings where applicable.
5. Keep commit messages under 140 characters. Do not commit/push unless asked.

## Required implementation response contract

For an implementation task, respond with these seven sections in this exact order:

1. **WHAT THIS STEP DOES**
2. **CODE**
3. **VERIFICATION COMMANDS**
4. **EXPECTED RESULT**
5. **COMMIT MESSAGE**
6. **GIT COMMANDS**
7. **NEXT BEST STEP**

A response is incomplete if those seven sections are required for an implementation task and any are missing.

Section expectations:

- **WHAT THIS STEP DOES**: objective, current status, scope, invariants, and exclusions.
- **CODE**: concise file-by-file summary and exact patch/code; state conflicts/owner decisions before code.
- **VERIFICATION COMMANDS**: exact commands the owner should run; never claim they ran unless evidence proves it. Warn before destructive disposable-database operations.
- **EXPECTED RESULT**: observable automated/manual outcomes and final database/runtime state.
- **COMMIT MESSAGE**: one proposed message under 140 characters.
- **GIT COMMANDS**: scoped add/status/diff/commit commands; no push unless requested; never stage unrelated dirty-tree files.
- **NEXT BEST STEP**: one dependency-ordered cohesive step, including any decision/verification gate.

## Current next-step guard

At the 2026-08-09 snapshot, do not start a concrete telephony adapter immediately. First restore/verify the disposable test database and current `0007` slice using `09-verification-ledger.md`. Then obtain the owner's telephony provider/signature/replay and phone consent/confirmation decisions. Only after those gates should the next implementation be the concrete signed adapter plus provider-to-neutral event ingress described in `07-remaining-build-plan.md`.
