import type {
  ConfirmedConversationIntake,
  ConversationSessionAuthorization,
  ConversationTurn,
} from "./contracts";

type ErrorBody = Readonly<{
  error?: Readonly<{
    message?: unknown;
  }>;
}>;

export class ConversationApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ConversationApiError";
    this.status = status;
  }
}

export async function authorizeConversationSession(
  apiBaseUrl: string,
): Promise<ConversationSessionAuthorization> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/development/conversation-sessions`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ai_disclosure_accepted: true,
        microphone_consent_granted: true,
        synthetic_data_acknowledged: true,
      }),
    },
  );
  const body: unknown = await readJson(response);
  if (!response.ok) {
    throw apiError(response, body);
  }
  if (!isRecord(body) || !isRecord(body.connection)) {
    throw new ConversationApiError(
      502,
      "The voice service returned invalid data",
    );
  }
  const sessionId = requiredString(body.session_id);
  const credential = requiredString(body.connection.credential);
  const maximumDurationSeconds = body.maximum_duration_seconds;
  const confirmationExpiresAt = requiredString(body.confirmation_expires_at);
  if (
    sessionId === undefined ||
    credential === undefined ||
    confirmationExpiresAt === undefined ||
    typeof maximumDurationSeconds !== "number"
  ) {
    throw new ConversationApiError(
      502,
      "The voice service returned invalid data",
    );
  }
  return {
    sessionId,
    credential,
    maximumDurationSeconds,
    confirmationExpiresAt,
  };
}

export async function endConversationSession(
  apiBaseUrl: string,
  sessionId: string,
  outcome: "COMPLETED" | "INTERRUPTED" | "FAILED",
): Promise<boolean> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/development/conversation-sessions/${sessionId}/end`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ outcome }),
    },
  );
  const body: unknown = await readJson(response);
  if (!response.ok) {
    throw apiError(response, body);
  }
  if (!isRecord(body) || typeof body.review_available !== "boolean") {
    throw new ConversationApiError(
      502,
      "The voice service returned invalid data",
    );
  }
  return body.review_available;
}

type ConfirmationInput = Readonly<{
  sessionId: string;
  fullName: string;
  email: string;
  phone: string;
  intakeIntent: string;
  transcript: readonly ConversationTurn[];
  idempotencyKey: string;
}>;

export async function confirmConversationIntake(
  apiBaseUrl: string,
  input: ConfirmationInput,
): Promise<ConfirmedConversationIntake> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/development/conversation-intakes`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": input.idempotencyKey,
      },
      body: JSON.stringify({
        conversation_session_id: input.sessionId,
        customer: {
          full_name: input.fullName,
          email: input.email || null,
          phone: input.phone || null,
        },
        intake_intent: input.intakeIntent,
        transcript: input.transcript.map((turn) => ({
          speaker: turn.speaker,
          text: turn.text,
        })),
      }),
    },
  );
  const body: unknown = await readJson(response);
  if (!response.ok) {
    throw apiError(response, body);
  }
  if (!isRecord(body) || !isRecord(body.customer)) {
    throw new ConversationApiError(
      502,
      "The intake service returned invalid data",
    );
  }
  const conversationIntakeId = requiredString(body.conversation_intake_id);
  const customerId = requiredString(body.customer.id);
  const customerName = requiredString(body.customer.full_name);
  const confirmedAt = requiredString(body.confirmed_at);
  if (
    conversationIntakeId === undefined ||
    customerId === undefined ||
    customerName === undefined ||
    confirmedAt === undefined
  ) {
    throw new ConversationApiError(
      502,
      "The intake service returned invalid data",
    );
  }
  return { conversationIntakeId, customerId, customerName, confirmedAt };
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

function apiError(response: Response, body: unknown): ConversationApiError {
  const errorBody = isRecord(body) ? (body as ErrorBody) : undefined;
  const message = errorBody?.error?.message;
  return new ConversationApiError(
    response.status,
    typeof message === "string" && message.trim()
      ? message
      : "The request could not be completed",
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function requiredString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}
