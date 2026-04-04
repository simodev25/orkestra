import type { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import "@/globals.css";

export const metadata: Metadata = {
  title: "Orkestra — Governed Multi-Agent Orchestration",
  description: "Control tower for governed multi-agent orchestration",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
