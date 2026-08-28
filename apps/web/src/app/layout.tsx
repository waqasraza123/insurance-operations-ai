import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./styles.css";

export const metadata: Metadata = {
  title: "CoverOps — Insurance Voice AI SaaS Starter Kit",
  description:
    "A Next.js and FastAPI starter for guarded browser and phone Voice AI, approved FAQs, confirmed lead intake, and human handoff.",
};

type RootLayoutProperties = Readonly<{
  children: ReactNode;
}>;

export default function RootLayout({ children }: RootLayoutProperties) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
