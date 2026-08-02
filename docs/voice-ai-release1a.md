# Voice AI Release 1A

## Purpose

Release 1A is a development-only browser conversation for synthetic insurance intake. ElevenLabs supplies two-way voice over WebRTC behind replaceable backend and frontend adapters. Business APIs and tables remain provider-neutral.

## User Flow

1. Show the AI limits, provider processing disclosure, synthetic-data rule, and microphone purpose.
2. Require explicit disclosure acceptance, microphone consent, and synthetic-data acknowledgement.
3. Ask the backend for a short-lived WebRTC credential; the API key never reaches the browser.
4. Let the customer and AI speak for at most 180 seconds while showing live transcript text.
5. End in editable review. Nothing is saved automatically.
6. Require a name, email or phone, intake intent, transcript turns from both parties, and explicit confirmation.
7. Atomically create the customer, immutable conversation intake, audit events, and confirmed session. Retrying the same confirmation is idempotent.

There is no telephony, phone-number provisioning, inbound/outbound calling, or call recording.

## Safety and Authority

- The assistant may collect contact details and insurance needs only.
- It must not quote, advise, recommend limits, bind coverage, verify coverage, determine eligibility, underwrite, handle claims, or make autonomous decisions.
- Spoken and transcribed values are untrusted until backend validation and explicit review.
- One active session per agency and ten authorized sessions per UTC day are enforced by the backend.
- The feature is hidden outside development and resolves only the deterministic active development actor and development agency.

## Provider Boundaries

Business code uses `ConversationProvider`, connection grants, generic session metadata, and generic conversation APIs. The ElevenLabs backend adapter alone knows its token endpoint, API-key header, agent ID, response fields, and provider metadata mapping. The ElevenLabs frontend adapter alone imports its React SDK and maps SDK state/messages/tools into generic UI contracts. A later provider can replace either adapter without renaming business tables or APIs.

Agent voice and language-model selection remain owner-controlled dashboard decisions. There is no automatic fallback or second provider.

## Privacy and Retention

- Raw audio is processed live and is never written to PostgreSQL, object storage, application logs, analytics, or audit details.
- Partial and draft transcript text remains browser memory only.
- Transcript retention begins only after explicit confirmation.
- Audit details contain identifiers and bounded outcomes, not transcript or contact content.
- Enabling the backend requires an owner attestation that provider audio saving is off and provider retention is zero days. Verify the dashboard again before every portfolio demonstration.

## Failure, Interruption, Retry, and Cost

- Permission denial, missing microphone, provider failure, unexpected disconnect, timeout, and backend failure produce a clear stopped state; none implies confirmation.
- Unexpected disconnects are marked interrupted. A retry creates a new session through explicit user action.
- Confirmation uses one stable idempotency key so a safe retry cannot duplicate the customer or intake.
- Provider authorization has a bounded timeout and sanitized errors. Credentials are short-lived and never persisted.
- Sessions stop at 180 seconds, concurrency is one, and daily authorization is ten. There are no unbounded retries, fallback providers, or background continuations.

## Explicitly Deferred

Production authentication and actors; real customer data; telephony; raw-audio retention; provider fallback; full customer management; uploads; Storage; queues; Document AI; OCR; and autonomous insurance actions.

