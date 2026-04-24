import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { ThemeProvider } from "next-themes";
import { AppShell } from "@/components/layout/app-shell";
import "@/globals.css";

export const metadata: Metadata = {
  title: "Orkestra — Governed Multi-Agent Orchestration",
  description: "Control tower for governed multi-agent orchestration",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable}`}
      suppressHydrationWarning
    >
      <body>
        <ThemeProvider
          attribute="data-theme"
          defaultTheme="dark"
          themes={["dark", "light"]}
          storageKey="orkestra-theme"
        >
          <AppShell>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
