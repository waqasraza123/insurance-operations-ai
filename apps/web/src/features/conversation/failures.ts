import { ConversationApiError } from "./api";

export type ConfirmationFailureAction =
  "correct_input" | "retry_confirmation" | "start_new_session";

export type ConfirmationFailure = Readonly<{
  action: ConfirmationFailureAction;
  message: string;
}>;

export function startFailureMessage(error: unknown): string {
  if (!(error instanceof ConversationApiError)) {
    return "The microphone or voice service is unavailable. Check access and try again.";
  }

  switch (error.status) {
    case 404:
      return "The Voice AI demo is unavailable in this environment.";
    case 409:
      return "Another voice session is still active. Wait briefly and try again.";
    case 429:
      return "The daily Voice AI session limit has been reached. Try again tomorrow.";
    default:
      return "The voice service is unavailable. Try again shortly.";
  }
}

export function classifyConfirmationFailure(
  error: unknown,
): ConfirmationFailure {
  if (
    error instanceof ConversationApiError &&
    (error.status === 400 || error.status === 422)
  ) {
    return {
      action: "correct_input",
      message: "The intake was not saved. Review the fields and try again.",
    };
  }

  if (
    error instanceof ConversationApiError &&
    (error.status === 404 || error.status === 409 || error.status === 410)
  ) {
    return {
      action: "start_new_session",
      message:
        "This conversation can no longer be confirmed. Start a new session.",
    };
  }

  return {
    action: "retry_confirmation",
    message: "The intake was not saved. Retry confirmation safely.",
  };
}
