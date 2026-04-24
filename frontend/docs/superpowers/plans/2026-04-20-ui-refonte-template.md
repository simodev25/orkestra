# UI Refonte — Fidélité 100% Orkestra-Mesh-template — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer entièrement la couche visuelle du projet Orkestra (Next.js 15) par le design system du template de référence Orkestra-Mesh-template — fidélité pixel-perfect, logique métier intacte.

**Architecture:** Migration complète vers CSS natif avec custom properties OKLCH, Geist + Geist Mono comme polices, désactivation du preflight Tailwind. Tailwind conservé pour les utilities layout. Chaque composant TSX adopte les classes CSS du template (`.btn`, `.badge`, `.tablewrap`, `.kv`, `.navlink`, etc.).

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS 3.4 (utilities seules), CSS natif custom properties OKLCH, package `geist` (Vercel)

**Working directory:** `frontend/` (toutes les commandes sont à exécuter depuis `frontend/`)

---

## Fichiers créés / modifiés

| Action | Fichier |
|--------|---------|
| Modify | `src/globals.css` |
| Modify | `tailwind.config.ts` |
| Modify | `src/app/layout.tsx` |
| Modify | `src/components/layout/app-shell.tsx` |
| **Create** | `src/components/layout/topbar.tsx` |
| Modify | `src/components/layout/sidebar.tsx` |
| Modify | `src/components/ui/status-badge.tsx` |
| Modify | `src/components/ui/stat-card.tsx` |
| Modify | `src/app/page.tsx` |
| Modify | `src/app/agents/page.tsx` |
| Modify | `src/app/agents/[id]/page.tsx` |
| Modify | `src/app/agents/new/page.tsx` |
| Modify | `src/app/agents/[id]/edit/page.tsx` |
| Modify | `src/components/agents/agent-form.tsx` |
| Modify | `src/components/agents/lifecycle/AgentLifecyclePanel.tsx` |
| Modify | `src/components/agents/lifecycle/PromotionPath.tsx` |
| Modify | `src/components/agents/lifecycle/TransitionGate.tsx` |
| Modify | `src/components/agents/lifecycle/OperationalStates.tsx` |
| Modify | `src/app/test-lab/page.tsx` |
| Modify | `src/app/mcps/page.tsx` |
| Modify | `src/app/runs/page.tsx` |
| Modify | `src/app/audit/page.tsx` |
| Modify | `src/app/approvals/page.tsx` |
| Modify | `src/components/test-lab/run-graph/RunTopbar.tsx` |
| Modify | `src/components/test-lab/run-graph/DetailPanel.tsx` |

---

## Task 1 : Foundation — Fonts Geist + tailwind.config.ts

**Files:**
- Modify: `package.json` (install geist)
- Modify: `tailwind.config.ts`
- Modify: `src/app/layout.tsx`

- [ ] **Step 1.1 — Installer le package geist**

```bash
npm install geist
```

Expected: geist ajouté dans node_modules et package.json.

- [ ] **Step 1.2 — Mettre à jour tailwind.config.ts**

Remplacer entièrement le contenu de `tailwind.config.ts` :

```typescript
import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  corePlugins: {
    preflight: false, // Désactivé — le reset vient de globals.css
  },
  theme: {
    extend: {
      animation: {
        "fade-in": "fadeIn 0.2s ease-out",
        "slide-up": "slideUp 0.2s ease-out",
        "pulse-slow": "pulseSlow 3s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 1.3 — Mettre à jour src/app/layout.tsx**

```tsx
import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
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
    >
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
```

- [ ] **Step 1.4 — Vérifier TypeScript**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs TypeScript.

- [ ] **Step 1.5 — Commit**

```bash
git add tailwind.config.ts src/app/layout.tsx package.json package-lock.json
git commit -m "feat(ui): install geist fonts, disable tailwind preflight"
```

---

## Task 2 : Foundation — globals.css (remplacement total)

**Files:**
- Modify: `src/globals.css`

- [ ] **Step 2.1 — Remplacer globals.css entièrement**

Remplacer le contenu entier de `src/globals.css` :

```css
/* Tailwind components + utilities (preflight désactivé dans tailwind.config) */
@tailwind components;
@tailwind utilities;

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ORKESTRA DESIGN SYSTEM — port fidèle de Orkestra-Mesh-template
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

:root {
  --ork-bg:       oklch(0.16 0.004 80);
  --ork-surface:  oklch(0.185 0.004 80);
  --ork-panel:    oklch(0.21 0.005 80);
  --ork-panel-2:  oklch(0.24 0.005 80);
  --ork-hover:    oklch(0.225 0.005 80);

  --ork-border:   oklch(0.28 0.006 80);
  --ork-border-2: oklch(0.33 0.007 80);
  --ork-dim:      oklch(0.48 0.006 85);

  --ork-text:     oklch(0.96 0.004 85);
  --ork-text-1:   oklch(0.82 0.005 85);
  --ork-muted:    oklch(0.62 0.006 85);
  --ork-muted-2:  oklch(0.48 0.006 85);

  --ork-green:     oklch(0.78 0.17 145);
  --ork-green-dim: oklch(0.52 0.12 145);
  --ork-green-bg:  oklch(0.26 0.07 145);

  --ork-cyan:     oklch(0.78 0.13 200);
  --ork-cyan-bg:  oklch(0.26 0.06 200);

  --ork-amber:    oklch(0.82 0.15 75);
  --ork-amber-bg: oklch(0.28 0.07 75);

  --ork-red:      oklch(0.70 0.19 25);
  --ork-red-bg:   oklch(0.26 0.08 25);

  --ork-purple:    oklch(0.72 0.12 305);
  --ork-purple-bg: oklch(0.26 0.06 305);

  --accent: var(--ork-green);
  --radius: 3px;
  --radius-lg: 6px;
  --font-sans: var(--font-geist-sans), "Inter Tight", system-ui, sans-serif;
  --font-mono: var(--font-geist-mono), "JetBrains Mono", ui-monospace, monospace;
}

/* ── Reset & base ─────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
html { background: var(--ork-bg); }
body {
  background: var(--ork-bg);
  color: var(--ork-text);
  font-family: var(--font-sans);
  font-feature-settings: "cv11", "ss01", "ss03";
  font-size: 13px;
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
button { font: inherit; color: inherit; background: none; border: 0; cursor: pointer; padding: 0; }
input, select, textarea { font: inherit; color: inherit; }
a { color: inherit; text-decoration: none; }
code, .mono { font-family: var(--font-mono); font-feature-settings: normal; }

/* ── Scrollbar ────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--ork-border); border-radius: 10px; border: 2px solid var(--ork-bg); }
::-webkit-scrollbar-thumb:hover { background: var(--ork-border-2); }

/* ── Keyframe animations ──────────────────────────────────────── */
@keyframes fadeIn    { from { opacity: 0 } to { opacity: 1 } }
@keyframes slideUp   { from { opacity: 0; transform: translateY(2px) } to { opacity: 1; transform: none } }
@keyframes pulseSlow { 0%,100% { opacity: 1 } 50% { opacity: .55 } }
@keyframes dotBlink  { 0%,100% { opacity: 1 } 50% { opacity: .2 } }
@keyframes caret     { 0%,50% { opacity: 1 } 51%,100% { opacity: 0 } }
@keyframes ringPulse { 0% { transform: scale(0.7); opacity: 0.8; } 100% { transform: scale(1.6); opacity: 0; } }
/* RunGraph specific */
@keyframes edgeDash      { to { stroke-dashoffset: -26; } }
@keyframes nodeRingPulse { 0%,100% { opacity: 0.4; transform: scale(1); } 50% { opacity: 1; transform: scale(1.015); } }
@keyframes verdictPulse  { 0%,100% { opacity: 1; box-shadow: 0 0 0 0 currentColor; } 50% { opacity: 0.6; box-shadow: 0 0 0 4px transparent; } }

.animate-fade-in    { animation: fadeIn .2s ease-out; }
.animate-slide-up   { animation: slideUp .2s ease-out; }
.animate-pulse-slow { animation: pulseSlow 3s ease-in-out infinite; }

/* ── Utility bits ─────────────────────────────────────────────── */
.glass-panel       { background: var(--ork-surface); border: 1px solid var(--ork-border); border-radius: var(--radius-lg); }
.glass-panel-hover:hover { border-color: var(--ork-border-2); }
.section-title { font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ork-muted-2); font-weight: 500; }
.data-label    { font-family: var(--font-mono); font-size: 11px; color: var(--ork-muted-2); }
.stat-value    { font-family: var(--font-mono); font-weight: 400; font-size: 22px; letter-spacing: -0.01em; color: var(--ork-text); }
.glow-dot      { width: 6px; height: 6px; border-radius: 999px; background: currentColor; box-shadow: 0 0 0 3px color-mix(in oklch, currentColor 20%, transparent); }
.glow-cyan     { box-shadow: 0 0 20px color-mix(in oklch, var(--ork-cyan) 15%, transparent); }
.row           { display: flex; align-items: center; gap: 8px; }
.col           { display: flex; flex-direction: column; gap: 8px; }
.muted         { color: var(--ork-muted); }
.dim           { color: var(--ork-muted-2); }
.text          { color: var(--ork-text); }
.cyan          { color: var(--accent); }
.right         { margin-left: auto; }
.flex-wrap     { flex-wrap: wrap; }
.hidden        { display: none; }
.sep           { height: 1px; background: var(--ork-border); margin: 14px 0; }
:focus-visible { outline: 1.5px solid var(--accent); outline-offset: 1px; border-radius: 2px; }

/* ── App shell ────────────────────────────────────────────────── */
.app { display: grid; grid-template-columns: 224px 1fr; min-height: 100vh; }

/* ── Sidebar ──────────────────────────────────────────────────── */
.sidebar { width: 224px; background: var(--ork-bg); border-right: 1px solid var(--ork-border); display: flex; flex-direction: column; height: 100vh; position: sticky; top: 0; }
.sidebar__brand { padding: 14px 14px 12px; border-bottom: 1px solid var(--ork-border); display: flex; align-items: center; gap: 10px; }
.sidebar__logo { width: 22px; height: 22px; border-radius: 3px; background: color-mix(in oklch, var(--accent) 18%, transparent); display: grid; place-items: center; color: var(--accent); font-family: var(--font-mono); font-weight: 600; font-size: 11px; flex-shrink: 0; }
.sidebar__title { font-family: var(--font-mono); font-size: 12px; color: var(--ork-text); font-weight: 500; margin: 0; }
.sidebar__subtitle { margin: 0; font-family: var(--font-mono); font-size: 9.5px; letter-spacing: 0.08em; color: var(--ork-muted-2); text-transform: uppercase; }
.sidebar__nav { flex: 1; overflow-y: auto; padding: 10px 10px 16px; }
.sidebar__section { padding: 14px 8px 6px; font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ork-muted-2); font-weight: 500; }
.sidebar__foot { padding: 10px 14px; border-top: 1px solid var(--ork-border); font-family: var(--font-mono); font-size: 10px; color: var(--ork-muted-2); display: flex; align-items: center; gap: 8px; }
.sidebar__foot::before { content: ""; width: 6px; height: 6px; border-radius: 999px; background: var(--accent); box-shadow: 0 0 0 3px color-mix(in oklch, var(--accent) 20%, transparent); }

.navlink { display: flex; align-items: center; gap: 9px; padding: 6px 8px; margin-bottom: 1px; border-radius: 3px; font-size: 12.5px; color: var(--ork-text-1); cursor: pointer; transition: background .12s, color .12s; position: relative; white-space: nowrap; height: 28px; }
.navlink > svg { width: 14px; height: 14px; color: var(--ork-muted); flex-shrink: 0; }
.navlink:hover { background: var(--ork-surface); color: var(--ork-text); }
.navlink:hover > svg { color: var(--ork-text-1); }
.navlink--active { background: var(--ork-panel); color: var(--ork-text); }
.navlink--active > svg { color: var(--ork-text); }
.navlink--active::before { content: ""; position: absolute; left: -10px; top: 7px; width: 2px; height: 14px; background: var(--accent); border-radius: 1px; }
.navlink__badge { margin-left: auto; font-family: var(--font-mono); font-size: 10px; color: var(--ork-muted-2); }

/* ── Topbar ──────────────────────────────────────────────────── */
.main { min-height: 100vh; overflow: hidden; }
.topbar { display: flex; align-items: center; justify-content: space-between; padding: 0 16px; height: 44px; border-bottom: 1px solid var(--ork-border); background: var(--ork-bg); position: sticky; top: 0; z-index: 5; }
.topbar__crumbs { display: flex; align-items: center; gap: 6px; font-family: var(--font-mono); font-size: 12px; color: var(--ork-muted); }
.topbar__crumbs strong { color: var(--ork-text); font-weight: 500; }
.topbar__right { display: flex; align-items: center; gap: 8px; }
.topbar__btn { display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 10px; border: 1px solid var(--ork-border); border-radius: var(--radius); background: var(--ork-surface); font-family: var(--font-mono); font-size: 11px; color: var(--ork-text-1); }
.topbar__btn:hover { background: var(--ork-panel); border-color: var(--ork-border-2); color: var(--ork-text); }
.topbar__health { display: inline-flex; align-items: center; gap: 7px; font-family: var(--font-mono); font-size: 11px; color: var(--ork-text-1); padding: 0 10px; height: 28px; border: 1px solid var(--ork-border); border-radius: 999px; background: var(--ork-surface); }
.topbar__health .glow-dot { color: var(--ork-green); animation: pulseSlow 2.4s infinite; }

/* ── Page ─────────────────────────────────────────────────────── */
.page { padding: 18px 20px 32px; max-width: 1600px; margin: 0 auto; }
.pagehead { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; }
.pagehead h1 { margin: 0 0 4px; font-size: 17px; font-weight: 500; letter-spacing: -0.01em; color: var(--ork-text); }
.pagehead p { margin: 0; font-size: 12.5px; color: var(--ork-text-1); max-width: 72ch; line-height: 1.5; }
.pagehead__actions { display: flex; gap: 6px; flex-wrap: wrap; }

/* ── Buttons ──────────────────────────────────────────────────── */
.btn { display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 10px; font-family: var(--font-sans); font-size: 12px; border: 1px solid var(--ork-border); border-radius: var(--radius); background: var(--ork-surface); color: var(--ork-text); transition: background .12s, border-color .12s, color .12s; white-space: nowrap; }
.btn:hover { background: var(--ork-panel); border-color: var(--ork-border-2); }
.btn > svg { width: 13px; height: 13px; }
.btn--cyan { background: var(--accent); color: oklch(0.15 0.03 145); border-color: var(--accent); font-weight: 500; }
.btn--cyan:hover { background: oklch(0.82 0.17 145); color: oklch(0.12 0.03 145); border-color: oklch(0.82 0.17 145); }
.btn--purple { color: var(--ork-purple); background: var(--ork-purple-bg); border-color: color-mix(in oklch, var(--ork-purple) 30%, transparent); }
.btn--purple:hover { border-color: color-mix(in oklch, var(--ork-purple) 50%, transparent); }
.btn--red { color: var(--ork-red); background: var(--ork-red-bg); border-color: color-mix(in oklch, var(--ork-red) 30%, transparent); }
.btn--ghost { background: transparent; border-color: transparent; color: var(--ork-text-1); }
.btn--ghost:hover { background: var(--ork-panel); border-color: var(--ork-border); color: var(--ork-text); }

/* ── Stat cards ──────────────────────────────────────────────── */
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px; }
.stat { background: var(--ork-bg); border: 1px solid var(--ork-border); border-radius: var(--radius-lg); padding: 12px 14px; position: relative; overflow: hidden; }
.stat__label { font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ork-muted-2); margin-bottom: 8px; font-weight: 500; }
.stat__value { font-family: var(--font-mono); font-size: 22px; letter-spacing: -0.01em; }
.stat__delta { font-family: var(--font-mono); font-size: 10.5px; color: var(--ork-muted); }
.stat__bar { height: 2px; margin-top: 10px; background: var(--ork-border); border-radius: 999px; overflow: hidden; }
.stat__bar > span { display: block; height: 100%; background: currentColor; border-radius: 999px; }
.stat--green  { color: var(--ork-green); }
.stat--green  .stat__value { color: var(--ork-green); }
.stat--cyan   { color: var(--ork-cyan); }
.stat--cyan   .stat__value { color: var(--ork-cyan); }
.stat--amber  { color: var(--ork-amber); }
.stat--amber  .stat__value { color: var(--ork-amber); }
.stat--purple { color: var(--ork-purple); }
.stat--purple .stat__value { color: var(--ork-purple); }

/* ── Filters ──────────────────────────────────────────────────── */
.filters { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr auto; gap: 8px; padding: 10px 12px; margin-bottom: 12px; background: var(--ork-bg); border: 1px solid var(--ork-border); border-radius: var(--radius-lg); }

/* ── Form fields ──────────────────────────────────────────────── */
.field { background: var(--ork-surface); border: 1px solid var(--ork-border); border-radius: var(--radius); padding: 0 10px; height: 28px; font-family: var(--font-mono); font-size: 11.5px; color: var(--ork-text); outline: none; transition: border-color .12s, background .12s; }
.field::placeholder { color: var(--ork-muted-2); }
.field:focus { border-color: var(--ork-border-2); background: var(--ork-panel); }
select.field { appearance: none; background-image: linear-gradient(45deg, transparent 50%, var(--ork-muted) 50%), linear-gradient(135deg, var(--ork-muted) 50%, transparent 50%); background-position: calc(100% - 14px) 50%, calc(100% - 10px) 50%; background-size: 4px 4px, 4px 4px; background-repeat: no-repeat; padding-right: 28px; }
textarea.field { height: auto; padding: 8px 10px; resize: vertical; }
.fieldwrap { position: relative; display: flex; align-items: center; }
.fieldwrap svg { position: absolute; left: 9px; width: 13px; height: 13px; color: var(--ork-muted-2); pointer-events: none; }
.fieldwrap .field { padding-left: 30px; width: 100%; }
.field-label { font-family: var(--font-mono); font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ork-muted-2); margin-bottom: 4px; display: block; }
.field-group { display: flex; flex-direction: column; gap: 0; }

/* ── Table ────────────────────────────────────────────────────── */
.tablewrap { overflow: hidden; background: var(--ork-bg); border: 1px solid var(--ork-border); border-radius: var(--radius-lg); }
.table { width: 100%; border-collapse: separate; border-spacing: 0; font-family: var(--font-sans); font-size: 12.5px; }
.table thead th { text-align: left; font-weight: 500; color: var(--ork-muted-2); background: var(--ork-bg); padding: 0 12px; height: 28px; border-bottom: 1px solid var(--ork-border); font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 0.06em; text-transform: uppercase; position: sticky; top: 0; z-index: 1; }
.table tbody td { padding: 0 12px; height: 40px; vertical-align: middle; border-bottom: 1px solid var(--ork-border); color: var(--ork-text-1); }
.table tbody tr:last-child td { border-bottom: none; }
.table tbody tr { cursor: pointer; transition: background .1s; }
.table tbody tr:hover { background: var(--ork-surface); }
.table tbody tr.is-selected { background: var(--ork-panel); }
.table tbody tr.is-selected td:first-child { box-shadow: inset 2px 0 0 var(--accent); }
.table td.col-name { color: var(--ork-text); font-weight: 500; font-size: 12.5px; white-space: nowrap; }
.table td.col-id { color: var(--accent); font-family: var(--font-mono); font-size: 11px; }
.table td.col-fam { color: var(--ork-text-1); font-family: var(--font-mono); font-size: 11.5px; }
.table .sub { display: block; color: var(--ork-muted-2); font-family: var(--font-mono); font-size: 10.5px; margin-top: 1px; }

/* ── Chips & badges ───────────────────────────────────────────── */
.chip { display: inline-flex; align-items: center; gap: 5px; height: 20px; padding: 0 7px; border: 1px solid var(--ork-border); border-radius: var(--radius); font-size: 10.5px; color: var(--ork-text-1); font-family: var(--font-mono); background: var(--ork-surface); }
.chip--mini { height: 18px; padding: 0 6px; font-size: 10px; }
.badge { display: inline-flex; align-items: center; gap: 5px; height: 20px; padding: 0 7px; border: 1px solid transparent; border-radius: var(--radius); font-family: var(--font-mono); font-size: 10.5px; letter-spacing: 0.02em; text-transform: lowercase; white-space: nowrap; }
.badge::before { content: ""; width: 5px; height: 5px; border-radius: 999px; background: currentColor; flex-shrink: 0; }
.badge--draft      { color: var(--ork-muted);   background: var(--ork-panel);      border-color: var(--ork-border); }
.badge--designed   { color: var(--ork-purple);  background: var(--ork-purple-bg);  border-color: color-mix(in oklch, var(--ork-purple) 25%, transparent); }
.badge--tested     { color: var(--ork-cyan);    background: var(--ork-cyan-bg);    border-color: color-mix(in oklch, var(--ork-cyan) 25%, transparent); }
.badge--registered { color: var(--ork-cyan);    background: var(--ork-cyan-bg);    border-color: color-mix(in oklch, var(--ork-cyan) 25%, transparent); }
.badge--active     { color: var(--ork-green);   background: var(--ork-green-bg);   border-color: color-mix(in oklch, var(--ork-green) 25%, transparent); }
.badge--deprecated { color: var(--ork-amber);   background: var(--ork-amber-bg);   border-color: color-mix(in oklch, var(--ork-amber) 25%, transparent); }
.badge--disabled   { color: var(--ork-red);     background: var(--ork-red-bg);     border-color: color-mix(in oklch, var(--ork-red) 25%, transparent); }
.badge--archived   { color: var(--ork-muted-2); background: var(--ork-panel);      border-color: var(--ork-border); }
.badge--passed     { color: var(--ork-green);   background: var(--ork-green-bg);   border-color: color-mix(in oklch, var(--ork-green) 25%, transparent); }
.badge--failed     { color: var(--ork-red);     background: var(--ork-red-bg);     border-color: color-mix(in oklch, var(--ork-red) 25%, transparent); }
.badge--not_tested { color: var(--ork-muted);   background: var(--ork-panel);      border-color: var(--ork-border); }
.badge--passed_with_warnings { color: var(--ork-amber); background: var(--ork-amber-bg); border-color: color-mix(in oklch, var(--ork-amber) 25%, transparent); }
.badge--running    { color: var(--ork-cyan);    background: var(--ork-cyan-bg);    border-color: color-mix(in oklch, var(--ork-cyan) 25%, transparent); animation: pulseSlow 1.5s ease-in-out infinite; }
.badge--completed  { color: var(--ork-green);   background: var(--ork-green-bg);   border-color: color-mix(in oklch, var(--ork-green) 25%, transparent); }
.badge--pending    { color: var(--ork-amber);   background: var(--ork-amber-bg);   border-color: color-mix(in oklch, var(--ork-amber) 25%, transparent); }
.badge--blocked    { color: var(--ork-red);     background: var(--ork-red-bg);     border-color: color-mix(in oklch, var(--ork-red) 25%, transparent); }
.badge--cancelled  { color: var(--ork-muted);   background: var(--ork-panel);      border-color: var(--ork-border); }
.badge--planned    { color: var(--ork-purple);  background: var(--ork-purple-bg);  border-color: color-mix(in oklch, var(--ork-purple) 25%, transparent); }
.badge--allow      { color: var(--ork-green);   background: var(--ork-green-bg);   border-color: color-mix(in oklch, var(--ork-green) 25%, transparent); }
.badge--deny       { color: var(--ork-red);     background: var(--ork-red-bg);     border-color: color-mix(in oklch, var(--ork-red) 25%, transparent); }
.badge--approved   { color: var(--ork-green);   background: var(--ork-green-bg);   border-color: color-mix(in oklch, var(--ork-green) 25%, transparent); }
.badge--rejected   { color: var(--ork-red);     background: var(--ork-red-bg);     border-color: color-mix(in oklch, var(--ork-red) 25%, transparent); }
.badge--warning    { color: var(--ork-amber);   background: var(--ork-amber-bg);   border-color: color-mix(in oklch, var(--ork-amber) 25%, transparent); }
.badge--healthy    { color: var(--ork-green);   background: var(--ork-green-bg);   border-color: color-mix(in oklch, var(--ork-green) 25%, transparent); }
.badge--degraded   { color: var(--ork-amber);   background: var(--ork-amber-bg);   border-color: color-mix(in oklch, var(--ork-amber) 25%, transparent); }

/* criticality */
.crit { display: inline-block; font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.04em; text-transform: lowercase; padding: 1px 6px; border-radius: var(--radius); border: 1px solid transparent; }
.crit--low      { color: var(--ork-muted);  background: var(--ork-panel);      border-color: var(--ork-border); }
.crit--medium   { color: var(--ork-cyan);   background: var(--ork-cyan-bg);    border-color: color-mix(in oklch, var(--ork-cyan) 20%, transparent); }
.crit--high     { color: var(--ork-amber);  background: var(--ork-amber-bg);   border-color: color-mix(in oklch, var(--ork-amber) 20%, transparent); }
.crit--critical { color: var(--ork-red);    background: var(--ork-red-bg);     border-color: color-mix(in oklch, var(--ork-red) 20%, transparent); }

/* ── Split view ───────────────────────────────────────────────── */
.split { display: grid; grid-template-columns: minmax(0, 1fr) 540px; gap: 12px; align-items: start; }

/* ── Detail panel ─────────────────────────────────────────────── */
.detail { background: var(--ork-bg); border: 1px solid var(--ork-border); border-radius: var(--radius-lg); position: sticky; top: 56px; max-height: calc(100vh - 80px); overflow-y: auto; }
.detail__head { padding: 16px 18px 14px; border-bottom: 1px solid var(--ork-border); }
.detail__idrow { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; flex-wrap: wrap; }
.detail__id { font-family: var(--font-mono); font-size: 11px; color: var(--ork-muted); }
.detail__name { font-size: 17px; font-weight: 500; margin: 2px 0 4px; letter-spacing: -0.01em; color: var(--ork-text); }
.detail__purpose { font-size: 13px; color: var(--ork-text-1); margin: 6px 0 0; max-width: 80ch; line-height: 1.5; }
.detail__meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.detail__empty { display: grid; place-items: center; min-height: 200px; font-family: var(--font-mono); font-size: 11.5px; color: var(--ork-muted-2); text-align: center; }

/* ── Tabs ─────────────────────────────────────────────────────── */
.tabs { display: flex; align-items: center; border-bottom: 1px solid var(--ork-border); padding: 0 10px; gap: 2px; overflow-x: auto; scrollbar-width: none; }
.tabs::-webkit-scrollbar { display: none; }
.tabs__btn { position: relative; display: inline-flex; align-items: center; gap: 6px; height: 36px; padding: 0 12px; border-bottom: 2px solid transparent; font-family: var(--font-sans); font-size: 12.5px; color: var(--ork-muted); transition: color .12s; white-space: nowrap; }
.tabs__btn:hover { color: var(--ork-text); }
.tabs__btn--active { color: var(--ork-text); }
.tabs__btn--active::after { content: ""; position: absolute; left: 10px; right: 10px; bottom: -1px; height: 2px; background: var(--accent); border-radius: 1px 1px 0 0; }
.tabs__btn .count { font-family: var(--font-mono); font-size: 10px; color: var(--ork-muted-2); padding: 1px 5px; background: var(--ork-panel); border-radius: var(--radius); }
.tabpane { padding: 16px 18px 40px; }

/* ── KV display ───────────────────────────────────────────────── */
.kv { display: grid; grid-template-columns: 140px 1fr; gap: 0; font-size: 12.5px; align-items: start; }
.kv .k { font-family: var(--font-mono); font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ork-muted-2); padding: 8px 0; border-bottom: 1px dashed var(--ork-border); }
.kv .v { color: var(--ork-text); word-break: break-word; padding: 8px 0; border-bottom: 1px dashed var(--ork-border); }
.kv > .k:last-of-type, .kv > .v:last-of-type { border-bottom: none; }
.kv .v.mono { font-family: var(--font-mono); font-size: 12px; color: var(--ork-text-1); }
.kv .v.cyan { color: var(--accent); font-family: var(--font-mono); font-size: 12px; }

/* ── Block (section dans detail pane) ────────────────────────── */
.block { padding: 16px 0; border-top: 1px solid var(--ork-border); }
.block:first-child { border-top: 0; padding-top: 0; }
.block__title { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.block__title .section-title { margin: 0; }

/* ── Lifecycle / Promotion path ───────────────────────────────── */
.promotion { padding: 16px 6px 6px; background: radial-gradient(circle at 20% 0%, oklch(0.23 0.02 145) 0%, transparent 40%), radial-gradient(circle at 80% 100%, oklch(0.22 0.02 75) 0%, transparent 50%), var(--ork-surface); border: 1px solid var(--ork-border); border-radius: var(--radius-lg); }
.promotion__head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; padding: 0 8px; }
.promopath { display: flex; align-items: flex-start; position: relative; padding: 0 4px; }
.promopath__step { flex: 0 0 auto; display: flex; flex-direction: column; align-items: center; gap: 8px; min-width: 70px; }
.promopath__dot { width: 14px; height: 14px; border-radius: 999px; display: grid; place-items: center; font-size: 10px; position: relative; background: var(--ork-panel); border: 1.5px solid var(--ork-border-2); z-index: 1; transition: all .2s; }
.promopath__dot--done { background: var(--accent); border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in oklch, var(--accent) 18%, transparent); }
.promopath__dot--done > * { display: none; }
.promopath__dot--done::before { content: ""; position: absolute; inset: 3px; background: oklch(0.15 0.03 145); clip-path: polygon(20% 50%, 40% 70%, 80% 25%, 70% 18%, 40% 55%, 30% 42%); }
.promopath__dot--current { background: var(--ork-bg); border: 2.5px solid var(--accent); box-shadow: 0 0 0 4px color-mix(in oklch, var(--accent) 22%, transparent); }
.promopath__dot--current::after { content: ""; position: absolute; inset: -9px; border-radius: 999px; border: 1px solid color-mix(in oklch, var(--accent) 40%, transparent); animation: ringPulse 2.4s ease-out infinite; }
.promopath__dot--locked { background: var(--ork-panel); border-color: var(--ork-border); color: var(--ork-muted-2); }
.promopath__label { font-family: var(--font-mono); font-size: 10.5px; text-transform: lowercase; color: var(--ork-muted); text-align: center; }
.promopath__label--done    { color: var(--ork-text-1); }
.promopath__label--current { color: var(--ork-text); font-weight: 500; }
.promopath__label--locked  { color: var(--ork-muted-2); }
.promopath__connector { flex: 1 1 auto; display: flex; flex-direction: column; align-items: center; padding-top: 6px; min-width: 0; }
.promopath__line { height: 1.5px; width: 100%; background: var(--ork-border-2); border-radius: 999px; }
.promopath__line--done { background: var(--accent); }
.promopath__gate { font-family: var(--font-mono); font-size: 9.5px; color: var(--ork-muted-2); margin-top: 6px; text-align: center; line-height: 1.3; }

/* ── Gate / blockers ──────────────────────────────────────────── */
.gate { margin-top: 14px; border: 1px solid var(--ork-border); border-radius: var(--radius-lg); padding: 12px 14px; background: var(--ork-surface); }
.gate__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 6px; }
.gate__title { font-size: 13px; font-weight: 500; margin: 0; color: var(--ork-text); }
.gate__flow { font-family: var(--font-mono); font-size: 10.5px; color: var(--ork-muted); display: flex; align-items: center; gap: 6px; }
.gate__flow .to { color: var(--accent); }
.gate__desc { font-size: 12px; color: var(--ork-text-1); margin: 6px 0 10px; line-height: 1.5; }
.gate__blockers { display: flex; flex-direction: column; gap: 5px; }
.blocker { display: flex; align-items: flex-start; gap: 8px; padding: 6px 8px; border-radius: var(--radius); font-size: 11.5px; font-family: var(--font-mono); border: 1px solid transparent; }
.blocker--error   { color: var(--ork-red);   background: var(--ork-red-bg);   border-color: color-mix(in oklch, var(--ork-red) 20%, transparent); }
.blocker--warning { color: var(--ork-amber); background: var(--ork-amber-bg); border-color: color-mix(in oklch, var(--ork-amber) 20%, transparent); }
.blocker--ok      { color: var(--ork-green); background: var(--ork-green-bg); border-color: color-mix(in oklch, var(--ork-green) 20%, transparent); }
.gate__foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; }

/* ── Pipeline list ────────────────────────────────────────────── */
.pipe { display: flex; flex-direction: column; border: 1px solid var(--ork-border); border-radius: var(--radius-lg); overflow: hidden; background: var(--ork-surface); }
.pipe__row { display: grid; grid-template-columns: 26px 1fr auto; gap: 12px; align-items: center; padding: 9px 12px; border-bottom: 1px solid var(--ork-border); font-family: var(--font-mono); font-size: 11.5px; }
.pipe__row:last-child { border-bottom: none; }
.pipe__row:hover { background: var(--ork-panel); }
.pipe__idx { color: var(--ork-muted-2); font-size: 10.5px; text-align: right; }
.pipe__id { color: var(--ork-text); font-size: 12px; }
.routing { display: inline-flex; align-items: center; gap: 5px; padding: 1px 7px; height: 18px; border-radius: var(--radius); font-family: var(--font-mono); font-size: 10px; text-transform: lowercase; border: 1px solid transparent; }
.routing--sequential { color: var(--accent); border-color: color-mix(in oklch, var(--accent) 30%, transparent); background: var(--ork-green-bg); }
.routing--dynamic    { color: var(--ork-purple); border-color: color-mix(in oklch, var(--ork-purple) 30%, transparent); background: var(--ork-purple-bg); }

/* ── Forbidden effects ────────────────────────────────────────── */
.forbidden { display: flex; flex-wrap: wrap; gap: 5px; }
.forbidden__item { font-family: var(--font-mono); font-size: 10.5px; padding: 2px 7px; border-radius: var(--radius); color: var(--ork-red); background: var(--ork-red-bg); border: 1px solid color-mix(in oklch, var(--ork-red) 22%, transparent); }

/* ── MCP rows ─────────────────────────────────────────────────── */
.mcprow { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: center; padding: 9px 12px; border-bottom: 1px solid var(--ork-border); background: var(--ork-surface); }
.mcprow:hover { background: var(--ork-panel); }
.mcprow__name { color: var(--ork-text); font-size: 12.5px; font-weight: 500; }
.mcprow__id { font-family: var(--font-mono); font-size: 10.5px; color: var(--ork-muted); }
.mcprow__meta { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 3px; }

/* ── Codebox ──────────────────────────────────────────────────── */
.codebox { background: var(--ork-bg); border: 1px solid var(--ork-border); border-radius: var(--radius-lg); padding: 12px 14px; font-family: var(--font-mono); font-size: 11.5px; color: var(--ork-text-1); white-space: pre-wrap; line-height: 1.6; max-height: 360px; overflow-y: auto; }
.codebox--muted { color: var(--ork-muted); }

/* ── Chat ─────────────────────────────────────────────────────── */
.chat { display: flex; flex-direction: column; height: 60vh; border: 1px solid var(--ork-border); border-radius: var(--radius-lg); background: var(--ork-bg); overflow: hidden; }
.chat__scroll { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.chat__row { display: flex; }
.chat__row.u { justify-content: flex-end; }
.chat__bubble { max-width: 80%; border-radius: var(--radius-lg); padding: 9px 12px; font-size: 12.5px; line-height: 1.5; }
.chat__bubble.u { background: var(--ork-green-bg); border: 1px solid color-mix(in oklch, var(--accent) 30%, transparent); color: var(--ork-text); border-top-right-radius: 2px; }
.chat__bubble.a { background: var(--ork-surface); border: 1px solid var(--ork-border); color: var(--ork-text-1); border-top-left-radius: 2px; }
.chat__who { font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.06em; text-transform: lowercase; margin-bottom: 4px; color: var(--ork-muted-2); }
.chat__input { display: flex; gap: 10px; align-items: flex-end; padding: 12px 14px; border-top: 1px solid var(--ork-border); background: var(--ork-surface); }
.chat__input textarea { flex: 1; background: var(--ork-bg); border: 1px solid var(--ork-border); border-radius: var(--radius); padding: 8px 10px; font-family: var(--font-mono); font-size: 12px; min-height: 38px; max-height: 100px; resize: none; outline: none; color: var(--ork-text); }
.chat__input textarea:focus { border-color: var(--ork-border-2); }
.chat__empty { height: 100%; display: grid; place-items: center; font-family: var(--font-mono); font-size: 11.5px; color: var(--ork-muted-2); text-align: center; line-height: 1.7; padding: 24px; }
.thinking { display: inline-flex; align-items: center; gap: 6px; color: var(--accent); font-family: var(--font-mono); font-size: 11.5px; }
.thinking .dot { width: 4px; height: 4px; background: currentColor; border-radius: 999px; animation: dotBlink 1s infinite; }
.thinking .dot:nth-child(2) { animation-delay: .15s; }
.thinking .dot:nth-child(3) { animation-delay: .3s; }

/* ── Density variants ─────────────────────────────────────────── */
.density-compact .table tbody td { height: 32px; }
.density-compact .kv .k, .density-compact .kv .v { padding: 6px 0; }
.density-compact .block { padding: 10px 0; }
.density-roomy .table tbody td { height: 48px; }
.density-roomy .kv .k, .density-roomy .kv .v { padding: 12px 0; }

/* ── ReactFlow overrides ──────────────────────────────────────── */
.react-flow__attribution { display: none !important; }
.react-flow__controls-button { background: transparent !important; border: none !important; color: var(--ork-muted-2) !important; fill: var(--ork-muted-2) !important; }
.react-flow__controls-button:hover { color: var(--ork-cyan) !important; fill: var(--ork-cyan) !important; }
.react-flow__handle { border-radius: 50% !important; transition: transform 0.15s, box-shadow 0.15s !important; }
.react-flow__handle:hover { transform: scale(1.5) !important; }
```

- [ ] **Step 2.2 — Vérifier que le build compile**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs. (Des warnings visuels peuvent apparaître dans le navigateur — c'est attendu avant de migrer les composants.)

- [ ] **Step 2.3 — Commit**

```bash
git add src/globals.css
git commit -m "feat(ui): replace globals.css with template design system (OKLCH tokens, full component library)"
```

---

## Task 3 : Layout — app-shell.tsx + topbar.tsx

**Files:**
- Modify: `src/components/layout/app-shell.tsx`
- Create: `src/components/layout/topbar.tsx`

- [ ] **Step 3.1 — Créer src/components/layout/topbar.tsx**

```tsx
"use client";

import { usePathname } from "next/navigation";

const BREADCRUMB_LABELS: Record<string, string> = {
  agents: "agents",
  "test-lab": "test-lab",
  mcps: "mcps",
  runs: "runs",
  audit: "audit",
  approvals: "approvals",
  requests: "requests",
  cases: "cases",
  workflows: "workflows",
  plans: "plans",
  admin: "admin",
  control: "control",
};

export function Topbar() {
  const pathname = usePathname();

  const segments = pathname.split("/").filter(Boolean);
  const section = segments[0] ? BREADCRUMB_LABELS[segments[0]] || segments[0] : "dashboard";
  const sub = segments[1] && !segments[1].startsWith("[") ? segments[1] : null;

  return (
    <header className="topbar">
      <div className="topbar__crumbs">
        <span>orkestra</span>
        <span style={{ color: "var(--ork-border-2)" }}>/</span>
        <strong>{section}</strong>
        {sub && (
          <>
            <span style={{ color: "var(--ork-border-2)" }}>/</span>
            <span>{sub}</span>
          </>
        )}
      </div>
      <div className="topbar__right">
        <div className="topbar__health">
          <span className="glow-dot" style={{ color: "var(--ork-green)" }} />
          api · nominal
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 3.2 — Mettre à jour src/components/layout/app-shell.tsx**

```tsx
"use client";

import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app">
      <Sidebar />
      <div className="main flex flex-col">
        <Topbar />
        <main className="flex-1 overflow-hidden min-h-0">{children}</main>
      </div>
    </div>
  );
}
```

- [ ] **Step 3.3 — Vérifier TypeScript**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs.

- [ ] **Step 3.4 — Commit**

```bash
git add src/components/layout/app-shell.tsx src/components/layout/topbar.tsx
git commit -m "feat(ui): add topbar with breadcrumbs, refactor app-shell to .app grid"
```

---

## Task 4 : Layout — sidebar.tsx

**Files:**
- Modify: `src/components/layout/sidebar.tsx`

- [ ] **Step 4.1 — Remplacer sidebar.tsx**

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot, Wrench, Activity, FlaskConical, Settings, SlidersHorizontal,
  FileText, CheckSquare, Shield, List, BarChart2,
} from "lucide-react";

type NavItem =
  | { section: string }
  | { label: string; href: string; icon: React.ElementType };

const NAV: NavItem[] = [
  { label: "Dashboard",      href: "/",                       icon: Activity },
  { section: "Registries" },
  { label: "Agents",         href: "/agents",                 icon: Bot },
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
```

- [ ] **Step 4.2 — Vérifier TypeScript**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs.

- [ ] **Step 4.3 — Commit**

```bash
git add src/components/layout/sidebar.tsx
git commit -m "feat(ui): refactor sidebar — navlink active state, sections, template classes"
```

---

## Task 5 : Composants UI — StatusBadge + StatCard

**Files:**
- Modify: `src/components/ui/status-badge.tsx`
- Modify: `src/components/ui/stat-card.tsx`

- [ ] **Step 5.1 — Remplacer status-badge.tsx**

```tsx
// Mapping statut → variante badge du template
const STATUS_VARIANT: Record<string, string> = {
  // Runs
  running:       "running",
  completed:     "completed",
  failed:        "failed",
  blocked:       "blocked",
  cancelled:     "cancelled",
  planned:       "planned",
  pending:       "pending",
  ready:         "tested",
  hold:          "pending",
  waiting_review:"pending",
  // Requests/cases
  draft:         "draft",
  designed:      "designed",
  submitted:     "tested",
  ready_for_planning: "designed",
  planning:      "designed",
  // Agent/MCP lifecycle
  active:        "active",
  deprecated:    "deprecated",
  disabled:      "disabled",
  degraded:      "degraded",
  tested:        "tested",
  registered:    "registered",
  archived:      "archived",
  restricted:    "pending",
  hidden:        "archived",
  healthy:       "healthy",
  warning:       "warning",
  failing:       "failed",
  published:     "active",
  // Control
  allow:         "allow",
  deny:          "deny",
  review_required: "pending",
  adjust:        "planned",
  // Approvals
  requested:     "pending",
  assigned:      "tested",
  approved:      "approved",
  rejected:      "rejected",
  refine_required: "pending",
  validated:     "active",
  not_tested:    "not_tested",
  passed:        "passed",
  passed_with_warnings: "passed_with_warnings",
  partial:       "pending",
};

export function StatusBadge({ status }: { status: string }) {
  const variant = STATUS_VARIANT[status] || "draft";
  return (
    <span
      role="status"
      aria-label={`Status: ${status.replace(/_/g, " ")}`}
      className={`badge badge--${variant}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
```

- [ ] **Step 5.2 — Remplacer stat-card.tsx**

```tsx
interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "cyan" | "green" | "amber" | "red" | "purple";
  barPercent?: number;
}

export function StatCard({ label, value, sub, accent = "cyan", barPercent }: StatCardProps) {
  return (
    <div className={`stat stat--${accent}`}>
      <div className="stat__label">{label}</div>
      <div className="stat__value">{value}</div>
      {sub && <div className="stat__delta">{sub}</div>}
      {barPercent !== undefined && (
        <div className="stat__bar">
          <span style={{ width: `${Math.min(100, Math.max(0, barPercent))}%` }} />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5.3 — Vérifier TypeScript**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs.

- [ ] **Step 5.4 — Commit**

```bash
git add src/components/ui/status-badge.tsx src/components/ui/stat-card.tsx
git commit -m "feat(ui): refactor StatusBadge (lowercase+dot) and StatCard (template classes)"
```

---

## Task 6 : Dashboard page

**Files:**
- Modify: `src/app/page.tsx`

- [ ] **Step 6.1 — Remplacer src/app/page.tsx**

```tsx
"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { StatCard } from "@/components/ui/stat-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { api } from "@/lib/api";
import type { PlatformMetrics, Agent, MCP } from "@/lib/types";

const MOCK_METRICS: PlatformMetrics = {
  total_runs: 24,
  runs_by_status: { completed: 14, running: 3, failed: 2, planned: 5 },
  total_agent_cost: 12.48,
  total_mcp_cost: 3.72,
  total_cost: 16.2,
  control_decisions_by_type: { allow: 42, deny: 7, review_required: 5, adjust: 3 },
  audit_events_total: 187,
};

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [mcps, setMcps] = useState<MCP[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [m, a, mc] = await Promise.all([
          api.getPlatformMetrics(),
          api.listAgents(),
          api.listMCPs(),
        ]);
        setMetrics(m);
        setAgents(a.items || []);
        setMcps(mc.items || []);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "API offline");
        setMetrics(MOCK_METRICS);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const m = metrics || MOCK_METRICS;
  const activeAgents = error ? 6 : agents.filter((a) => a.status === "active").length;
  const activeMcps = error ? 4 : mcps.filter((mc) => mc.status === "active").length;
  const maxStatusCount = Math.max(...Object.values(m.runs_by_status), 1);

  const statusBarColor: Record<string, string> = {
    completed: "var(--ork-green)", running: "var(--ork-cyan)",
    failed: "var(--ork-red)", planned: "var(--ork-purple)",
    pending: "var(--ork-amber)", cancelled: "var(--ork-muted-2)",
    blocked: "var(--ork-red)",
  };

  const decisionColor: Record<string, string> = {
    allow: "var(--ork-green)", deny: "var(--ork-red)",
    review_required: "var(--ork-amber)", adjust: "var(--ork-purple)",
  };

  if (loading) {
    return (
      <div className="page flex items-center justify-center" style={{ minHeight: "60vh" }}>
        <div className="text-center" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
          <div style={{ width: 24, height: 24, border: "2px solid var(--ork-border)", borderTopColor: "var(--ork-cyan)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
          <p className="section-title">Loading platform metrics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page animate-fade-in">
      {/* Page header */}
      <div className="pagehead">
        <div>
          <h1>Command Center</h1>
          <p>Governed Multi-Agent Orchestration Platform</p>
        </div>
        {error && (
          <span className="badge badge--pending">demo mode · api offline</span>
        )}
      </div>

      {/* Stat cards */}
      <div className="stats">
        <StatCard label="Total Runs"     value={m.total_runs}                          accent="cyan"   barPercent={75} sub={`${m.runs_by_status.running || 0} active`} />
        <StatCard label="Active Agents"  value={activeAgents}                          accent="green"  barPercent={Math.round((activeAgents / (agents.length || 8)) * 100)} sub={`${agents.length || 8} registered`} />
        <StatCard label="Active MCPs"    value={activeMcps}                            accent="purple" barPercent={Math.round((activeMcps / (mcps.length || 6)) * 100)} sub={`${mcps.length || 6} registered`} />
        <StatCard label="Total Cost"     value={`$${m.total_cost.toFixed(2)}`}         accent="amber"  sub={`agents $${m.total_agent_cost.toFixed(2)}`} />
      </div>

      {/* Middle row */}
      <div className="grid gap-4" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        {/* Runs by Status */}
        <div className="glass-panel" style={{ padding: "14px 16px" }}>
          <p className="section-title" style={{ marginBottom: 12 }}>Runs by Status</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {Object.entries(m.runs_by_status).map(([status, count]) => (
              <div key={status} className="row">
                <div style={{ width: 90, flexShrink: 0 }}>
                  <StatusBadge status={status} />
                </div>
                <div style={{ flex: 1, height: 4, background: "var(--ork-border)", borderRadius: 999, overflow: "hidden" }}>
                  <div style={{ height: "100%", borderRadius: 999, background: statusBarColor[status] || "var(--ork-muted-2)", width: `${(count / maxStatusCount) * 100}%`, minWidth: count > 0 ? 4 : 0 }} />
                </div>
                <span className="mono dim" style={{ fontSize: 12, width: 28, textAlign: "right" }}>{count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Control Decisions */}
        <div className="glass-panel" style={{ padding: "14px 16px" }}>
          <p className="section-title" style={{ marginBottom: 12 }}>Control Decisions</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {Object.entries(m.control_decisions_by_type).map(([type, count]) => (
              <div key={type} style={{ background: "var(--ork-bg)", borderRadius: "var(--radius-lg)", padding: "10px 12px", border: "1px solid var(--ork-border)" }}>
                <p className="section-title" style={{ marginBottom: 6 }}>{type.replace(/_/g, " ")}</p>
                <p className="stat-value" style={{ color: decisionColor[type] || "var(--ork-text)" }}>{count}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 12 }}>
        <div className="glass-panel" style={{ padding: "14px 16px" }}>
          <p className="section-title" style={{ marginBottom: 8 }}>Audit Trail</p>
          <p className="stat-value" style={{ color: "var(--ork-cyan)" }}>{m.audit_events_total}</p>
          <p className="dim" style={{ fontFamily: "var(--font-mono)", fontSize: 11, marginTop: 4 }}>total recorded events</p>
        </div>
        <div className="glass-panel" style={{ padding: "14px 16px" }}>
          <p className="section-title" style={{ marginBottom: 10 }}>Quick Actions</p>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <Link href="/requests/new" className="btn btn--cyan">New Request</Link>
            <Link href="/requests"     className="btn">Requests</Link>
            <Link href="/cases"        className="btn">Cases</Link>
            <Link href="/runs"         className="btn">Runs</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6.2 — Vérifier TypeScript**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs.

- [ ] **Step 6.3 — Commit**

```bash
git add src/app/page.tsx
git commit -m "feat(ui): refactor dashboard — template classes, pagehead, stats grid"
```

---

## Task 7 : Agents list page — split view

**Files:**
- Modify: `src/app/agents/page.tsx`

- [ ] **Step 7.1 — Ajouter l'état de sélection et le detail pane**

Dans `src/app/agents/page.tsx`, localiser la fonction `AgentRegistryPageContent` et appliquer ces changements au JSX du `return` :

**Ajouter l'import et le state** (juste après les imports existants, dans la fonction `AgentRegistryPageContent`) :

```tsx
// Ajouter après les useState existants :
const [selectedAgent, setSelectedAgent] = useState<AgentDefinition | null>(null);
```

**Remplacer le return JSX** de `AgentRegistryPageContent` par :

```tsx
return (
  <div className="page animate-fade-in">
    {/* Page header */}
    <div className="pagehead">
      <div>
        <h1>Agent Registry</h1>
        <p>Governed registry of specialized agents with mission, MCP permissions, contracts, lifecycle, and reliability metadata.</p>
      </div>
      <div className="pagehead__actions">
        <Link href="/agents/new" className="btn btn--cyan">+ Add Agent</Link>
        <button onClick={() => setAiModalOpen(true)} className="btn btn--purple">✦ Generate</button>
      </div>
    </div>

    {/* Stat cards */}
    <div className="stats">
      <StatCard label="Active"      value={stats.active_agents}     accent="green"  />
      <StatCard label="Tested"      value={stats.tested_agents}     accent="cyan"   />
      <StatCard label="Deprecated"  value={stats.deprecated_agents} accent="amber"  />
      <StatCard label="In Workflow" value={stats.current_workflow_agents} accent="purple" />
    </div>

    {/* Filters */}
    <div className="filters" style={{ gridTemplateColumns: "2fr 1fr 1fr 1fr auto" }}>
      <div className="fieldwrap">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
        <input
          className="field"
          value={filters.q ?? ""}
          onChange={(e) => updateFilter("q", e.target.value)}
          placeholder="Search name, id, purpose, skill"
        />
      </div>
      <select className="field" value={filters.family ?? "all"} onChange={(e) => updateFilter("family", e.target.value)}>
        <option value="all">family: all</option>
        {families.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
      </select>
      <select className="field" value={filters.status ?? "all"} onChange={(e) => updateFilter("status", e.target.value)}>
        <option value="all">status: all</option>
        {["draft","designed","tested","registered","active","deprecated","disabled","archived"].map((s) => (
          <option key={s} value={s}>{s}</option>
        ))}
      </select>
      <select className="field" value={filters.criticality ?? "all"} onChange={(e) => updateFilter("criticality", e.target.value)}>
        <option value="all">criticality: all</option>
        {["low","medium","high","critical"].map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
      <button className="btn btn--cyan" onClick={applyFilters}>Apply</button>
    </div>

    {/* Split view */}
    <div className="split">
      {/* Table */}
      <div className="tablewrap">
        {loading ? (
          <div style={{ padding: "32px 16px", textAlign: "center" }}>
            <p className="section-title">Loading agents...</p>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Family</th>
                <th>Status</th>
                <th>Criticality</th>
                <th>Version</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr
                  key={agent.id}
                  className={selectedAgent?.id === agent.id ? "is-selected" : ""}
                  onClick={() => setSelectedAgent(agent)}
                >
                  <td className="col-name">
                    {agent.name}
                    <span className="sub">{agent.id}</span>
                  </td>
                  <td className="col-fam">{agent.family_id}</td>
                  <td><StatusBadge status={agent.status} /></td>
                  <td>
                    <span className={`crit crit--${agent.criticality || "low"}`}>
                      {agent.criticality || "low"}
                    </span>
                  </td>
                  <td className="col-fam">{agent.version}</td>
                  <td>
                    <div className="row" onClick={(e) => e.stopPropagation()}>
                      <Link href={`/agents/${agent.id}`} className="btn btn--ghost" style={{ height: 22, fontSize: 11, padding: "0 7px" }}>view</Link>
                      <button
                        onClick={() => setAgentPendingDelete(agent)}
                        className="btn btn--ghost"
                        style={{ height: 22, fontSize: 11, padding: "0 7px", color: "var(--ork-red)" }}
                      >del</button>
                    </div>
                  </td>
                </tr>
              ))}
              {agents.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--ork-muted-2)", fontFamily: "var(--font-mono)", fontSize: 11.5, padding: "24px 0" }}>No agents found</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Detail pane */}
      <div className="detail">
        {!selectedAgent ? (
          <div className="detail__empty">
            <span>Select an agent<br/>to see details</span>
          </div>
        ) : (
          <>
            <div className="detail__head">
              <div className="detail__idrow">
                <span className="detail__id">{selectedAgent.id}</span>
                <StatusBadge status={selectedAgent.status} />
              </div>
              <div className="detail__name">{selectedAgent.name}</div>
              {selectedAgent.purpose && (
                <p className="detail__purpose">{selectedAgent.purpose}</p>
              )}
              <div className="detail__meta">
                <span className={`crit crit--${selectedAgent.criticality || "low"}`}>{selectedAgent.criticality || "low"}</span>
                <span className="chip chip--mini">{selectedAgent.family_id}</span>
                {selectedAgent.version && <span className="chip chip--mini">v{selectedAgent.version}</span>}
              </div>
            </div>
            <div className="tabs">
              <button className="tabs__btn tabs__btn--active">Details</button>
              <button className="tabs__btn">Skills</button>
            </div>
            <div className="tabpane">
              <div className="kv">
                <span className="k">Agent ID</span><span className="v mono">{selectedAgent.id}</span>
                <span className="k">Family</span><span className="v">{selectedAgent.family_id}</span>
                <span className="k">Status</span><span className="v"><StatusBadge status={selectedAgent.status} /></span>
                <span className="k">Version</span><span className="v mono">{selectedAgent.version || "—"}</span>
                <span className="k">Criticality</span><span className="v"><span className={`crit crit--${selectedAgent.criticality || "low"}`}>{selectedAgent.criticality || "low"}</span></span>
                <span className="k">Cost Profile</span><span className="v mono">{selectedAgent.cost_profile || "—"}</span>
                {selectedAgent.llm_model && <><span className="k">LLM Model</span><span className="v mono">{selectedAgent.llm_model}</span></>}
              </div>
              {selectedAgent.skill_ids && selectedAgent.skill_ids.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <p className="section-title" style={{ marginBottom: 8 }}>Skills</p>
                  <div className="row flex-wrap">
                    {selectedAgent.skill_ids.map((s: string) => (
                      <span key={s} className="chip chip--mini">{s}</span>
                    ))}
                  </div>
                </div>
              )}
              <div style={{ marginTop: 16 }}>
                <Link href={`/agents/${selectedAgent.id}`} className="btn btn--cyan" style={{ width: "100%", justifyContent: "center" }}>
                  View Full Details →
                </Link>
              </div>
            </div>
          </>
        )}
      </div>
    </div>

    {/* Modals (logique inchangée) */}
    {agentPendingDelete && (
      <ConfirmDangerDialog
        label={agentPendingDelete.name}
        onConfirm={confirmDeleteAgent}
        onCancel={() => setAgentPendingDelete(null)}
        loading={deletingAgentId === agentPendingDelete.id}
      />
    )}
    {aiModalOpen && (
      <GenerateAgentModal onClose={() => setAiModalOpen(false)} onSaved={() => { setAiModalOpen(false); void loadAll(filters); }} />
    )}
  </div>
);
```

- [ ] **Step 7.2 — Vérifier TypeScript**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs.

- [ ] **Step 7.3 — Commit**

```bash
git add src/app/agents/page.tsx
git commit -m "feat(ui): agents page — split view with detail pane, template classes"
```

---

## Task 8 : Agent form — agent-form.tsx

**Files:**
- Modify: `src/components/agents/agent-form.tsx`

- [ ] **Step 8.1 — Remplacer les patterns de style Tailwind dans agent-form.tsx**

Il s'agit d'un fichier volumineux (~1000 lignes). Appliquer ces remplacements globaux (find & replace) :

| Pattern Tailwind | Classe template |
|---|---|
| `bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono` | `field` |
| `bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono focus:outline-none` | `field` |
| `px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10` | `btn btn--cyan` |
| `px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-purple/30 text-ork-purple bg-ork-purple/10` | `btn btn--purple` |
| `px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-red/30 text-ork-red bg-ork-red/10` | `btn btn--red` |
| `text-xs font-mono text-ork-dim` (labels) | `field-label` |
| `glass-panel p-4` ou `glass-panel p-5` | `gate` (pour les sections formulaire) |
| `text-xl font-semibold text-ork-text tracking-wide` | inline style `font-size:17px; font-weight:500; letter-spacing:-0.01em` |
| `section-title` | `section-title` (déjà correct, inchangé) |
| `text-ork-muted` | `muted` |
| `text-ork-dim` | `dim` |
| `text-ork-text` | `text` |

Pour les `<input>`, `<select>`, `<textarea>` : remplacer leurs `className` Tailwind par `className="field"`.

Pour les boutons de soumission : `className="btn btn--cyan"`.

Pour les boutons secondaires/annulation : `className="btn"` ou `className="btn btn--ghost"`.

Pour les sections de formulaire (blocs regroupant plusieurs champs) : envelopper dans `<div className="gate">` avec `<h3 className="gate__title">`.

- [ ] **Step 8.2 — Vérifier TypeScript**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs.

- [ ] **Step 8.3 — Commit**

```bash
git add src/components/agents/agent-form.tsx
git commit -m "feat(ui): agent-form — replace all Tailwind input/button classes with template classes"
```

---

## Task 9 : Lifecycle components

**Files:**
- Modify: `src/components/agents/lifecycle/PromotionPath.tsx`
- Modify: `src/components/agents/lifecycle/TransitionGate.tsx`
- Modify: `src/components/agents/lifecycle/AgentLifecyclePanel.tsx`
- Modify: `src/components/agents/lifecycle/OperationalStates.tsx`

- [ ] **Step 9.1 — Lire les fichiers lifecycle**

```bash
cat src/components/agents/lifecycle/PromotionPath.tsx
cat src/components/agents/lifecycle/TransitionGate.tsx
cat src/components/agents/lifecycle/AgentLifecyclePanel.tsx
cat src/components/agents/lifecycle/OperationalStates.tsx
```

- [ ] **Step 9.2 — Refactorer PromotionPath.tsx**

Dans `PromotionPath.tsx`, remplacer les classes Tailwind par les classes du template :

- Le conteneur principal → `className="promotion"`
- Le header → `className="promotion__head"`
- La liste d'étapes → `className="promopath"`
- Chaque step → `className="promopath__step"`
- Le dot d'une étape :
  - Complétée → `className="promopath__dot promopath__dot--done"`
  - Courante → `className="promopath__dot promopath__dot--current"`
  - Verrouillée → `className="promopath__dot promopath__dot--locked"`
- Le label → `className="promopath__label promopath__label--{done|current|locked}"`
- Le connecteur → `className="promopath__connector"`
- La ligne → `className={`promopath__line${isDone ? " promopath__line--done" : ""}`}`

- [ ] **Step 9.3 — Refactorer TransitionGate.tsx**

Dans `TransitionGate.tsx` :

- Le conteneur → `className="gate"`
- L'en-tête → `className="gate__head"`
- Le titre → `className="gate__title"`
- La liste des blockers → `className="gate__blockers"`
- Chaque blocker :
  - Erreur → `className="blocker blocker--error"`
  - Warning → `className="blocker blocker--warning"`
  - OK → `className="blocker blocker--ok"`
- Le footer (boutons) → `className="gate__foot"`

- [ ] **Step 9.4 — Refactorer AgentLifecyclePanel.tsx + OperationalStates.tsx**

Dans `AgentLifecyclePanel.tsx` :
- Le panneau principal → `className="glass-panel"` + `style={{ padding: "14px 16px" }}`
- Les titres de section → `className="section-title"`

Dans `OperationalStates.tsx` :
- Le conteneur → `className="opstates"` (`.opstates { display: flex; gap: 8px; flex-wrap: wrap; }`)
- Chaque état → `className="badge badge--{variant}"`

- [ ] **Step 9.5 — Vérifier TypeScript**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs.

- [ ] **Step 9.6 — Commit**

```bash
git add src/components/agents/lifecycle/
git commit -m "feat(ui): lifecycle components — promopath, gate, blockers using template classes"
```

---

## Task 10 : Test Lab page

**Files:**
- Modify: `src/app/test-lab/page.tsx`

- [ ] **Step 10.1 — Appliquer les patterns template à test-lab/page.tsx**

Lire le fichier puis appliquer :

```bash
cat src/app/test-lab/page.tsx
```

Remplacements à effectuer :

- Wrapper de page → `<div className="page animate-fade-in">`
- Page header → `<div className="pagehead"><div><h1>Test Lab</h1><p>...</p></div><div className="pagehead__actions">...</div></div>`
- Stats → `<div className="stats">` + `<StatCard ... />`
- Table des scénarios → `<div className="tablewrap"><table className="table">...`
- Thead → `<th>` avec hauteur 28px automatique via CSS
- Tbody rows → `<tr>` avec `<td>` (logique inchangée)
- Boutons → `className="btn"`, `className="btn btn--cyan"`
- Inputs de filtre → `className="field"`
- Badges status → `<StatusBadge status={...} />`

- [ ] **Step 10.2 — Vérifier TypeScript**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs.

- [ ] **Step 10.3 — Commit**

```bash
git add src/app/test-lab/page.tsx
git commit -m "feat(ui): test-lab page — template layout, tablewrap table, pagehead"
```

---

## Task 11 : MCPs page — split view

**Files:**
- Modify: `src/app/mcps/page.tsx`

- [ ] **Step 11.1 — Lire et refactorer mcps/page.tsx**

```bash
cat src/app/mcps/page.tsx
```

Appliquer le même pattern split view que la page agents (Task 7) :

- `selectedMcp` state : `useState<MCP | null>(null)`
- Wrapper → `<div className="page">`
- Pagehead avec h1 + actions
- Stats row : `<div className="stats">`
- Filtres : `<div className="filters">`
- Split : `<div className="split">`
- Table gauche : `<div className="tablewrap"><table className="table">`
- Rows cliquables : `onClick={() => setSelectedMcp(mcp)}`, `className={selectedMcp?.id === mcp.id ? "is-selected" : ""}`
- Detail pane droite : `<div className="detail">` avec `.detail__head`, `.detail__name`, `.tabs`, `.tabpane`, `.kv`
- Bouton "View Full Details" : `<Link href={/mcps/${selectedMcp.id}} className="btn btn--cyan">`

- [ ] **Step 11.2 — Vérifier TypeScript**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs.

- [ ] **Step 11.3 — Commit**

```bash
git add src/app/mcps/page.tsx
git commit -m "feat(ui): mcps page — split view + template classes"
```

---

## Task 12 : Pages secondaires — harmonisation

**Files:**
- Modify: `src/app/runs/page.tsx`
- Modify: `src/app/audit/page.tsx`
- Modify: `src/app/approvals/page.tsx`
- Modify: `src/app/requests/page.tsx`
- Modify: `src/app/agents/[id]/page.tsx`

- [ ] **Step 12.1 — Pattern à appliquer à chaque page**

Pour chacune de ces pages, lire le fichier puis appliquer ces remplacements systématiques :

```bash
# Lire chaque fichier avant de modifier
cat src/app/runs/page.tsx
cat src/app/audit/page.tsx
cat src/app/approvals/page.tsx
```

Remplacements par page :

**Pattern commun à toutes :**
- Wrapper externe → `<div className="page animate-fade-in">`
- Heading h1 → `<div className="pagehead"><div><h1>Nom Page</h1></div></div>`
- Tables → `<div className="tablewrap"><table className="table">` + thead/tbody corrects
- Badges → `<StatusBadge status={...} />`
- Boutons d'action → `className="btn"` ou `className="btn btn--cyan"`
- Inputs → `className="field"`
- Panels de contenu → `className="glass-panel"` + `style={{ padding: "14px 16px" }}`
- Titres de section → `className="section-title"`

**runs/page.tsx :** Table de runs avec colonnes id, agent, status, duration, cost. Ajouter un filtre `.filters`.

**audit/page.tsx :** Table d'événements. Colonnes : timestamp, type, agent, details.

**approvals/page.tsx :** Table d'approbations. StatusBadge pour pending/approved/rejected.

**agents/[id]/page.tsx :** KV display pour les métadonnées. Tabs pour Details/Chat/Lifecycle.

- [ ] **Step 12.2 — Vérifier TypeScript**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs.

- [ ] **Step 12.3 — Commit**

```bash
git add src/app/runs/page.tsx src/app/audit/page.tsx src/app/approvals/page.tsx src/app/requests/page.tsx src/app/agents/[id]/page.tsx
git commit -m "feat(ui): harmonize secondary pages — template classes, tablewrap, pagehead"
```

---

## Task 13 : RunGraph components

**Files:**
- Modify: `src/components/test-lab/run-graph/RunTopbar.tsx`
- Modify: `src/components/test-lab/run-graph/DetailPanel.tsx`
- Modify: `src/components/test-lab/run-graph/nodes/AgentNode.tsx`

- [ ] **Step 13.1 — Lire les fichiers RunGraph**

```bash
cat src/components/test-lab/run-graph/RunTopbar.tsx
cat src/components/test-lab/run-graph/DetailPanel.tsx
cat src/components/test-lab/run-graph/nodes/AgentNode.tsx
```

- [ ] **Step 13.2 — Refactorer RunTopbar.tsx**

Dans `RunTopbar.tsx` :
- La barre de contrôle → `className="topbar"` (sticky, 44px)
- Boutons de contrôle → `className="topbar__btn"`
- Breadcrumbs/titre → `className="topbar__crumbs"`
- Conserver toute la logique play/pause/replay inchangée

- [ ] **Step 13.3 — Refactorer DetailPanel.tsx**

Dans `DetailPanel.tsx` (le panneau de détail d'un nœud) :
- Conteneur → `className="detail"` (ou `className="glass-panel"`)
- Titre du nœud → `className="detail__name"`
- ID → `className="detail__id"`
- Paires clé-valeur → structure `.kv` avec `.k` et `.v`
- Badge de statut → `<StatusBadge status={...} />`
- Conserver toute la logique d'affichage des données du nœud

- [ ] **Step 13.4 — Refactorer AgentNode.tsx**

Dans `AgentNode.tsx` (nœud ReactFlow) :
- Appliquer `background: var(--ork-surface)`, `border: 1px solid var(--ork-border)`, `border-radius: var(--radius-lg)` via CSS inline ou className `glass-panel`
- Phase tags → `className="chip chip--mini"` ou équivalent
- Status colors → utiliser les CSS vars OKLCH directement (`var(--ork-cyan)`, `var(--ork-green)`, etc.)
- Conserver les animations Framer Motion et la logique de nœud

- [ ] **Step 13.5 — Vérifier TypeScript**

```bash
npx tsc --noEmit
```

Expected: 0 erreurs.

- [ ] **Step 13.6 — Commit**

```bash
git add src/components/test-lab/run-graph/
git commit -m "feat(ui): run-graph components — topbar, detail panel, agent nodes using template tokens"
```

---

## Task 14 : Vérification finale

- [ ] **Step 14.1 — Build complet**

```bash
npm run build
```

Expected: Build successful, 0 erreurs TypeScript ou Next.js.

- [ ] **Step 14.2 — Run les tests existants**

```bash
npm test
```

Expected: Tous les tests passent. (Les tests snapshot peuvent nécessiter une mise à jour : `npm test -- --update-snapshots`)

- [ ] **Step 14.3 — Vérification visuelle manuelle**

Lancer le dev server :
```bash
npm run dev
```

Vérifier chaque page dans le navigateur à `http://localhost:3000` :
- [ ] Dashboard : pagehead, 4 stat cards avec micro-bars, grille 2 colonnes
- [ ] Agents : topbar, split view table+detail, badge lowercase+dot
- [ ] Agent detail `/agents/[id]` : kv display, tabs, lifecycle panel
- [ ] Test Lab : pagehead, table scénarios, boutons template
- [ ] MCPs : split view identique agents
- [ ] Runs : table + badges
- [ ] Sidebar : active state barre verte gauche
- [ ] Topbar : breadcrumbs + health indicator vert pulsant
- [ ] Polices Geist chargées (DevTools → Network → Fonts)
- [ ] Aucune classe Tailwind `ork-*` résiduelle dans les elements (DevTools → Elements)

- [ ] **Step 14.4 — Commit final**

```bash
git add -A
git commit -m "feat(ui): visual refonte complete — 100% fidelity to Orkestra-Mesh-template"
```

---

## Critères de succès

- [ ] Interface visuellement identique au Orkestra-Mesh-template
- [ ] Toutes les actions métier fonctionnent identiquement
- [ ] `npm run build` passe sans erreur
- [ ] `npm test` passe sans régression
- [ ] Badges en lowercase avec dot indicator 5px
- [ ] Formulaires avec champs compacts 28px
- [ ] Split view fonctionnel sur Agents et MCPs
- [ ] Geist chargé correctement (pas de FOUT)
- [ ] Topbar sticky 44px avec breadcrumbs
- [ ] Sidebar active = barre 2px verte gauche
