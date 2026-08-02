import type { ConversationSpeaker, ConversationTurn } from "./contracts";

export type IntakeReviewValues = Readonly<{
  fullName: string;
  email: string;
  phone: string;
  intakeIntent: string;
}>;

export function appendTranscript(
  current: readonly ConversationTurn[],
  speaker: ConversationSpeaker,
  text: string,
): ConversationTurn[] {
  const normalizedText = text.trim();
  const lastTurn = current.at(-1);
  if (lastTurn?.speaker === speaker) {
    if (lastTurn.text === normalizedText) {
      return [...current];
    }
    if (
      normalizedText.startsWith(lastTurn.text) ||
      lastTurn.text.startsWith(normalizedText)
    ) {
      return [...current.slice(0, -1), { speaker, text: normalizedText }];
    }
  }
  return [...current, { speaker, text: normalizedText }];
}

export function validateConfirmation(
  form: IntakeReviewValues,
  transcript: readonly ConversationTurn[],
): string | undefined {
  if (!form.fullName.trim()) {
    return "Full name is required.";
  }
  if (!form.email.trim() && !form.phone.trim()) {
    return "Email or phone is required.";
  }
  if (!form.intakeIntent.trim()) {
    return "Insurance intake intent is required.";
  }
  const speakers = new Set(transcript.map((turn) => turn.speaker));
  if (!speakers.has("USER") || !speakers.has("AGENT")) {
    return "The confirmed transcript needs customer and AI assistant turns.";
  }
  if (transcript.some((turn) => !turn.text.trim())) {
    return "Transcript turns cannot be empty.";
  }
  return undefined;
}
