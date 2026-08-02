import { cookies } from "next/headers";

import { parsePublicEnvironment } from "@/lib/environment";

const defaultAccessTokenCookieName = "insurance_operations_access_token";

export type AuthenticatedActor = Readonly<{
  app_user_id: string;
  display_name: string;
  agency_id: string;
  agency_name: string;
  agency_environment: string;
}>;

export async function getAuthenticatedActor(): Promise<AuthenticatedActor | null> {
  const cookieName =
    process.env.AUTH_ACCESS_TOKEN_COOKIE_NAME?.trim() ||
    defaultAccessTokenCookieName;
  const accessToken = (await cookies()).get(cookieName)?.value;
  if (!accessToken) {
    return null;
  }

  const { apiBaseUrl } = parsePublicEnvironment(process.env);
  const response = await fetch(`${apiBaseUrl}/api/v1/me`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${accessToken}` },
    signal: AbortSignal.timeout(5_000),
  });
  if (response.status === 401 || response.status === 403) {
    return null;
  }
  if (!response.ok) {
    throw new Error("The protected API is unavailable");
  }
  return (await response.json()) as AuthenticatedActor;
}
