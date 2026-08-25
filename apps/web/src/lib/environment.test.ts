import { describe, expect, it } from "vitest";

import {
  EnvironmentValidationError,
  parseDemoPhoneNumber,
  parsePublicEnvironment,
} from "./environment";

describe("parsePublicEnvironment", () => {
  it("returns a normalized API URL", () => {
    expect(
      parsePublicEnvironment({
        NEXT_PUBLIC_API_BASE_URL: "https://api.example.com/",
      }),
    ).toEqual({
      apiBaseUrl: "https://api.example.com",
      conversationAiEnabled: false,
      demoSandboxEnabled: false,
    });
  });

  it("rejects a missing API URL", () => {
    expect(() => parsePublicEnvironment({})).toThrow(
      new EnvironmentValidationError("NEXT_PUBLIC_API_BASE_URL is required"),
    );
  });

  it("rejects unsupported URL protocols", () => {
    expect(() =>
      parsePublicEnvironment({ NEXT_PUBLIC_API_BASE_URL: "ftp://example.com" }),
    ).toThrow("NEXT_PUBLIC_API_BASE_URL must use HTTP or HTTPS");
  });

  it("parses the public conversation feature flag", () => {
    expect(
      parsePublicEnvironment({
        NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000",
        NEXT_PUBLIC_CONVERSATION_AI_ENABLED: "true",
      }).conversationAiEnabled,
    ).toBe(true);
  });

  it("rejects an invalid public conversation feature flag", () => {
    expect(() =>
      parsePublicEnvironment({
        NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000",
        NEXT_PUBLIC_CONVERSATION_AI_ENABLED: "yes",
      }),
    ).toThrow("NEXT_PUBLIC_CONVERSATION_AI_ENABLED must be true or false");
  });

  it("does not require phone configuration for browser routes", () => {
    expect(
      parsePublicEnvironment({
        NEXT_PUBLIC_API_BASE_URL: "https://api.example.com",
        NEXT_PUBLIC_DEMO_SANDBOX_ENABLED: "true",
        NEXT_PUBLIC_DEMO_PHONE_NUMBER: "555-0100",
      }).demoSandboxEnabled,
    ).toBe(true);
  });

  it("requires an E.164 number when parsing phone demo configuration", () => {
    expect(() =>
      parseDemoPhoneNumber({
        NEXT_PUBLIC_DEMO_PHONE_NUMBER: "555-0100",
      }),
    ).toThrow("NEXT_PUBLIC_DEMO_PHONE_NUMBER must use E.164 format");
  });

  it("parses the public phone demo configuration", () => {
    expect(
      parseDemoPhoneNumber({
        NEXT_PUBLIC_DEMO_PHONE_NUMBER: "+15550100100",
      }),
    ).toBe("+15550100100");
  });
});
