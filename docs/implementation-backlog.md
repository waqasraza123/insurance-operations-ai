# Implementation Backlog

This order favors the fastest safe path to a reviewable product while preserving the approved boundaries in Documents 4, 6, and 7.

1. **Verified foundation** — Run the Task 004 migration, constraint, connection, readiness, lint, and type checks against a disposable PostgreSQL database. Resolve failures before extending persistence.
2. **Authentication and customer** — Implement FastAPI-owned identity, membership authorization, protected shell, and the idempotent customer workflow from Document 7 Milestones 4–5.
3. **Private PDF upload** — Add private Storage, signed upload/download authorization, file metadata, and one durable Processing transition from Milestone 6. Keep file bytes outside PostgreSQL.
4. **Durable worker** — Add the PostgreSQL job, lease, heartbeat, reclaim, and stage contracts from Milestone 7 before any live provider work.
5. **Provider-neutral candidate** — Implement the immutable candidate, evidence, validation, warning, fixture, and Stored Result contracts from Milestone 8 without selecting a provider.
6. **Review and approval** — Build granular human review and immutable approval against the provider-neutral fixture path. Preserve candidate/review/approved separation, optimistic concurrency, audit, and Current-policy uniqueness.
7. **Document AI evaluation and integration** — Run the controlled benchmark in Milestone 9, record the Milestone 10 owner decision, then integrate only the winning pipeline through the existing candidate contract as bounded Milestones 11–12 work.
8. **Narrow Voice AI extension** — Start only after a separate owner-approved product, architecture, data, privacy, evaluation, and operational specification. Voice AI is outside Release 1.

Each item must be split into one reviewable vertical slice with its migration, focused tests, security boundary, rollback note, and owner verification. Do not combine provider selection with product workflow implementation.
