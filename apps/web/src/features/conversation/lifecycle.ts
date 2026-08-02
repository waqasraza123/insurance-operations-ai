export type ConversationPhase =
  | "idle"
  | "requesting"
  | "connecting"
  | "active"
  | "stopping"
  | "review_error"
  | "review"
  | "saving"
  | "saved"
  | "error";

export type ConnectionFailureSource = "disconnect" | "provider_error";

export type ConnectionFailure = Readonly<{
  outcome: "INTERRUPTED" | "FAILED";
  sessionId: string;
}>;

type ConnectionFailureInput = Readonly<{
  intentionalEnd: boolean;
  phase: ConversationPhase;
  sessionId: string | undefined;
  source: ConnectionFailureSource;
}>;

export function classifyConnectionFailure({
  intentionalEnd,
  phase,
  sessionId,
  source,
}: ConnectionFailureInput): ConnectionFailure | undefined {
  if (
    intentionalEnd ||
    sessionId === undefined ||
    !isLiveConversationPhase(phase)
  ) {
    return undefined;
  }

  return {
    outcome: source === "disconnect" ? "INTERRUPTED" : "FAILED",
    sessionId,
  };
}

export function isLiveConversationPhase(phase: ConversationPhase): boolean {
  return phase === "connecting" || phase === "active";
}
