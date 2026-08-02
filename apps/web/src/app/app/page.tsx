import { redirect } from "next/navigation";

import { getAuthenticatedActor } from "@/lib/authenticated-api";

export default async function ProtectedWorkspace() {
  let actor: Awaited<ReturnType<typeof getAuthenticatedActor>>;
  try {
    actor = await getAuthenticatedActor();
  } catch {
    return (
      <main>
        <p className="eyebrow">Protected workspace</p>
        <h1>Workspace unavailable</h1>
        <p className="summary">
          The authenticated API could not be reached. No customer or voice
          intake data was submitted. Retry after the backend is available.
        </p>
      </main>
    );
  }
  if (!actor) {
    redirect("/");
  }

  return (
    <main>
      <p className="eyebrow">Protected workspace</p>
      <h1>Welcome, {actor.display_name}</h1>
      <p className="summary">
        You are working in {actor.agency_name}. Agency ownership is resolved by
        the API and cannot be selected in the browser.
      </p>
      <section className="foundation-card" aria-labelledby="voice-intake">
        <h2 id="voice-intake">Voice intake foundation</h2>
        <p>
          Customer intake is the next approved workflow. Microphone capture and
          transcription remain unavailable until their separate implementation
          and provider approval.
        </p>
      </section>
    </main>
  );
}
