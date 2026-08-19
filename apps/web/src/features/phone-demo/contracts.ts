export type PhoneDemoState =
  | "READY"
  | "RINGING"
  | "IN_PROGRESS"
  | "LEAD_CREATED"
  | "TRANSFERRED"
  | "CALLBACK_REQUESTED"
  | "FAILED";

export type PhoneDemoStatus = Readonly<{
  state: PhoneDemoState;
  receivedAt: string | null;
  answeredAt: string | null;
  endedAt: string | null;
  consentCompleted: boolean;
  leadCreated: boolean;
  urgency: "LOW" | "NORMAL" | "HIGH" | null;
  handoffKind: "CALLBACK" | "LIVE_TRANSFER" | null;
  handoffStatus:
    "REQUESTED" | "ACKNOWLEDGED" | "COMPLETED" | "CANCELLED" | null;
}>;
