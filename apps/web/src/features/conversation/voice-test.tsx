"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";

import {
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
import {
  classifyConfirmationFailure,
  startFailureMessage,
} from "./failures";
import {
  classifyConnectionFailure,
  isLiveConversationPhase,
} from "./lifecycle";
import type {
  ConnectionFailureSource,
  ConversationPhase,
} from "./lifecycle";
import { appendTranscript, validateConfirmation } from "./review";

type VoiceTestProperties = Readonly<{
  apiBaseUrl: string;
}>;

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
  const [phase, setPhaseState] = useState<ConversationPhase>("idle");
  const [errorMessage, setErrorMessage] = useState<string>();
  const phaseRef = useRef<ConversationPhase>("idle");
  const sessionIdRef = useRef<string | undefined>(undefined);
  const intentionalEndRef = useRef(false);

  const setPhase = useCallback((nextPhase: ConversationPhase) => {
    phaseRef.current = nextPhase;
    setPhaseState(nextPhase);
  }, []);

  const handleTranscript = useCallback(
    (speaker: ConversationSpeaker, text: string) => {
      if (!isLiveConversationPhase(phaseRef.current)) {
        return;
      }
      setTranscript((current) => appendTranscript(current, speaker, text));
    },
    [],
  );

  const handleDraft = useCallback((draft: ConversationDraft) => {
    if (!isLiveConversationPhase(phaseRef.current)) {
      return;
    }
    setForm((current) => ({
      fullName: draft.fullName ?? current.fullName,
      email: draft.email ?? current.email,
      phone: draft.phone ?? current.phone,
      intakeIntent: draft.intakeIntent ?? current.intakeIntent,
    }));
  }, []);

  const handleConnectionFailure = useCallback(
    (source: ConnectionFailureSource) => {
      const failure = classifyConnectionFailure({
        intentionalEnd: intentionalEndRef.current,
        phase: phaseRef.current,
        sessionId: sessionIdRef.current,
        source,
      });
      if (failure === undefined) {
        return;
      }

      setErrorMessage(
        "The live voice connection ended unexpectedly. Start a new session.",
      );
      setPhase("stopping");
      void endConversationSession(
        apiBaseUrl,
        failure.sessionId,
        failure.outcome,
      )
        .catch(() => undefined)
        .finally(() => {
          if (phaseRef.current === "stopping") {
            setPhase("error");
          }
        });
    },
    [apiBaseUrl, setPhase],
  );

  const handleDisconnect = useCallback(() => {
    handleConnectionFailure("disconnect");
  }, [handleConnectionFailure]);

  const handleError = useCallback(() => {
    handleConnectionFailure("provider_error");
  }, [handleConnectionFailure]);

  useEffect(() => {
    return () => {
      const failure = classifyConnectionFailure({
        intentionalEnd: intentionalEndRef.current,
        phase: phaseRef.current,
        sessionId: sessionIdRef.current,
        source: "disconnect",
      });
      if (failure === undefined) {
        return;
      }

      phaseRef.current = "stopping";
      void endConversationSession(
        apiBaseUrl,
        failure.sessionId,
        failure.outcome,
      ).catch(() => undefined);
    };
  }, [apiBaseUrl]);

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
          errorMessage={errorMessage}
          form={form}
          intentionalEndRef={intentionalEndRef}
          phase={phase}
          phaseRef={phaseRef}
          sessionIdRef={sessionIdRef}
          setErrorMessage={setErrorMessage}
          setForm={setForm}
          setPhase={setPhase}
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
  errorMessage: string | undefined;
  form: IntakeForm;
  intentionalEndRef: MutableRefObject<boolean>;
  phase: ConversationPhase;
  phaseRef: MutableRefObject<ConversationPhase>;
  sessionIdRef: MutableRefObject<string | undefined>;
  setErrorMessage: Dispatch<SetStateAction<string | undefined>>;
  setForm: Dispatch<SetStateAction<IntakeForm>>;
  setPhase: (phase: ConversationPhase) => void;
  setTranscript: Dispatch<SetStateAction<ConversationTurn[]>>;
  transcript: ConversationTurn[];
}>;

function VoiceTestExperience({
  apiBaseUrl,
  client,
  errorMessage,
  form,
  intentionalEndRef,
  phase,
  phaseRef,
  sessionIdRef,
  setErrorMessage,
  setForm,
  setPhase,
  setTranscript,
  transcript,
}: ExperienceProperties) {
  const [disclosureAccepted, setDisclosureAccepted] = useState(false);
  const [microphoneConsent, setMicrophoneConsent] = useState(false);
  const [syntheticDataAcknowledged, setSyntheticDataAcknowledged] =
    useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(180);
  const [maximumDuration, setMaximumDuration] = useState(180);
  const [savedIntake, setSavedIntake] = useState<ConfirmedConversationIntake>();
  const [confirmationLocked, setConfirmationLocked] = useState(false);
  const confirmationKeyRef = useRef<string | undefined>(undefined);
  const finishConversationRef = useRef<() => Promise<void>>(
    async () => undefined,
  );

  const finishConversation = useCallback(async () => {
    const sessionId = sessionIdRef.current;
    if (sessionId === undefined || intentionalEndRef.current) {
      return;
    }
    intentionalEndRef.current = true;
    setErrorMessage(undefined);
    setPhase("stopping");
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
  }, [
    apiBaseUrl,
    client,
    intentionalEndRef,
    sessionIdRef,
    setErrorMessage,
    setPhase,
  ]);

  useEffect(() => {
    finishConversationRef.current = finishConversation;
  }, [finishConversation]);

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
      if (phaseRef.current === "stopping" || phaseRef.current === "error") {
        throw new Error("voice connection failed during startup");
      }
      setPhase("active");
    } catch (error) {
      if (phaseRef.current === "stopping" || phaseRef.current === "error") {
        return;
      }
      const sessionId = sessionIdRef.current;
      if (sessionId !== undefined) {
        setPhase("stopping");
        await endConversationSession(apiBaseUrl, sessionId, "FAILED").catch(
          () => undefined,
        );
      }
      setErrorMessage(startFailureMessage(error));
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
      const failure = classifyConfirmationFailure(error);
      if (failure.action === "correct_input") {
        confirmationKeyRef.current = undefined;
        setConfirmationLocked(false);
      }
      setErrorMessage(failure.message);
      setPhase(failure.action === "start_new_session" ? "error" : "review");
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

  const isBusy = ["requesting", "connecting", "stopping", "saving"].includes(
    phase,
  );
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
          You are interacting with an AI, not a human. Your microphone audio
          and conversation are recorded during the session and may be shared
          with ElevenLabs and third-party AI/LLM providers for processing. Use
          fictional test data only—never real customer or sensitive
          information. This app does not retain raw audio or a live draft
          transcript. Intake details and transcript text are saved only after
          you review and explicitly confirm them.
        </div>
        <label className="consent-row">
          <input
            checked={disclosureAccepted}
            disabled={!canStart}
            onChange={(event) => setDisclosureAccepted(event.target.checked)}
            type="checkbox"
          />
          I agree to the AI, recording, sharing, and provider-processing
          disclosure above.
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
          I will use fictional test details only, never real customer or
          sensitive data.
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
        {errorMessage && (
          <p className="error-message" role="alert">
            {errorMessage}
          </p>
        )}
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
                      phase === "connecting" ||
                      phase === "active" ||
                      phase === "stopping" ||
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
          {phase === "saving" && <p aria-live="polite">Saving confirmation…</p>}
          {savedIntake && (
            <p className="success-message" aria-live="polite">
              Saved customer {savedIntake.customerName}. Intake ID:{" "}
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
  phase: ConversationPhase,
  mode: "speaking" | "listening" | undefined,
  remainingSeconds: number,
): string {
  if (phase === "active") {
    const activity = mode === "speaking" ? "AI is speaking" : "AI is listening";
    return `${activity} · ${formatDuration(remainingSeconds)} remaining`;
  }
  const labels: Record<ConversationPhase, string> = {
    idle: "Ready to request microphone access",
    requesting: "Requesting microphone access and authorization…",
    connecting: "Connecting securely…",
    active: "Conversation active",
    stopping: "Ending the conversation securely…",
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
