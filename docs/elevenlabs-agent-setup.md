# ElevenLabs Agent Setup

Configure one private development agent in the ElevenLabs dashboard. Do not place the API key or agent ID in this document. Keep both Voice AI feature flags disabled until every privacy and billing item below is complete.

## Agent Contract

Explicitly select the LLM, STT, TTS, and voice. Do not enable automatic fallback or silently substitute an unavailable selection; stop and require a new owner selection instead. Enable authentication so the browser must use the backend-minted WebRTC token.

Suggested first message:

> Hello. I’m an AI intake assistant for a synthetic insurance demo. This conversation is recorded during the session and may be shared with ElevenLabs and third-party AI/LLM providers for processing. Please use fictional information only. I can collect fictional contact details and insurance needs, but I cannot quote, advise, bind, or verify coverage. What name should I use?

Suggested system prompt:

```text
You are a concise insurance intake assistant in a development-only synthetic-data demo.
Collect the customer's full name, at least one contact method (email or phone), and a short intake intent.
Ask one clear question at a time. Repeat uncertain spelling or numbers and ask the customer to correct them.
Never provide quotes, insurance advice, recommendations, coverage verification, binding, eligibility, underwriting, claims decisions, or autonomous decisions.
If asked for a prohibited action, explain that a licensed human must help and return to intake.
For every agency-specific factual question, call lookup_approved_faq with the customer's complete question. Never answer an agency-specific question from model knowledge.
If lookup_approved_faq returns matched=true, speak approved_answer exactly without adding facts. Do not speak source identifiers or versions.
If lookup_approved_faq returns matched=false or the tool fails, speak fallback_message and offer to capture details for human follow-up. Never invent an answer or infer one from a partial match.
Never claim data is saved. When the minimum details are collected, call submit_intake_draft once, explain that the browser will show an editable review, and ask the user to finish the conversation.
Use synthetic data only. Do not request sensitive payment, government identifier, health, or credential information.
If the user provides or appears to provide real or sensitive information, do not repeat it and do not call submit_intake_draft. Tell the user to end the session and restart with fictional data.
```

## Client Tools

Create a client tool named `submit_intake_draft` with optional string parameters `full_name`, `email`, `phone`, and `intake_intent`. Mark it as blocking/wait-for-response. Its purpose is to prefill browser review fields only; it does not persist data.

Create a second blocking client tool named `lookup_approved_faq` with one required string parameter named `query`. The browser sends the query and active conversation-session ID to the provider-neutral backend lookup. The tool returns JSON containing `matched`, `approved_answer`, `fallback_message`, and a source reference. Only a matched result may be presented as an agency answer; source IDs and versions are for auditability and must not be spoken.

## Privacy Checklist

- Disable provider [audio saving](https://elevenlabs.io/docs/eleven-agents/customization/privacy/audio-saving).
- Set conversation/audio/transcript [retention](https://elevenlabs.io/docs/eleven-agents/customization/privacy/retention) to the shortest duration the account supports (currently zero days for scheduled deletion).
- Enable Zero Retention Mode (ZRM) when the account offers it. Record when it is unavailable; that does not block this synthetic-only demo, but it blocks every real-data and production mode.
- In **Terms and privacy → Data use**, disable **Improve the models for everyone** so new submitted data is opted out of model-improvement and training use.
- Confirm the workspace region and model subprocessors are acceptable to the owner.
- Confirm the agent is private and requires authentication.
- Set the provider-side maximum conversation duration to 180 seconds.
- Confirm the LLM, STT, TTS, and voice are explicitly selected and set **Backup LLM configuration** to **Disabled**.
- Configure the account's plan-available hard billing guard, such as finite prepaid credits, a finite overage threshold, or a billing-group credit quota; never leave overage unlimited.
- Do not configure exports, webhooks, conversation analysis, success evaluation, data collection, analytics destinations, recordings, or unused integrations.
- Set `ELEVENLABS_PRIVACY_CONFIRMED=true` only after verifying these items.

Dashboard labels can change; verify effective behavior, not just toggle names. Only after both the privacy and billing checklist are complete should the server and public feature flags be enabled in development. These settings and the in-app disclosure define a synthetic portfolio demo only; they are not provider guarantees or claims of production, HIPAA, privacy, legal, or insurance compliance.

The checklist is based on ElevenLabs' current documentation for [disclosure](https://elevenlabs.io/docs/eleven-agents/legal/disclosure-requirement), [authenticated WebRTC access](https://elevenlabs.io/docs/api-reference/conversations/get-webrtc-token), [per-agent ZRM](https://elevenlabs.io/docs/eleven-agents/customization/privacy/zrm), [data-use opt-out](https://elevenlabs.io/docs/help-center/legal/is-my-data-used-to-improve-eleven-labs-ai-models), [LLM backup controls](https://elevenlabs.io/docs/eleven-agents/customization/llm), and [billing](https://elevenlabs.io/docs/overview/administration/billing). Re-check these references because provider controls and availability can change.
