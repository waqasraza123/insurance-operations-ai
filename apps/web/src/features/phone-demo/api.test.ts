import { describe, expect, it } from "vitest";

import { parsePhoneDemoStatus } from "./api";

describe("parsePhoneDemoStatus", () => {
  it("accepts the redacted public status contract", () => {
    expect(
      parsePhoneDemoStatus({
        state: "CALLBACK_REQUESTED",
        received_at: "2026-08-19T12:00:00Z",
        answered_at: "2026-08-19T12:00:02Z",
        ended_at: "2026-08-19T12:01:00Z",
        consent_completed: true,
        lead_created: true,
        urgency: "NORMAL",
        handoff_kind: "CALLBACK",
        handoff_status: "REQUESTED",
      }),
    ).toEqual({
      state: "CALLBACK_REQUESTED",
      receivedAt: "2026-08-19T12:00:00Z",
      answeredAt: "2026-08-19T12:00:02Z",
      endedAt: "2026-08-19T12:01:00Z",
      consentCompleted: true,
      leadCreated: true,
      urgency: "NORMAL",
      handoffKind: "CALLBACK",
      handoffStatus: "REQUESTED",
    });
  });

  it("rejects unexpected fields in state-bearing values", () => {
    expect(() =>
      parsePhoneDemoStatus({
        state: "COMPLETED",
        received_at: null,
        answered_at: null,
        ended_at: null,
        consent_completed: false,
        lead_created: false,
        urgency: null,
        handoff_kind: null,
        handoff_status: null,
      }),
    ).toThrow("invalid response");
  });
});
