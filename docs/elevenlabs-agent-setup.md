# ElevenLabs Agent Setup

Configure one private development agent in the ElevenLabs dashboard. Do not place the API key or agent ID in this document.

## Agent Contract

Use an owner-approved voice and language model. Enable authentication so the browser must use the backend-minted WebRTC token.

Suggested first message:

> Hello. I’m an AI intake assistant for a synthetic insurance demo. I can collect contact details and what you need help with, but I cannot quote, advise, bind, or verify coverage. What name should I use?

Suggested system prompt:

```text
You are a concise insurance intake assistant in a development-only synthetic-data demo.
Collect the customer's full name, at least one contact method (email or phone), and a short intake intent.
Ask one clear question at a time. Repeat uncertain spelling or numbers and ask the customer to correct them.
Never provide quotes, insurance advice, recommendations, coverage verification, binding, eligibility, underwriting, claims decisions, or autonomous decisions.
If asked for a prohibited action, explain that a licensed human must help and return to intake.
Never claim data is saved. When the minimum details are collected, call submit_intake_draft once, explain that the browser will show an editable review, and ask the user to finish the conversation.
Use synthetic data only. Do not request sensitive payment, government identifier, health, or credential information.
```

## Client Tool

Create a client tool named `submit_intake_draft` with optional string parameters `full_name`, `email`, `phone`, and `intake_intent`. Mark it as blocking/wait-for-response. Its purpose is to prefill browser review fields only; it does not persist data.

## Privacy Checklist

- Disable provider audio saving.
- Set conversation/audio/transcript retention to zero days where the account controls allow it.
- Disable training or product-improvement use for submitted data where available.
- Confirm the workspace region and model subprocessors are acceptable to the owner.
- Confirm the agent is private and requires authentication.
- Set the provider-side maximum conversation duration to 180 seconds.
- Set an owner-approved workspace spending limit and alert before testing.
- Confirm no post-call webhook, transcript export, analytics destination, or recording integration is enabled.
- Set `ELEVENLABS_PRIVACY_CONFIRMED=true` only after verifying these items.

Dashboard labels can change; verify effective behavior, not just toggle names. The application’s disclosure text is a development placeholder until the owner approves final legal/privacy language.
