"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot, Wrench, Activity, FlaskConical, Settings, SlidersHorizontal,
  FileText, CheckSquare, Shield, List, BarChart2, Network, Layers, Zap,
} from "lucide-react";

type NavItem =
  | { section: string }
  | { label: string; href: string; icon: React.ElementType };

const NAV: NavItem[] = [
  { label: "Dashboard",      href: "/",                       icon: Activity },
  { section: "Registries" },
  { label: "Agents",         href: "/agents",                 icon: Bot },
  { label: "Orchestrateurs", href: "/agents/orchestrators/new", icon: Network },
  { label: "Families",       href: "/agents/families",        icon: Layers },
  { label: "Agent Skills",   href: "/agents/skills",          icon: Zap },
  { label: "Test Lab",       href: "/test-lab",               icon: FlaskConical },
  { label: "MCP Catalog",    href: "/mcps",                   icon: Wrench },
  { section: "Monitoring" },
  { label: "Runs",           href: "/runs",                   icon: BarChart2 },
  { label: "Requests",       href: "/requests",               icon: List },
  { label: "Approvals",      href: "/approvals",              icon: CheckSquare },
  { label: "Audit",          href: "/audit",                  icon: FileText },
  { label: "Control",        href: "/control",                icon: Shield },
  { section: "Configuration" },
  { label: "Admin",          href: "/admin",                  icon: Settings },
  { label: "Lab Config",     href: "/test-lab/config",        icon: SlidersHorizontal },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__logo">O</div>
        <div>
          <p className="sidebar__title">Orkestra</p>
          <p className="sidebar__subtitle">Orchestration</p>
        </div>
      </div>

      <nav className="sidebar__nav">
        {NAV.map((item, i) => {
          if ("section" in item) {
            return (
              <p key={i} className="sidebar__section">{item.section}</p>
            );
          }
          const Icon = item.icon;
          const active =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.label}
              href={item.href}
              className={`navlink${active ? " navlink--active" : ""}`}
            >
              <Icon size={14} strokeWidth={1.5} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="sidebar__foot">v0.9.4</div>
    </aside>
  );
}
