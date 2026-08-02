import { describe, expect, it } from "vitest";

import {
  EnvironmentValidationError,
  parsePublicEnvironment,
} from "./environment";

describe("parsePublicEnvironment", () => {
  it("returns a normalized API URL", () => {
    expect(
      parsePublicEnvironment({
        NEXT_PUBLIC_API_BASE_URL: "https://api.example.com/",
      }),
    ).toEqual({ apiBaseUrl: "https://api.example.com" });
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
});
