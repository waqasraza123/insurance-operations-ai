export type ConversationSpeaker = "USER" | "AGENT";

export type ConversationTurn = Readonly<{
  speaker: ConversationSpeaker;
  text: string;
}>;

export type ConversationDraft = Readonly<{
  fullName?: string;
  email?: string;
  phone?: string;
  intakeIntent?: string;
}>;

export type ApprovedFaqToolResult = Readonly<{
  matched: boolean;
  answer: string | null;
  fallbackMessage: string;
  source: Readonly<{
    faqId: string;
    question: string;
    rowVersion: number;
  }> | null;
}>;

export type ApprovedFaqToolLookup = (
  query: string,
) => Promise<ApprovedFaqToolResult>;

export type ConversationConnectionStatus =
  "disconnected" | "connecting" | "connected";

export type ConversationMode = "speaking" | "listening" | undefined;

export type ConversationClient = Readonly<{
  status: ConversationConnectionStatus;
  mode: ConversationMode;
  isMuted: boolean;
  start: (credential: string) => Promise<void>;
  end: () => Promise<void>;
  setMuted: (muted: boolean) => void;
}>;

export type ConversationSessionAuthorization = Readonly<{
  sessionId: string;
  credential: string;
  maximumDurationSeconds: number;
  confirmationExpiresAt: string;
}>;

export type ConfirmedConversationIntake = Readonly<{
  conversationIntakeId: string;
  customerId: string;
  customerName: string;
  confirmedAt: string;
}>;
