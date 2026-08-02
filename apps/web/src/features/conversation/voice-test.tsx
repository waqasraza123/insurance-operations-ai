"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";

import {
  ConversationApiError,
  authorizeConversationSession,
  confirmConversationIntake,
  endConversationSession,
} from "./api";
import { ConfiguredConversationAdapter } from "./configured-adapter";
import type {
  ConfirmedConversationIntake,
  ConversationClient,
  ConversationDraft,
  ConversationSpeaker,
  ConversationTurn,
} from "./contracts";
import { appendTranscript, validateConfirmation } from "./review";

type VoiceTestProperties = Readonly<{
  apiBaseUrl: string;
}>;

type Phase =
  | "idle"
  | "requesting"
  | "connecting"
  | "active"
  | "review_error"
  | "review"
  | "saving"
  | "saved"
  | "error";

type IntakeForm = {
  fullName: string;
  email: string;
  phone: string;
  intakeIntent: string;
};

const EMPTY_FORM: IntakeForm = {
  fullName: "",
  email: "",
  phone: "",
  intakeIntent: "",
};

export function VoiceTest({ apiBaseUrl }: VoiceTestProperties) {
  const [transcript, setTranscript] = useState<ConversationTurn[]>([]);
  const [form, setForm] = useState<IntakeForm>(EMPTY_FORM);
  const [failureVersion, setFailureVersion] = useState(0);
  const phaseRef = useRef<Phase>("idle");
  const sessionIdRef = useRef<string | undefined>(undefined);
  const intentionalEndRef = useRef(false);

  const handleTranscript = useCallback(
    (speaker: ConversationSpeaker, text: string) => {
      setTranscript((current) => appendTranscript(current, speaker, text));
    },
    [],
  );

  const handleDraft = useCallback((draft: ConversationDraft) => {
    setForm((current) => ({
      fullName: draft.fullName ?? current.fullName,
      email: draft.email ?? current.email,
      phone: draft.phone ?? current.phone,
      intakeIntent: draft.intakeIntent ?? current.intakeIntent,
    }));
  }, []);

  const handleDisconnect = useCallback(() => {
    const sessionId = sessionIdRef.current;
    if (
      phaseRef.current !== "active" ||
      sessionId === undefined ||
      intentionalEndRef.current
    ) {
      return;
    }
    phaseRef.current = "error";
    void endConversationSession(apiBaseUrl, sessionId, "INTERRUPTED").catch(
      () => undefined,
    );
    setFailureVersion((current) => current + 1);
  }, [apiBaseUrl, intentionalEndRef]);

  const handleError = useCallback(() => {
    if (intentionalEndRef.current) {
      return;
    }
    const sessionId = sessionIdRef.current;
    if (phaseRef.current === "active" && sessionId !== undefined) {
      void endConversationSession(apiBaseUrl, sessionId, "FAILED").catch(
        () => undefined,
      );
    }
    phaseRef.current = "error";
    setFailureVersion((current) => current + 1);
  }, [apiBaseUrl, intentionalEndRef]);

  return (
    <ConfiguredConversationAdapter
      onDisconnect={handleDisconnect}
      onDraft={handleDraft}
      onError={handleError}
      onTranscript={handleTranscript}
    >
      {(client) => (
        <VoiceTestExperience
          apiBaseUrl={apiBaseUrl}
          client={client}
          form={form}
          failureVersion={failureVersion}
          intentionalEndRef={intentionalEndRef}
          phaseRef={phaseRef}
          sessionIdRef={sessionIdRef}
          setForm={setForm}
          setTranscript={setTranscript}
          transcript={transcript}
        />
      )}
    </ConfiguredConversationAdapter>
  );
}

type ExperienceProperties = Readonly<{
  apiBaseUrl: string;
  client: ConversationClient;
  failureVersion: number;
  form: IntakeForm;
  intentionalEndRef: MutableRefObject<boolean>;
  phaseRef: MutableRefObject<Phase>;
  sessionIdRef: MutableRefObject<string | undefined>;
  setForm: Dispatch<SetStateAction<IntakeForm>>;
  setTranscript: Dispatch<SetStateAction<ConversationTurn[]>>;
  transcript: ConversationTurn[];
}>;

function VoiceTestExperience({
  apiBaseUrl,
  client,
  failureVersion,
  form,
  intentionalEndRef,
  phaseRef,
  sessionIdRef,
  setForm,
  setTranscript,
  transcript,
}: ExperienceProperties) {
  const [phase, setPhaseState] = useState<Phase>("idle");
  const [disclosureAccepted, setDisclosureAccepted] = useState(false);
  const [microphoneConsent, setMicrophoneConsent] = useState(false);
  const [syntheticDataAcknowledged, setSyntheticDataAcknowledged] =
    useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(180);
  const [maximumDuration, setMaximumDuration] = useState(180);
  const [errorMessage, setErrorMessage] = useState<string>();
  const [savedIntake, setSavedIntake] = useState<ConfirmedConversationIntake>();
  const [confirmationLocked, setConfirmationLocked] = useState(false);
  const confirmationKeyRef = useRef<string | undefined>(undefined);
  const finishConversationRef = useRef<() => Promise<void>>(
    async () => undefined,
  );

  const setPhase = useCallback(
    (nextPhase: Phase) => {
      phaseRef.current = nextPhase;
      setPhaseState(nextPhase);
    },
    [phaseRef],
  );

  const finishConversation = useCallback(async () => {
    const sessionId = sessionIdRef.current;
    if (sessionId === undefined || intentionalEndRef.current) {
      return;
    }
    intentionalEndRef.current = true;
    try {
      if (client.status !== "disconnected") {
        await client.end();
      }
      const reviewAvailable = await endConversationSession(
        apiBaseUrl,
        sessionId,
        "COMPLETED",
      );
      if (!reviewAvailable) {
        setErrorMessage(
          "The session exceeded its limit and cannot be confirmed. " +
            "Start a new session.",
        );
        setPhase("error");
        return;
      }
      setPhase("review");
    } catch {
      setErrorMessage(
        "The conversation ended, but the review could not be prepared. " +
          "Start a new session.",
      );
      setPhase("review_error");
    } finally {
      intentionalEndRef.current = false;
    }
  }, [apiBaseUrl, client, intentionalEndRef, sessionIdRef, setPhase]);

  useEffect(() => {
    finishConversationRef.current = finishConversation;
  }, [finishConversation]);

  useEffect(() => {
    if (failureVersion === 0) {
      return;
    }
    setErrorMessage(
      "The live voice connection ended unexpectedly. Start a new session.",
    );
    setPhase("error");
  }, [failureVersion, setPhase]);

  useEffect(() => {
    if (phase !== "active") {
      return;
    }
    const startedAt = Date.now();
    const interval = window.setInterval(() => {
      const elapsedSeconds = Math.floor((Date.now() - startedAt) / 1_000);
      const nextRemaining = Math.max(maximumDuration - elapsedSeconds, 0);
      setRemainingSeconds(nextRemaining);
      if (nextRemaining === 0) {
        window.clearInterval(interval);
        void finishConversationRef.current();
      }
    }, 1_000);
    return () => window.clearInterval(interval);
  }, [maximumDuration, phase]);

  async function startConversation() {
    if (
      !disclosureAccepted ||
      !microphoneConsent ||
      !syntheticDataAcknowledged
    ) {
      setErrorMessage("Accept the disclosure and microphone consent first.");
      return;
    }
    setErrorMessage(undefined);
    setSavedIntake(undefined);
    setTranscript([]);
    setForm(EMPTY_FORM);
    confirmationKeyRef.current = undefined;
    setConfirmationLocked(false);
    sessionIdRef.current = undefined;
    setPhase("requesting");
    try {
      const permissionStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      permissionStream.getTracks().forEach((track) => track.stop());
      const authorization = await authorizeConversationSession(apiBaseUrl);
      sessionIdRef.current = authorization.sessionId;
      setMaximumDuration(authorization.maximumDurationSeconds);
      setRemainingSeconds(authorization.maximumDurationSeconds);
      setPhase("connecting");
      await client.start(authorization.credential);
      if (phaseRef.current === "error") {
        throw new Error("voice connection failed during startup");
      }
      setPhase("active");
    } catch {
      const sessionId = sessionIdRef.current;
      if (sessionId !== undefined) {
        await endConversationSession(apiBaseUrl, sessionId, "FAILED").catch(
          () => undefined,
        );
      }
      setErrorMessage(
        "The microphone or voice service is unavailable. Check access and try again.",
      );
      setPhase("error");
    }
  }

  async function saveConfirmedIntake() {
    const sessionId = sessionIdRef.current;
    if (sessionId === undefined) {
      setErrorMessage("The conversation session is unavailable.");
      return;
    }
    const validationMessage = validateConfirmation(form, transcript);
    if (validationMessage !== undefined) {
      setErrorMessage(validationMessage);
      return;
    }
    setErrorMessage(undefined);
    setPhase("saving");
    setConfirmationLocked(true);
    confirmationKeyRef.current ??= crypto.randomUUID();
    try {
      const result = await confirmConversationIntake(apiBaseUrl, {
        sessionId,
        fullName: form.fullName.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
        intakeIntent: form.intakeIntent.trim(),
        transcript,
        idempotencyKey: confirmationKeyRef.current,
      });
      setSavedIntake(result);
      setPhase("saved");
    } catch (error) {
      if (
        error instanceof ConversationApiError &&
        (error.status === 400 || error.status === 422)
      ) {
        confirmationKeyRef.current = undefined;
        setConfirmationLocked(false);
      }
      setErrorMessage(
        "The confirmed intake was not saved. Review the fields and retry safely.",
      );
      setPhase("review");
    }
  }

  function resetExperience() {
    sessionIdRef.current = undefined;
    confirmationKeyRef.current = undefined;
    setConfirmationLocked(false);
    setTranscript([]);
    setForm(EMPTY_FORM);
    setSavedIntake(undefined);
    setErrorMessage(undefined);
    setPhase("idle");
  }

  const isBusy = ["requesting", "connecting", "saving"].includes(phase);
  const canStart = phase === "idle" || phase === "error";

  return (
    <div className="voice-grid">
      <section className="voice-card" aria-labelledby="voice-controls-title">
        <p className="eyebrow">Development demo · synthetic data only</p>
        <h1 id="voice-controls-title">Voice AI insurance intake</h1>
        <p className="summary">
          Speak naturally with an AI intake assistant. It can collect contact
          details and needs, but cannot quote, advise, bind coverage, verify
          coverage, or make decisions.
        </p>
        <div className="disclosure" role="note">
          Audio is processed live by ElevenLabs and configured model services.
          This app does not retain raw audio. Nothing is saved until you review
          and explicitly confirm the transcript and customer details.
        </div>
        <label className="consent-row">
          <input
            checked={disclosureAccepted}
            disabled={!canStart}
            onChange={(event) => setDisclosureAccepted(event.target.checked)}
            type="checkbox"
          />
          I understand this is an AI intake assistant with the limits above.
        </label>
        <label className="consent-row">
          <input
            checked={microphoneConsent}
            disabled={!canStart}
            onChange={(event) => setMicrophoneConsent(event.target.checked)}
            type="checkbox"
          />
          I consent to live microphone access for this conversation.
        </label>
        <label className="consent-row">
          <input
            checked={syntheticDataAcknowledged}
            disabled={!canStart}
            onChange={(event) =>
              setSyntheticDataAcknowledged(event.target.checked)
            }
            type="checkbox"
          />
          I will use synthetic test details only, never real customer data.
        </label>
        <div className="voice-actions">
          {canStart && (
            <button
              className="primary-button"
              disabled={
                !disclosureAccepted ||
                !microphoneConsent ||
                !syntheticDataAcknowledged ||
                isBusy
              }
              onClick={() => void startConversation()}
              type="button"
            >
              {phase === "error" ? "Try a new session" : "Start conversation"}
            </button>
          )}
          {phase === "active" && (
            <>
              <button
                className="secondary-button"
                onClick={() => client.setMuted(!client.isMuted)}
                type="button"
              >
                {client.isMuted ? "Unmute" : "Mute"}
              </button>
              <button
                className="secondary-button"
                onClick={() => void finishConversation()}
                type="button"
              >
                Finish and review
              </button>
            </>
          )}
          {phase === "review_error" && (
            <button
              className="secondary-button"
              onClick={() => void finishConversation()}
              type="button"
            >
              Retry preparing review
            </button>
          )}
          {(phase === "saved" || phase === "review") && (
            <button
              className="secondary-button"
              onClick={resetExperience}
              type="button"
            >
              Start over
            </button>
          )}
        </div>
        <p className="voice-status" aria-live="polite">
          {statusLabel(phase, client.mode, remainingSeconds)}
        </p>
        {errorMessage && <p className="error-message">{errorMessage}</p>}
      </section>

      <section className="voice-card" aria-labelledby="transcript-title">
        <h2 id="transcript-title">Conversation transcript</h2>
        <p className="section-help">
          Live text remains in this browser until you explicitly confirm it.
        </p>
        {transcript.length === 0 ? (
          <p className="empty-state">No transcript yet.</p>
        ) : (
          <ol className="transcript-list">
            {transcript.map((turn, index) => (
              <li key={`${turn.speaker}-${index}`}>
                <label>
                  {turn.speaker === "USER" ? "Customer" : "AI assistant"}
                  <textarea
                    aria-label={`Transcript turn ${index + 1}`}
                    disabled={
                      phase === "active" ||
                      phase === "saving" ||
                      phase === "saved" ||
                      confirmationLocked
                    }
                    maxLength={2_000}
                    onChange={(event) => {
                      const text = event.target.value;
                      setTranscript((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, text } : item,
                        ),
                      );
                    }}
                    value={turn.text}
                  />
                </label>
              </li>
            ))}
          </ol>
        )}
      </section>

      {(phase === "review" || phase === "saving" || phase === "saved") && (
        <section
          className="voice-card review-card"
          aria-labelledby="review-title"
        >
          <h2 id="review-title">Review and confirm</h2>
          <p className="section-help">
            Correct every field before saving. Confirmation creates one customer
            and an immutable intake record.
          </p>
          <div className="form-grid">
            <FormField
              disabled={phase !== "review" || confirmationLocked}
              label="Full name"
              name="fullName"
              onChange={(value) => setForm({ ...form, fullName: value })}
              required
              value={form.fullName}
            />
            <FormField
              disabled={phase !== "review" || confirmationLocked}
              label="Email"
              name="email"
              onChange={(value) => setForm({ ...form, email: value })}
              type="email"
              value={form.email}
            />
            <FormField
              disabled={phase !== "review" || confirmationLocked}
              label="Phone"
              name="phone"
              onChange={(value) => setForm({ ...form, phone: value })}
              type="tel"
              value={form.phone}
            />
            <label className="wide-field">
              Insurance intake intent
              <textarea
                disabled={phase !== "review" || confirmationLocked}
                maxLength={2_000}
                onChange={(event) =>
                  setForm({ ...form, intakeIntent: event.target.value })
                }
                required
                value={form.intakeIntent}
              />
            </label>
          </div>
          {phase === "review" && (
            <button
              className="primary-button"
              onClick={() => void saveConfirmedIntake()}
              type="button"
            >
              {confirmationLocked
                ? "Retry confirmation"
                : "Confirm and create customer"}
            </button>
          )}
          {phase === "saving" && (
            <p aria-live="polite">Saving confirmation…</p>
          )}
          {savedIntake && (
            <p className="success-message" aria-live="polite">
              Saved customer {savedIntake.customerName}. Intake ID: {" "}
              <code>{savedIntake.conversationIntakeId}</code>
            </p>
          )}
        </section>
      )}
    </div>
  );
}

type FormFieldProperties = Readonly<{
  disabled: boolean;
  label: string;
  name: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: "email" | "tel" | "text";
  value: string;
}>;

function FormField({
  disabled,
  label,
  name,
  onChange,
  required = false,
  type = "text",
  value,
}: FormFieldProperties) {
  return (
    <label>
      {label}
      <input
        disabled={disabled}
        name={name}
        onChange={(event) => onChange(event.target.value)}
        required={required}
        type={type}
        value={value}
      />
    </label>
  );
}

function statusLabel(
  phase: Phase,
  mode: "speaking" | "listening" | undefined,
  remainingSeconds: number,
): string {
  if (phase === "active") {
    const activity = mode === "speaking" ? "AI is speaking" : "AI is listening";
    return `${activity} · ${formatDuration(remainingSeconds)} remaining`;
  }
  const labels: Record<Phase, string> = {
    idle: "Ready to request microphone access",
    requesting: "Requesting microphone access and authorization…",
    connecting: "Connecting securely…",
    active: "Conversation active",
    review_error: "Conversation ended · review preparation needs a retry",
    review: "Conversation ended · review required before saving",
    saving: "Saving confirmed intake…",
    saved: "Confirmed intake saved",
    error: "Session unavailable",
  };
  return labels[phase];
}

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}
