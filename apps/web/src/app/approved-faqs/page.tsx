import { notFound } from "next/navigation";

import { ApprovedFaqManager } from "@/features/approved-faqs/approved-faq-manager";
import { parsePublicEnvironment } from "@/lib/environment";

export default function ApprovedFaqsPage() {
  const environment = parsePublicEnvironment(process.env);
  if (!environment.conversationAiEnabled) notFound();
  return <ApprovedFaqManager apiBaseUrl={environment.apiBaseUrl} />;
}
