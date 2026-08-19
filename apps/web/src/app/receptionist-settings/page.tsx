import { notFound } from "next/navigation";

import { ReceptionistSettingsEditor } from "@/features/receptionist/receptionist-settings";
import { parsePublicEnvironment } from "@/lib/environment";

export default function ReceptionistSettingsPage() {
  const environment = parsePublicEnvironment(process.env);
  if (!environment.conversationAiEnabled || environment.demoSandboxEnabled) {
    notFound();
  }
  return <ReceptionistSettingsEditor apiBaseUrl={environment.apiBaseUrl} />;
}
