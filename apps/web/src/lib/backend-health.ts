import { parsePublicEnvironment } from "@/lib/environment";

type BackendStatus = Readonly<{
  label: string;
  status: "ready" | "unavailable";
}>;

export async function getBackendStatus(): Promise<BackendStatus> {
  const { apiBaseUrl } = parsePublicEnvironment(process.env);

  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(2_000),
    });

    if (!response.ok) {
      return { label: "Unavailable", status: "unavailable" };
    }

    return { label: "Healthy", status: "ready" };
  } catch {
    return { label: "Unavailable", status: "unavailable" };
  }
}
