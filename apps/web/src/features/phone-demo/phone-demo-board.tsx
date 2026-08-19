"use client";

import { useEffect, useState } from "react";

import { Brand } from "@/components/brand";

import { getPhoneDemoStatus } from "./api";
import type { PhoneDemoState, PhoneDemoStatus } from "./contracts";

const POLL_INTERVAL_MILLISECONDS = 5_000;
const TERMINAL_STATES: readonly PhoneDemoState[] = [
  "LEAD_CREATED",
  "TRANSFERRED",
  "CALLBACK_REQUESTED",
  "FAILED",
];

const INITIAL_STATUS: PhoneDemoStatus = {
  state: "READY",
  receivedAt: null,
  answeredAt: null,
  endedAt: null,
  consentCompleted: false,
  leadCreated: false,
  urgency: null,
  handoffKind: null,
  handoffStatus: null,
};

const STATE_COPY: Record<PhoneDemoState, string> = {
  READY: "Ready for the next fictional call",
  RINGING: "A demo call is arriving",
  IN_PROGRESS: "The AI receptionist is handling the call",
  LEAD_CREATED: "A confirmed lead was created",
  TRANSFERRED: "The caller reached the human transfer destination",
  CALLBACK_REQUESTED: "A human callback was requested",
  FAILED: "The call ended without a confirmed demo lead",
};

type PhoneDemoBoardProperties = Readonly<{
  apiBaseUrl: string;
  phoneNumber: string;
}>;

export function PhoneDemoBoard({
  apiBaseUrl,
  phoneNumber,
}: PhoneDemoBoardProperties) {
  const [status, setStatus] = useState<PhoneDemoStatus>(INITIAL_STATUS);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function refresh() {
      try {
        const nextStatus = await getPhoneDemoStatus(apiBaseUrl);
        if (!active) return;
        setStatus(nextStatus);
        setError(null);
        if (!TERMINAL_STATES.includes(nextStatus.state)) {
          timer = setTimeout(refresh, POLL_INTERVAL_MILLISECONDS);
        }
      } catch {
        if (!active) return;
        setError(
          "Live status is temporarily unavailable. The phone line can still work.",
        );
        timer = setTimeout(refresh, POLL_INTERVAL_MILLISECONDS);
      }
    }

    void refresh();
    return () => {
      active = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [apiBaseUrl]);

  return (
    <main className="phone-demo-shell">
      <nav className="top-nav" aria-label="Primary navigation">
        <Brand />
        <span className="demo-mode-badge">Fictional demo</span>
      </nav>

      <section className="phone-demo-hero" aria-labelledby="phone-demo-title">
        <div>
          <p className="eyebrow">Harborline Insurance showcase</p>
          <h1 id="phone-demo-title">Call the AI front desk.</h1>
          <p className="summary">
            Hear disclosure, approved FAQ answers, structured intake, verbal
            confirmation, and human handoff in one guarded phone workflow.
          </p>
          <a className="phone-number-link" href={`tel:${phoneNumber}`}>
            {phoneNumber}
          </a>
          <p className="demo-notice">
            Use fictional information only. This agent cannot quote, advise,
            bind coverage, or handle real insurance business.
          </p>
        </div>

        <aside className="demo-status-card" aria-live="polite">
          <div className="demo-status-heading">
            <span
              className={`demo-state-dot demo-state-${status.state.toLowerCase()}`}
            />
            Live call result
          </div>
          <h2>{STATE_COPY[status.state]}</h2>
          <dl className="demo-result-list">
            <Result
              label="Consent"
              value={status.consentCompleted ? "Accepted" : "Pending"}
            />
            <Result
              label="Lead"
              value={status.leadCreated ? "Created" : "Not created"}
            />
            <Result label="Urgency" value={status.urgency ?? "—"} />
            <Result
              label="Handoff"
              value={status.handoffKind?.replace("_", " ") ?? "—"}
            />
          </dl>
          {error && <p className="demo-status-error">{error}</p>}
        </aside>
      </section>

      <section className="demo-script" aria-labelledby="demo-script-title">
        <p className="eyebrow">Suggested call script</p>
        <h2 id="demo-script-title">A two-minute walkthrough</h2>
        <ol>
          <li>Agree to the AI and fictional-data disclosure.</li>
          <li>Ask: “What are your office hours?”</li>
          <li>Use the fictional name “Taylor Morgan.”</li>
          <li>Ask about a fictional auto-insurance callback.</li>
          <li>Confirm the details after the agent reads them back.</li>
          <li>Request a callback or live transfer.</li>
        </ol>
      </section>
    </main>
  );
}

function Result({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
