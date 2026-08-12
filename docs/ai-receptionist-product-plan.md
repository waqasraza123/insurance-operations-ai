# AI Receptionist Product Plan

## Product Direction

Build a multi-tenant AI front desk for small independent U.S. insurance agencies. The product handles first contact through browser voice and, later, telephone calls. It answers only agency-approved FAQs, collects qualified lead information, and creates a clear human follow-up request.

The product does not quote, advise, bind, verify coverage, recommend limits, underwrite, decide claims, or replace licensed agency staff. Unsupported or regulated requests must be handed to a human.

## Product Promise

An agency can configure a branded AI receptionist that:

1. Discloses that it is an AI and obtains required consent.
2. Answers approved questions about the agency and its services.
3. Collects contact details, insurance interest, intent, and urgency.
4. Recognizes requests that require licensed or human assistance.
5. Creates an actionable lead with a transcript and concise summary.
6. Routes the lead for follow-up without claiming that insurance action was completed.

## Current Baseline

The repository already provides a Next.js frontend, FastAPI backend, Python worker, Neon PostgreSQL foundation, deterministic development actor, provider-neutral conversation records, an ElevenLabs browser WebRTC adapter, consent gates, session quotas, editable transcript review, immutable confirmation, customer creation, and audit events.

The current implementation remains a synthetic-data development foundation. Agency receptionist settings, approved FAQ services, lead lifecycle APIs, and human-handoff APIs are owner-verified. Provider-neutral inbound-call persistence and orchestration are implemented but await owner verification. Production authentication, a concrete telephone adapter, billing, external integrations, final operations UI, and production deployment controls are not implemented.

## Execution Principles

- Deliver one complete customer-to-agency workflow before adding channels or broad features.
- Keep business models and APIs provider-neutral; isolate ElevenLabs and future telephony vendors in adapters.
- Keep authorization, tenancy, validation, quotas, audit, and transaction boundaries authoritative in the backend.
- Use only agency-approved knowledge for answers and attach the source FAQ to every answered question.
- Escalate uncertain, unsupported, regulated, or sensitive requests instead of improvising.
- Do not retain raw audio by default. Store confirmed transcript and business records only under explicit retention rules.
- Use synthetic data until production identity, privacy, security, deletion, and operational controls are verified.
- Treat each milestone acceptance gate as mandatory before starting the next milestone.

## Milestone 1 — Showcase-Ready Browser Receptionist

### Outcome

A prospect completes a natural browser voice conversation, receives an approved agency answer, submits an insurance-interest intake, and appears as an actionable lead in an agency dashboard.

### Workstreams

1. **Product presentation**
   - Replace foundation/demo language with AI receptionist positioning.
   - Add a credible agency-branded demo experience and clear synthetic-data disclosure.
   - Show supported tasks, human escalation boundaries, and conversation status clearly.

2. **Agency configuration**
   - Add backend-owned agency receptionist settings: display name, greeting, office hours, contact details, supported insurance categories, and escalation message.
   - Provide a development configuration screen using the existing deterministic agency until production authentication is implemented.
   - Audit configuration changes and validate all public content.

3. **Approved FAQ knowledge**
   - Add agency-owned FAQ records with question, approved answer, status, and version metadata.
   - Provide create, edit, activate, deactivate, and list operations.
   - Retrieve only active agency FAQs and return a safe fallback when no approved answer matches.
   - Record which FAQ supported an answer without storing provider credentials or hidden prompts.

4. **Receptionist conversation workflow**
   - Extend provider-neutral conversation tools for FAQ lookup, intake draft submission, and human follow-up requests.
   - Collect name, at least one contact method, insurance interest, intent, and urgency.
   - Detect prohibited requests and route them to human follow-up.
   - Keep explicit review and confirmation before persisting transcript-derived customer data.

5. **Lead inbox**
   - Present confirmed intakes as agency-owned leads with status, summary, contact details, intent, urgency, transcript, timestamps, and audit history.
   - Support safe status transitions such as new, contacted, qualified, closed, and archived.
   - Prevent cross-agency access and conflicting updates.

6. **Human handoff**
   - Create a callback request with reason, preferred contact method, and availability.
   - Surface the request in the lead inbox.
   - Add provider-neutral notification boundaries; begin with an in-app workflow before external email, SMS, or CRM delivery.

7. **Portfolio delivery**
   - Deploy a synthetic demonstration environment.
   - Add seeded agency configuration and approved FAQs.
   - Produce a short walkthrough covering conversation, safe refusal, confirmation, lead inbox, and handoff.
   - Document architecture, verification results, implemented capabilities, and limitations.

### Acceptance Gate

- The browser assistant identifies itself and accepts only synthetic data.
- It answers at least one agency-approved FAQ and safely declines an unsupported insurance request.
- It collects the required intake fields and creates no customer or lead before explicit confirmation.
- Confirmation creates one immutable intake and one visible lead without duplication on retry.
- A human follow-up request appears in the agency dashboard.
- Tenant ownership, validation, audit, quota, timeout, and failure paths have focused automated tests.
- The deployed demo and portfolio walkthrough make no unsupported production or compliance claims.

## Milestone 2 — Inbound Phone Receptionist

### Outcome

A prospect calls an agency number, speaks with the same guarded receptionist workflow, and can request transfer or callback.

### Workstreams

- Add a provider-neutral telephony port and one inbound-call adapter.
- Provision and map agency phone numbers without leaking provider identifiers into business APIs.
- Support disclosure, interruption, silence, timeout, disconnect, DTMF, transfer, and callback fallback.
- Apply agency concurrency, duration, daily usage, and billing controls before accepting a call.
- Persist provider-neutral call metadata, confirmed transcript, summary, lead, handoff, and audit events.
- Keep raw-audio retention disabled by default and make any future retention an explicit policy decision.
- Add failure simulation and conversation evaluations for common call paths.

### Acceptance Gate

- An inbound call completes the same approved FAQ, intake, and handoff workflow as browser voice.
- Transfer and callback fallback behave predictably when staff are unavailable.
- Provider failure cannot duplicate leads, lose confirmed state, or bypass quotas.
- Usage and cost are visible per agency and bounded by hard controls.

## Milestone 3 — Multi-Tenant SaaS

### Outcome

Multiple agencies can securely onboard, configure, operate, and pay for isolated AI receptionists.

### Workstreams

- Implement production authentication and invitation-based agency onboarding.
- Add owner, manager, and staff roles with backend-enforced permissions.
- Replace the deterministic development actor with authenticated identity resolution.
- Provide agency settings, FAQ, channel, lead, handoff, usage, and team administration.
- Add subscription plans, entitlements, usage metering, quotas, and billing lifecycle handling.
- Add webhook and CRM integration boundaries with signed delivery, retries, and audit history.
- Provide data export, deletion, retention, and account closure workflows.
- Add internal support tooling without allowing unrestricted tenant data access.

### Acceptance Gate

- Tenant-isolation tests cover every agency-owned route and background operation.
- Subscription state and entitlements are backend-authoritative and idempotent.
- Agency owners can onboard, configure, invite staff, inspect usage, and close their account.
- Data retention, export, and deletion behavior is documented and verified.

## Milestone 4 — Production Hardening

### Outcome

The service is observable, supportable, secure, and measurable under controlled real-customer pilots.

### Workstreams

- Add structured operational telemetry, health indicators, alerts, and provider diagnostics without sensitive content.
- Add prompt and configuration versioning, release controls, rollback, and audit history.
- Build repeatable conversation evaluations for FAQ accuracy, intake completion, prohibited requests, prompt injection, interruptions, handoff, and provider failure.
- Complete threat modeling, dependency review, tenant-isolation review, backup/restore testing, and incident procedures.
- Verify accessibility, browser/device compatibility, latency, load, and recovery objectives.
- Establish privacy notices, consent evidence, retention schedules, deletion procedures, and vendor control reviews.

### Acceptance Gate

- Critical user journeys and safety boundaries have automated regression and conversation evaluations.
- Operational owners can detect, diagnose, contain, and recover from expected failures.
- A controlled pilot can be enabled per agency with explicit limits and rollback.

## Immediate Execution Plan

Backend and API completion is the active priority. Freeze new frontend work until the browser and telephone backend workflows, contracts, persistence, safety rules, and provider adapters are complete. Implement in the following order:

1. **Completed:** Rewrite the public product presentation and establish a reusable agency-branded demo configuration contract.
2. **Completed and owner-verified:** Agency receptionist settings and approved FAQ persistence, APIs, deterministic retrieval, source references, and conversation-tool lookup.
3. **Completed and owner-verified:** Backend lead records, lifecycle APIs, immutable intake linkage, transcript access, audit history, optimistic concurrency, and human-handoff request APIs.
4. **Implemented; owner verification pending:** Agency transfer policy, staff availability rules, callback fallback orchestration, and provider-neutral notification ports.
5. **Partially implemented; owner verification pending:** Provider-neutral phone-number mapping, inbound-call persistence, idempotent call events, call state, concurrency/daily quotas, transfer decisions, disconnect handling, and failure recovery. Signed provider ingress, DTMF, duration enforcement, and usage metering remain.
6. Add one telephony adapter and prove that telephone calls reuse the same FAQ, intake, lead, and handoff services as browser conversations.
7. Complete backend safety, ownership, idempotency, failure-path, contract, and conversation-evaluation coverage.
8. Build the final agency operations UI against the stable APIs, then perform accessibility, browser QA, deployment, and portfolio delivery.

The first implementation slice is product presentation plus the agency receptionist settings contract. It must define the user-facing promise and the backend-owned configuration that every later FAQ, conversation, dashboard, and telephony feature consumes.

## Portfolio Positioning

Use this description only after Milestone 1 passes its acceptance gate:

> A multi-tenant-ready AI receptionist foundation for insurance agencies that handles approved FAQs, structured lead intake, explicit confirmation, human follow-up, and auditable conversation workflows through real-time browser voice.

Add “inbound phone receptionist” only after Milestone 2 passes its acceptance gate. Add “production SaaS” only after Milestone 3 passes its acceptance gate.
