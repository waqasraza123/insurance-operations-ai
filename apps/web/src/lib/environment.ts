export type PublicEnvironment = Readonly<{
  apiBaseUrl: string;
  conversationAiEnabled: boolean;
}>;

export class EnvironmentValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "EnvironmentValidationError";
  }
}

export function parsePublicEnvironment(
  values: Readonly<Record<string, string | undefined>>,
): PublicEnvironment {
  const rawApiBaseUrl = values.NEXT_PUBLIC_API_BASE_URL?.trim();

  if (!rawApiBaseUrl) {
    throw new EnvironmentValidationError(
      "NEXT_PUBLIC_API_BASE_URL is required",
    );
  }

  let apiUrl: URL;

  try {
    apiUrl = new URL(rawApiBaseUrl);
  } catch {
    throw new EnvironmentValidationError(
      "NEXT_PUBLIC_API_BASE_URL must be a valid URL",
    );
  }

  if (apiUrl.protocol !== "http:" && apiUrl.protocol !== "https:") {
    throw new EnvironmentValidationError(
      "NEXT_PUBLIC_API_BASE_URL must use HTTP or HTTPS",
    );
  }

  const rawConversationAiEnabled =
    values.NEXT_PUBLIC_CONVERSATION_AI_ENABLED?.trim().toLowerCase() ?? "false";
  if (
    rawConversationAiEnabled !== "true" &&
    rawConversationAiEnabled !== "false"
  ) {
    throw new EnvironmentValidationError(
      "NEXT_PUBLIC_CONVERSATION_AI_ENABLED must be true or false",
    );
  }

  return {
    apiBaseUrl: apiUrl.toString().replace(/\/$/, ""),
    conversationAiEnabled: rawConversationAiEnabled === "true",
  };
}
