export type PublicEnvironment = Readonly<{
  apiBaseUrl: string;
  conversationAiEnabled: boolean;
  demoSandboxEnabled: boolean;
  demoPhoneNumber: string | null;
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
  const conversationAiEnabled = parseBoolean(
    rawConversationAiEnabled,
    "NEXT_PUBLIC_CONVERSATION_AI_ENABLED",
  );
  const demoSandboxEnabled = parseBoolean(
    values.NEXT_PUBLIC_DEMO_SANDBOX_ENABLED?.trim().toLowerCase() ?? "false",
    "NEXT_PUBLIC_DEMO_SANDBOX_ENABLED",
  );
  const demoPhoneNumber = values.NEXT_PUBLIC_DEMO_PHONE_NUMBER?.trim() || null;
  if (
    demoSandboxEnabled &&
    (demoPhoneNumber === null || !/^\+[1-9][0-9]{7,14}$/.test(demoPhoneNumber))
  ) {
    throw new EnvironmentValidationError(
      "NEXT_PUBLIC_DEMO_PHONE_NUMBER must use E.164 format in demo sandbox mode",
    );
  }

  return {
    apiBaseUrl: apiUrl.toString().replace(/\/$/, ""),
    conversationAiEnabled,
    demoSandboxEnabled,
    demoPhoneNumber,
  };
}

function parseBoolean(value: string, name: string): boolean {
  if (value !== "true" && value !== "false") {
    throw new EnvironmentValidationError(`${name} must be true or false`);
  }
  return value === "true";
}
