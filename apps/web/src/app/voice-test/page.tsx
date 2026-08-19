import Link from "next/link";
import { notFound } from "next/navigation";

import { Brand } from "@/components/brand";
import { VoiceTest } from "@/features/conversation/voice-test";
import { getReceptionistSettings } from "@/features/receptionist/api";
import { parsePublicEnvironment } from "@/lib/environment";

export default async function VoiceTestPage() {
  const environment = parsePublicEnvironment(process.env);
  if (!environment.conversationAiEnabled || environment.demoSandboxEnabled) {
    notFound();
  }
  const receptionistSettings = await loadReceptionistSettings(
    environment.apiBaseUrl,
  );
  if (receptionistSettings === undefined) {
    return (
      <main className="voice-main">
        <nav className="top-nav" aria-label="Primary navigation">
          <Brand />
        </nav>
        <section className="settings-card">
          <p className="eyebrow">Configuration required</p>
          <h1>Receptionist profile unavailable</h1>
          <p className="summary">
            Apply the latest migration and rerun the development seed before
            starting a synthetic conversation.
          </p>
        </section>
      </main>
    );
  }
  return (
    <main className="voice-main">
      <nav className="top-nav" aria-label="Primary navigation">
        <Brand />
        <div className="nav-links">
          <Link className="text-link" href="/receptionist-settings">
            Agency profile
          </Link>
          <Link className="text-link" href="/approved-faqs">
            Approved FAQs
          </Link>
        </div>
      </nav>
      <VoiceTest
        apiBaseUrl={environment.apiBaseUrl}
        receptionistSettings={receptionistSettings}
      />
    </main>
  );
}

async function loadReceptionistSettings(apiBaseUrl: string) {
  try {
    return await getReceptionistSettings(apiBaseUrl);
  } catch {
    return undefined;
  }
}
