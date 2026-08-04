import { describe, expect, it } from "vitest";

import { ConversationApiError } from "./api";
import { classifyConfirmationFailure, startFailureMessage } from "./failures";

describe("conversation failure recovery", () => {
  it("gives actionable authorization guidance for bounded limits", () => {
    expect(startFailureMessage(new ConversationApiError(409, "conflict"))).toBe(
      "Another voice session is still active. Wait briefly and try again.",
    );
    expect(startFailureMessage(new ConversationApiError(429, "limited"))).toBe(
      "The daily Voice AI session limit has been reached. Try again tomorrow.",
    );
  });

  it("allows corrected input to use a new confirmation request", () => {
    expect(
      classifyConfirmationFailure(new ConversationApiError(422, "invalid")),
    ).toEqual({
      action: "correct_input",
      message: "The intake was not saved. Review the fields and try again.",
    });
  });

  it("separates terminal sessions from safely retryable failures", () => {
    expect(
      classifyConfirmationFailure(new ConversationApiError(410, "expired")),
    ).toEqual({
      action: "start_new_session",
      message:
        "This conversation can no longer be confirmed. Start a new session.",
    });
    expect(classifyConfirmationFailure(new TypeError("network error"))).toEqual(
      {
        action: "retry_confirmation",
        message: "The intake was not saved. Retry confirmation safely.",
      },
    );
  });
});
