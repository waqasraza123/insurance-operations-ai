# Voice AI Release 1A

## Purpose

Release 1A is a browser-based voice intake path for an authenticated agency user. It gathers basic customer/contact information and the intake intent, then presents an editable transcript for explicit user confirmation. Voice AI moves ahead of Document AI by owner decision; all shared architecture, security, persistence, API, audit, and Codex rules in the seven approved documents remain binding.

## Included Flow

1. The browser explains microphone use and records explicit consent before capture begins.
2. The user provides a name, available email or phone details, and a short description of the intake intent.
3. A provider-neutral backend boundary submits bounded audio for transcription when a provider is later approved.
4. The user can edit the resulting transcript and must explicitly confirm it.
5. Only the confirmed transcript may be retained and used by later approved workflows.

The first slice is browser-only. It has no provisioned telephone numbers, inbound or outbound calls, call routing, call-recording system, or other telephony integration.

## Safety and Authority

- The microphone cannot start without explicit, current-session consent and a visible recording state.
- Voice intake must not provide insurance quotes or advice, bind coverage, verify coverage, recommend limits, or make autonomous eligibility, underwriting, claim, or service decisions.
- Spoken and transcribed values remain untrusted user input. Backend validation, agency ownership, authorization, idempotency, and audit rules remain authoritative.
- A transcript is a user-confirmed intake record, not verified policy or carrier data.
- Confirmation must identify the actor and time and must not be inferred from silence, navigation, or transcription completion.

## Provider Boundary

Application code will depend on a narrow transcription capability that accepts a bounded audio input and returns transcript text plus provider-neutral diagnostics. Provider credentials, request construction, response mapping, timeouts, and usage metadata stay inside the adapter. No browser may call a provider directly. No transcription provider, model, SDK, or routing strategy is approved by this specification; selection requires a separate owner-approved evaluation.

## Data and Privacy

- Raw audio is transient processing input and is not permanently retained in PostgreSQL, object storage, logs, analytics, or audit details in the first slice.
- Draft and partial transcripts are not durable. Transcript retention begins only after explicit confirmation.
- Logs and audit events contain identifiers, outcomes, timings, and bounded error categories, never access tokens, raw audio, transcript content, or unnecessary contact data.
- Provider submissions must be limited to the minimum audio required for the active intake and governed by an approved retention and training policy before integration.

## Failure, Retry, and Cost Boundaries

- Permission denial, missing devices, interruption, timeout, invalid audio, provider unavailability, and transcription failure must leave the user in control with a clear retry or typed-input path.
- An interrupted capture is not silently resumed or submitted. Retrying requires an explicit user action and must not duplicate confirmed intake records.
- Provider failures must use bounded timeouts and retries; failure detail exposed to users and logs must be sanitized.
- Capture duration, payload size, retry count, request concurrency, and per-session/provider spend require configurable owner-approved limits before provider integration. No unlimited capture, retry, or provider fallback is allowed.
- A provider outage must not weaken consent, confirmation, retention, authorization, or safety rules.

## Explicitly Deferred

Transcription implementation and provider choice; microphone UI; raw-audio storage; telephony; speaker identification; autonomous conversations; insurance answers or decisions; Document AI; uploads; OCR; queues; and complete customer-management UI.
