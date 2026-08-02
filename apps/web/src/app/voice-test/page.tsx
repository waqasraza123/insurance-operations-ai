import { notFound } from "next/navigation";

import { VoiceTest } from "@/features/conversation/voice-test";
import { parsePublicEnvironment } from "@/lib/environment";

export default function VoiceTestPage() {
  const environment = parsePublicEnvironment(process.env);
  if (!environment.conversationAiEnabled) {
    notFound();
  }

  return (
    <main className="voice-main">
      <VoiceTest apiBaseUrl={environment.apiBaseUrl} />
    </main>
  );
}
