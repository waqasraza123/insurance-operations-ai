"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  ApprovedFaqApiError,
  createApprovedFaq,
  listApprovedFaqs,
  previewApprovedFaqLookup,
  setApprovedFaqStatus,
  updateApprovedFaq,
} from "./api";
import type { ApprovedFaq, ApprovedFaqDraft } from "./contracts";

const EMPTY_DRAFT: ApprovedFaqDraft = { question: "", approvedAnswer: "" };

export function ApprovedFaqManager({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [faqs, setFaqs] = useState<ApprovedFaq[]>([]);
  const [draft, setDraft] = useState<ApprovedFaqDraft>(EMPTY_DRAFT);
  const [lookupQuery, setLookupQuery] = useState("");
  const [lookupMessage, setLookupMessage] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string>();

  useEffect(() => {
    let active = true;
    void listApprovedFaqs(apiBaseUrl)
      .then((result) => active && setFaqs(result))
      .catch((error: unknown) => active && setMessage(faqErrorMessage(error)));
    return () => {
      active = false;
    };
  }, [apiBaseUrl]);

  async function createFaq() {
    if (!draft.question.trim() || !draft.approvedAnswer.trim()) {
      setMessage("Enter both an approved question and answer.");
      return;
    }
    setBusy(true);
    setMessage(undefined);
    try {
      const created = await createApprovedFaq(apiBaseUrl, draft);
      setFaqs((current) => [...current, created]);
      setDraft(EMPTY_DRAFT);
      setMessage("FAQ saved as inactive. Review it, then activate it.");
    } catch (error) {
      setMessage(faqErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function previewLookup() {
    if (!lookupQuery.trim()) return;
    setBusy(true);
    setLookupMessage(undefined);
    try {
      const result = await previewApprovedFaqLookup(apiBaseUrl, lookupQuery);
      setLookupMessage(
        result.matched && result.source
          ? `${result.answer} — Source: ${result.source.question} (v${result.source.rowVersion})`
          : `No approved match. ${result.fallbackMessage}`,
      );
    } catch (error) {
      setLookupMessage(faqErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  function replaceFaq(updated: ApprovedFaq) {
    setFaqs((current) =>
      current.map((faq) => (faq.id === updated.id ? updated : faq)),
    );
  }

  return (
    <main className="settings-shell">
      <nav className="top-nav" aria-label="Primary navigation">
        <Link className="brand-link" href="/">
          Insurance Operations AI
        </Link>
        <div className="nav-links">
          <Link className="text-link" href="/receptionist-settings">
            Agency profile
          </Link>
          <Link className="text-link" href="/voice-test">
            Open receptionist
          </Link>
        </div>
      </nav>
      <header className="page-header">
        <p className="eyebrow">Approved knowledge</p>
        <h1>Control what the receptionist can answer</h1>
        <p className="summary">
          Only active FAQs are eligible for deterministic matching. Uncertain or
          unsupported questions use the configured human handoff message.
        </p>
      </header>

      <section className="settings-card">
        <p className="section-kicker">New FAQ</p>
        <h2>Add an approved answer</h2>
        <FaqFields draft={draft} onChange={setDraft} />
        <div className="settings-actions">
          <button
            className="primary-button"
            disabled={busy}
            onClick={() => void createFaq()}
            type="button"
          >
            Save inactive FAQ
          </button>
          <p className="settings-note">
            Activation is a separate audited action.
          </p>
        </div>
        {message && <p role="status">{message}</p>}
      </section>

      <section className="settings-card">
        <div className="section-heading-row">
          <div>
            <p className="section-kicker">Knowledge base</p>
            <h2>{faqs.length} approved FAQ records</h2>
          </div>
        </div>
        <div className="faq-list">
          {faqs.length === 0 ? (
            <p className="empty-state">No FAQs have been configured.</p>
          ) : (
            faqs.map((faq) => (
              <FaqEditor
                apiBaseUrl={apiBaseUrl}
                faq={faq}
                key={faq.id}
                onReplace={replaceFaq}
              />
            ))
          )}
        </div>
      </section>

      <section className="settings-card">
        <p className="section-kicker">Safe retrieval preview</p>
        <h2>Test a customer question</h2>
        <label>
          Customer question
          <input
            maxLength={500}
            onChange={(event) => setLookupQuery(event.target.value)}
            type="text"
            value={lookupQuery}
          />
        </label>
        <div className="settings-actions">
          <button
            className="secondary-button"
            disabled={busy || !lookupQuery.trim()}
            onClick={() => void previewLookup()}
            type="button"
          >
            Test approved lookup
          </button>
        </div>
        {lookupMessage && <p className="lookup-result">{lookupMessage}</p>}
      </section>
    </main>
  );
}

function FaqEditor({
  apiBaseUrl,
  faq,
  onReplace,
}: {
  apiBaseUrl: string;
  faq: ApprovedFaq;
  onReplace: (faq: ApprovedFaq) => void;
}) {
  const [draft, setDraft] = useState<ApprovedFaqDraft>({
    question: faq.question,
    approvedAnswer: faq.approvedAnswer,
  });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string>();

  async function save() {
    setBusy(true);
    setMessage(undefined);
    try {
      const updated = await updateApprovedFaq(apiBaseUrl, faq, draft);
      onReplace(updated);
      setMessage("Saved and audited.");
    } catch (error) {
      setMessage(faqErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function toggleStatus() {
    setBusy(true);
    setMessage(undefined);
    try {
      const updated = await setApprovedFaqStatus(
        apiBaseUrl,
        faq,
        faq.status === "ACTIVE" ? "INACTIVE" : "ACTIVE",
      );
      onReplace(updated);
      setMessage(
        `${updated.status === "ACTIVE" ? "Activated" : "Deactivated"} and audited.`,
      );
    } catch (error) {
      setMessage(faqErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="faq-editor">
      <div className="section-heading-row">
        <span className={`faq-status faq-status-${faq.status.toLowerCase()}`}>
          {faq.status}
        </span>
        <span className="version-badge">Version {faq.rowVersion}</span>
      </div>
      <FaqFields draft={draft} onChange={setDraft} />
      <div className="settings-actions">
        <button
          className="secondary-button"
          disabled={busy}
          onClick={() => void save()}
          type="button"
        >
          Save changes
        </button>
        <button
          className="secondary-button"
          disabled={busy}
          onClick={() => void toggleStatus()}
          type="button"
        >
          {faq.status === "ACTIVE" ? "Deactivate" : "Activate"}
        </button>
      </div>
      {message && <p role="status">{message}</p>}
    </article>
  );
}

function FaqFields({
  draft,
  onChange,
}: {
  draft: ApprovedFaqDraft;
  onChange: (draft: ApprovedFaqDraft) => void;
}) {
  return (
    <div className="faq-fields">
      <label>
        Approved customer question
        <input
          maxLength={300}
          onChange={(event) =>
            onChange({ ...draft, question: event.target.value })
          }
          type="text"
          value={draft.question}
        />
      </label>
      <label>
        Exact approved answer
        <textarea
          maxLength={2_000}
          onChange={(event) =>
            onChange({ ...draft, approvedAnswer: event.target.value })
          }
          value={draft.approvedAnswer}
        />
      </label>
    </div>
  );
}

function faqErrorMessage(error: unknown): string {
  if (error instanceof ApprovedFaqApiError) {
    if (error.status === 409) {
      return `${error.message}. Reload if this record changed elsewhere.`;
    }
    return error.message;
  }
  return "The approved FAQ service is unavailable.";
}
