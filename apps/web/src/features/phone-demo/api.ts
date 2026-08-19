import type { PhoneDemoState, PhoneDemoStatus } from "./contracts";

const PHONE_DEMO_PATH = "/api/v1/demo/latest-phone-call";
const REQUEST_TIMEOUT_MILLISECONDS = 5_000;
const STATES: readonly PhoneDemoState[] = [
  "READY",
  "RINGING",
  "IN_PROGRESS",
  "LEAD_CREATED",
  "TRANSFERRED",
  "CALLBACK_REQUESTED",
  "FAILED",
];

export async function getPhoneDemoStatus(
  apiBaseUrl: string,
): Promise<PhoneDemoStatus> {
  const response = await fetch(`${apiBaseUrl}${PHONE_DEMO_PATH}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MILLISECONDS),
  });
  if (!response.ok) throw new Error("The phone demo status is unavailable");
  return parsePhoneDemoStatus(await response.json());
}

export function parsePhoneDemoStatus(body: unknown): PhoneDemoStatus {
  if (!isRecord(body) || !STATES.includes(body.state as PhoneDemoState)) {
    throw new Error("The phone demo returned an invalid response");
  }
  if (
    typeof body.consent_completed !== "boolean" ||
    typeof body.lead_created !== "boolean"
  ) {
    throw new Error("The phone demo returned an invalid response");
  }
  return {
    state: body.state as PhoneDemoState,
    receivedAt: nullableString(body.received_at),
    answeredAt: nullableString(body.answered_at),
    endedAt: nullableString(body.ended_at),
    consentCompleted: body.consent_completed,
    leadCreated: body.lead_created,
    urgency: enumOrNull(body.urgency, ["LOW", "NORMAL", "HIGH"]),
    handoffKind: enumOrNull(body.handoff_kind, ["CALLBACK", "LIVE_TRANSFER"]),
    handoffStatus: enumOrNull(body.handoff_status, [
      "REQUESTED",
      "ACKNOWLEDGED",
      "COMPLETED",
      "CANCELLED",
    ]),
  };
}

function enumOrNull<const Value extends string>(
  value: unknown,
  allowed: readonly Value[],
): Value | null {
  if (value === null) return null;
  if (typeof value !== "string" || !allowed.includes(value as Value)) {
    throw new Error("The phone demo returned an invalid response");
  }
  return value as Value;
}

function nullableString(value: unknown): string | null {
  if (value === null) return null;
  if (typeof value !== "string" || !value.trim()) {
    throw new Error("The phone demo returned an invalid response");
  }
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
