"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Brand } from "@/components/brand";

import {
  getReceptionistSettings,
  ReceptionistSettingsApiError,
  replaceReceptionistSettings,
} from "./api";
import type {
  ReceptionistSettings,
  ReceptionistSettingsDraft,
} from "./contracts";
import { settingsDraft, validateSettingsDraft } from "./settings-form";

type ReceptionistSettingsProperties = Readonly<{
  apiBaseUrl: string;
}>;

const EMPTY_DRAFT: ReceptionistSettingsDraft = {
  publicName: "",
  greeting: "",
  officeHours: "",
  contactEmail: "",
  contactPhone: "",
  supportedInsuranceCategories: "",
  escalationMessage: "",
};

export function ReceptionistSettingsEditor({
  apiBaseUrl,
}: ReceptionistSettingsProperties) {
  const [settings, setSettings] = useState<ReceptionistSettings>();
  const [draft, setDraft] = useState<ReceptionistSettingsDraft>(EMPTY_DRAFT);
  const [status, setStatus] = useState<"loading" | "ready" | "saving">(
    "loading",
  );
  const [message, setMessage] = useState<string>();

  useEffect(() => {
    let active = true;
    void getReceptionistSettings(apiBaseUrl)
      .then((result) => {
        if (!active) return;
        setSettings(result);
        setDraft(settingsDraft(result));
        setStatus("ready");
      })
      .catch((error: unknown) => {
        if (!active) return;
        setMessage(settingsErrorMessage(error));
        setStatus("ready");
      });
    return () => {
      active = false;
    };
  }, [apiBaseUrl]);

  async function save() {
    const validationMessage = validateSettingsDraft(draft);
    if (validationMessage !== undefined) {
      setMessage(validationMessage);
      return;
    }
    setMessage(undefined);
    setStatus("saving");
    try {
      const result = await replaceReceptionistSettings(
        apiBaseUrl,
        draft,
        settings?.rowVersion ?? 0,
      );
      setSettings(result);
      setDraft(settingsDraft(result));
      setMessage("Receptionist settings saved and audited.");
    } catch (error) {
      setMessage(settingsErrorMessage(error));
    } finally {
      setStatus("ready");
    }
  }

  return (
    <main className="settings-shell">
      <nav className="top-nav" aria-label="Primary navigation">
        <Brand />
        <div className="nav-links">
          <Link className="text-link" href="/approved-faqs">
            Approved FAQs
          </Link>
          <Link className="text-link" href="/voice-test">
            Open receptionist
          </Link>
        </div>
      </nav>
      <header className="page-header">
        <p className="eyebrow">Development workspace</p>
        <h1>Configure your AI receptionist</h1>
        <p className="summary">
          These backend-owned settings define the public agency identity and
          safe handoff language used across the receptionist experience.
        </p>
      </header>
      <section className="settings-card" aria-labelledby="agency-profile-title">
        <div className="section-heading-row">
          <div>
            <p className="section-kicker">Agency profile</p>
            <h2 id="agency-profile-title">Public receptionist settings</h2>
          </div>
          {settings && (
            <span className="version-badge">Version {settings.rowVersion}</span>
          )}
        </div>
        {status === "loading" ? (
          <p aria-live="polite">Loading receptionist settings…</p>
        ) : (
          <div className="settings-grid">
            <SettingsField
              label="Agency public name"
              maxLength={160}
              onChange={(publicName) => setDraft({ ...draft, publicName })}
              value={draft.publicName}
            />
            <SettingsField
              label="Public email"
              maxLength={320}
              onChange={(contactEmail) => setDraft({ ...draft, contactEmail })}
              type="email"
              value={draft.contactEmail}
            />
            <SettingsField
              label="Public phone"
              maxLength={32}
              onChange={(contactPhone) => setDraft({ ...draft, contactPhone })}
              type="tel"
              value={draft.contactPhone}
            />
            <SettingsTextarea
              className="wide-field"
              label="Opening greeting"
              maxLength={600}
              onChange={(greeting) => setDraft({ ...draft, greeting })}
              value={draft.greeting}
            />
            <SettingsTextarea
              label="Office hours"
              maxLength={1_000}
              onChange={(officeHours) => setDraft({ ...draft, officeHours })}
              value={draft.officeHours}
            />
            <SettingsTextarea
              help="Enter one category per line."
              label="Supported insurance categories"
              maxLength={1_600}
              onChange={(supportedInsuranceCategories) =>
                setDraft({ ...draft, supportedInsuranceCategories })
              }
              value={draft.supportedInsuranceCategories}
            />
            <SettingsTextarea
              className="wide-field"
              label="Human escalation message"
              maxLength={600}
              onChange={(escalationMessage) =>
                setDraft({ ...draft, escalationMessage })
              }
              value={draft.escalationMessage}
            />
          </div>
        )}
        <div className="settings-actions">
          <button
            className="primary-button"
            disabled={status !== "ready"}
            onClick={() => void save()}
            type="button"
          >
            {status === "saving" ? "Saving…" : "Save configuration"}
          </button>
          <p className="settings-note">
            Updates use optimistic concurrency and create an agency audit event.
          </p>
        </div>
        {message && (
          <p
            className={
              message.includes("saved") ? "success-message" : "error-message"
            }
            role="status"
          >
            {message}
          </p>
        )}
      </section>
    </main>
  );
}

type SettingsFieldProperties = Readonly<{
  label: string;
  maxLength: number;
  onChange: (value: string) => void;
  type?: "email" | "tel" | "text";
  value: string;
}>;

function SettingsField({
  label,
  maxLength,
  onChange,
  type = "text",
  value,
}: SettingsFieldProperties) {
  return (
    <label>
      {label}
      <input
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        type={type}
        value={value}
      />
    </label>
  );
}

type SettingsTextareaProperties = Readonly<{
  className?: string;
  help?: string;
  label: string;
  maxLength: number;
  onChange: (value: string) => void;
  value: string;
}>;

function SettingsTextarea({
  className,
  help,
  label,
  maxLength,
  onChange,
  value,
}: SettingsTextareaProperties) {
  return (
    <label className={className}>
      {label}
      {help && <span className="field-help">{help}</span>}
      <textarea
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  );
}

function settingsErrorMessage(error: unknown): string {
  if (error instanceof ReceptionistSettingsApiError) {
    if (error.status === 404) {
      return "Run the development seed, then reload this page.";
    }
    if (error.status === 409) {
      return "These settings changed elsewhere. Reload before saving again.";
    }
    return error.message;
  }
  return "The receptionist settings service is unavailable.";
}
