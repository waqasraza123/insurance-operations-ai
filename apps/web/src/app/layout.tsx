import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./styles.css";

export const metadata: Metadata = {
  title: "Insurance Operations AI",
  description: "Release 1 engineering foundation",
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
