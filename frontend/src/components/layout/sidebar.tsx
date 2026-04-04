"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Inbox, FolderOpen, GitBranch, Play, Bot, Wrench,
  Shield, Eye, CheckCircle, FileSearch, Workflow, Settings, Activity,
} from "lucide-react";

const NAV = [
  { label: "Dashboard", href: "/", icon: Activity },
  { section: "Operations" },
  { label: "Requests", href: "/requests", icon: Inbox },
  { label: "Cases", href: "/cases", icon: FolderOpen },
  { label: "Plans", href: "/plans", icon: GitBranch },
  { label: "Runs", href: "/runs", icon: Play },
  { section: "Registries" },
  { label: "Agents", href: "/agents", icon: Bot },
  { label: "MCPs", href: "/mcps", icon: Wrench },
  { section: "Governance" },
  { label: "Control", href: "/control", icon: Shield },
  { label: "Supervision", href: "/runs", icon: Eye },
  { label: "Approvals", href: "/approvals", icon: CheckCircle },
  { label: "Audit", href: "/audit", icon: FileSearch },
  { section: "Configuration" },
  { label: "Workflows", href: "/workflows", icon: Workflow },
  { label: "Admin", href: "/admin", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 bg-ork-surface border-r border-ork-border flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-ork-border">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded bg-ork-cyan/20 flex items-center justify-center">
            <span className="text-ork-cyan font-mono font-bold text-sm">O</span>
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-wide">ORKESTRA</h1>
            <p className="text-[9px] font-mono text-ork-dim tracking-[0.15em]">ORCHESTRATION</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-3">
        {NAV.map((item, i) => {
          if ("section" in item) {
            return (
              <p key={i} className="section-title px-2 pt-4 pb-1.5">
                {item.section}
              </p>
            );
          }
          const Icon = item.icon;
          const active = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href!));
          return (
            <Link
              key={item.href}
              href={item.href!}
              className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded text-[13px] mb-0.5 transition-colors duration-150 ${
                active
                  ? "bg-ork-cyan/10 text-ork-cyan"
                  : "text-ork-muted hover:text-ork-text hover:bg-ork-hover"
              }`}
            >
              <Icon size={15} strokeWidth={active ? 2 : 1.5} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Version */}
      <div className="px-5 py-3 border-t border-ork-border">
        <p className="text-[9px] font-mono text-ork-dim">v0.1.0 — Phase 1</p>
      </div>
    </aside>
  );
}
