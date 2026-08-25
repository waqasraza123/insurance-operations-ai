import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PhoneDemoBoard } from "@/features/phone-demo/phone-demo-board";
import {
  parseDemoPhoneNumber,
  parsePublicEnvironment,
} from "@/lib/environment";

export const metadata: Metadata = {
  title: "Phone Agent Demo | Insurance Operations AI",
  description: "A fictional-data demonstration of an AI insurance front desk.",
  robots: { index: false, follow: false },
};

export default function PhoneDemoPage() {
  const environment = parsePublicEnvironment(process.env);
  if (!environment.demoSandboxEnabled) {
    notFound();
  }
  const phoneNumber = parseDemoPhoneNumber(process.env);
  return (
    <PhoneDemoBoard
      apiBaseUrl={environment.apiBaseUrl}
      phoneNumber={phoneNumber}
    />
  );
}
