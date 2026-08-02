import { describe, expect, it } from "vitest";

import { appendTranscript, validateConfirmation } from "./review";

describe("conversation review", () => {
  it("replaces an adjacent partial transcript instead of duplicating it", () => {
    expect(
      appendTranscript(
        [{ speaker: "USER", text: "I need renters" }],
        "USER",
        "I need renters insurance",
      ),
    ).toEqual([{ speaker: "USER", text: "I need renters insurance" }]);
  });

  it("requires contact, intent, and both conversation speakers", () => {
    expect(
      validateConfirmation(
        {
          fullName: "Synthetic Customer",
          email: "",
          phone: "",
          intakeIntent: "Renters insurance",
        },
        [
          { speaker: "AGENT", text: "How may I help?" },
          { speaker: "USER", text: "I need renters insurance." },
        ],
      ),
    ).toBe("Email or phone is required.");

    expect(
      validateConfirmation(
        {
          fullName: "Synthetic Customer",
          email: "synthetic@example.test",
          phone: "",
          intakeIntent: "Renters insurance",
        },
        [
          { speaker: "AGENT", text: "How may I help?" },
          { speaker: "USER", text: "I need renters insurance." },
        ],
      ),
    ).toBeUndefined();
  });
});
