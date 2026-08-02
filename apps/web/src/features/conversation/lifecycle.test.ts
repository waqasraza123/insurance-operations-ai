import { describe, expect, it } from "vitest";

import { classifyConnectionFailure } from "./lifecycle";

describe("conversation lifecycle", () => {
  it("marks startup and active disconnects as interrupted", () => {
    for (const phase of ["connecting", "active"] as const) {
      expect(
        classifyConnectionFailure({
          intentionalEnd: false,
          phase,
          sessionId: "session-1",
          source: "disconnect",
        }),
      ).toEqual({ outcome: "INTERRUPTED", sessionId: "session-1" });
    }
  });

  it("marks provider errors during startup and active use as failed", () => {
    for (const phase of ["connecting", "active"] as const) {
      expect(
        classifyConnectionFailure({
          intentionalEnd: false,
          phase,
          sessionId: "session-1",
          source: "provider_error",
        }),
      ).toEqual({ outcome: "FAILED", sessionId: "session-1" });
    }
  });

  it("ignores intentional, sessionless, and terminal disconnects", () => {
    expect(
      classifyConnectionFailure({
        intentionalEnd: true,
        phase: "active",
        sessionId: "session-1",
        source: "disconnect",
      }),
    ).toBeUndefined();
    expect(
      classifyConnectionFailure({
        intentionalEnd: false,
        phase: "connecting",
        sessionId: undefined,
        source: "provider_error",
      }),
    ).toBeUndefined();
    expect(
      classifyConnectionFailure({
        intentionalEnd: false,
        phase: "review",
        sessionId: "session-1",
        source: "disconnect",
      }),
    ).toBeUndefined();
  });
});
