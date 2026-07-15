import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { LanguageProvider } from "@/components/language-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: "MemWeave（忆织）",
  description: "把散落在文字、照片和声音里的碎片，整理成记忆。",
  icons: {
    icon: "/icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        <LanguageProvider>
          <AppShell>{children}</AppShell>
        </LanguageProvider>
      </body>
    </html>
  );
}
