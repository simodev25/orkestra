# Light Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un mode clair slate cool avec un switch ☀/🌙 dans la topbar, sans modifier le dark mode existant.

**Architecture:** CSS custom properties override sous `[data-theme="light"]` dans globals.css. `next-themes` gère l'état React, la persistance localStorage et prévient le flash SSR. `ThemeProvider` wrappe `AppShell` dans layout.tsx. `ThemeToggle` s'insère dans la Topbar.

**Tech Stack:** Next.js 15 App Router, next-themes, OKLCH CSS variables, lucide-react (déjà installé)

---

## Fichiers

| Action | Fichier |
|--------|---------|
| Modifier | `frontend/src/globals.css` — ajouter bloc `[data-theme="light"]` après `:root` |
| Modifier | `frontend/src/app/layout.tsx` — wrapper ThemeProvider |
| Créer   | `frontend/src/components/layout/ThemeToggle.tsx` |
| Modifier | `frontend/src/components/layout/Topbar.tsx` — ajouter ThemeToggle |

**Déploiement Docker (pattern à utiliser après chaque modification) :**
```bash
DOCKER=/Applications/Docker.app/Contents/Resources/bin/docker
$DOCKER cp <fichier_local> orkestra-frontend-1:/app/src/<chemin_relatif>
```
Next.js HMR détecte les changements automatiquement. Hard reload (`cmd+shift+r`) si nécessaire.

---

## Task 1 — Palette CSS light mode (globals.css)

**Files:**
- Modify: `frontend/src/globals.css` — ajouter le bloc `[data-theme="light"]` après la fermeture du bloc `:root` (après la ligne 46)

Le dark mode dans `:root` (lignes 9-46) n'est PAS touché. On ajoute seulement après.

- [ ] **Step 1 : Ajouter le bloc `[data-theme="light"]` dans globals.css**

Insérer ce bloc immédiatement après la fermeture `}` du `:root` (après la ligne 46), avant le commentaire `/* ── Reset & base ─────────── */` :

```css
[data-theme="light"] {
  /* Fonds & surfaces — miroir OKLCH du dark (lightness inversée) */
  --ork-bg:       oklch(0.97 0.004 80);
  --ork-surface:  oklch(0.945 0.004 80);
  --ork-panel:    oklch(0.92 0.005 80);
  --ork-panel-2:  oklch(0.89 0.005 80);
  --ork-hover:    oklch(0.905 0.005 80);

  /* Bordures */
  --ork-border:   oklch(0.82 0.006 80);
  --ork-border-2: oklch(0.76 0.007 80);

  /* Textes — sombres sur fond clair */
  --ork-text:     oklch(0.15 0.006 265);
  --ork-text-1:   oklch(0.30 0.006 265);
  --ork-muted:    oklch(0.50 0.006 265);
  --ork-muted-2:  oklch(0.44 0.006 265);
  --ork-dim:      oklch(0.65 0.006 265);

  /* Variantes -bg des accents — passent en clair */
  --ork-green-bg:  oklch(0.92 0.04 145);
  --ork-green-dim: oklch(0.40 0.14 145);
  --ork-cyan-bg:   oklch(0.92 0.04 200);
  --ork-amber-bg:  oklch(0.93 0.04 75);
  --ork-red-bg:    oklch(0.92 0.05 25);
  --ork-purple-bg: oklch(0.92 0.04 305);
}
```

- [ ] **Step 2 : Déployer globals.css dans Docker**

```bash
DOCKER=/Applications/Docker.app/Contents/Resources/bin/docker
$DOCKER cp frontend/src/globals.css orkestra-frontend-1:/app/src/globals.css
```

- [ ] **Step 3 : Vérifier visuellement que le dark mode est intact**

Ouvrir `http://localhost:3300` dans le navigateur.
Hard reload (`cmd+shift+r`).
Le dark mode doit être identique à avant — aucun changement visible.

- [ ] **Step 4 : Vérifier manuellement l'activation du light mode**

Dans la console du navigateur, tester que les variables CSS se mettent à jour :

```js
// Activer le light mode manuellement
document.documentElement.setAttribute('data-theme', 'light');
// L'interface doit passer en mode clair (fonds clairs, textes sombres)

// Revenir en dark
document.documentElement.removeAttribute('data-theme');
// L'interface revient en dark (identique à avant)
```

- [ ] **Step 5 : Commit**

```bash
git add frontend/src/globals.css
git commit -m "feat(theme): ajouter palette light mode [data-theme=light] oklch slate"
```

---

## Task 2 — Installer next-themes et wrapper ThemeProvider (layout.tsx)

**Files:**
- Modify: `frontend/package.json` — ajouter next-themes
- Modify: `frontend/src/app/layout.tsx` — wrapper ThemeProvider

- [ ] **Step 1 : Installer next-themes**

```bash
cd frontend
npm install next-themes
```

Vérifier dans `package.json` que `"next-themes"` apparaît dans `dependencies`.

- [ ] **Step 2 : Modifier layout.tsx**

Remplacer le contenu de `frontend/src/app/layout.tsx` par :

```tsx
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
```

Note : `suppressHydrationWarning` sur `<html>` est requis par next-themes — il évite le warning React quand next-themes modifie l'attribut `data-theme` côté client après le rendu serveur.

- [ ] **Step 3 : Déployer layout.tsx et package.json dans Docker**

```bash
DOCKER=/Applications/Docker.app/Contents/Resources/bin/docker

# Copier layout.tsx
$DOCKER cp frontend/src/app/layout.tsx orkestra-frontend-1:/app/src/app/layout.tsx

# Copier package.json et package-lock.json
$DOCKER cp frontend/package.json orkestra-frontend-1:/app/package.json
$DOCKER cp frontend/package-lock.json orkestra-frontend-1:/app/package-lock.json

# Installer les dépendances dans le container
$DOCKER exec orkestra-frontend-1 npm install --prefix /app
```

- [ ] **Step 4 : Vérifier que l'app démarre sans erreur**

```bash
DOCKER=/Applications/Docker.app/Contents/Resources/bin/docker
$DOCKER logs orkestra-frontend-1 --tail 20
```

Attendu : pas d'erreur sur ThemeProvider ou next-themes. Le log doit montrer le serveur Next.js en écoute.

- [ ] **Step 5 : Vérifier dans le navigateur**

Ouvrir `http://localhost:3300`. Hard reload.
Le dark mode doit fonctionner identiquement.
Dans DevTools → Elements, l'élément `<html>` doit avoir `data-theme="dark"`.

- [ ] **Step 6 : Commit**

```bash
git add frontend/src/app/layout.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(theme): intégrer next-themes ThemeProvider dans layout.tsx"
```

---

## Task 3 — Créer le composant ThemeToggle

**Files:**
- Create: `frontend/src/components/layout/ThemeToggle.tsx`

- [ ] **Step 1 : Créer ThemeToggle.tsx**

Créer le fichier `frontend/src/components/layout/ThemeToggle.tsx` :

```tsx
"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Évite le mismatch d'hydration SSR :
  // côté serveur, on ne sait pas quel thème sera actif →
  // on rend un placeholder invisible jusqu'au montage client.
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    // Placeholder de même taille pour éviter le layout shift
    return <div className="w-7 h-7" />;
  }

  const isLight = theme === "light";

  return (
    <button
      onClick={() => setTheme(isLight ? "dark" : "light")}
      className="flex items-center justify-center w-7 h-7 rounded text-ork-muted hover:text-ork-text hover:bg-ork-hover transition-colors"
      title={isLight ? "Passer en mode sombre" : "Passer en mode clair"}
      aria-label={isLight ? "Passer en mode sombre" : "Passer en mode clair"}
    >
      {isLight
        ? <Moon className="w-3.5 h-3.5" />
        : <Sun className="w-3.5 h-3.5" />
      }
    </button>
  );
}
```

Logique de l'icône :
- Thème **dark** → affiche ☀ (Sun) → clic bascule en light
- Thème **light** → affiche 🌙 (Moon) → clic bascule en dark

- [ ] **Step 2 : Déployer ThemeToggle.tsx dans Docker**

```bash
DOCKER=/Applications/Docker.app/Contents/Resources/bin/docker
$DOCKER cp frontend/src/components/layout/ThemeToggle.tsx \
  orkestra-frontend-1:/app/src/components/layout/ThemeToggle.tsx
```

- [ ] **Step 3 : Commit**

```bash
git add frontend/src/components/layout/ThemeToggle.tsx
git commit -m "feat(theme): créer composant ThemeToggle Sun/Moon"
```

---

## Task 4 — Intégrer ThemeToggle dans la Topbar

**Files:**
- Modify: `frontend/src/components/layout/Topbar.tsx`

La Topbar actuelle (lignes 40-46) :

```tsx
<div className="topbar__right">
  <div className="topbar__health">
    <span className="glow-dot" style={{ color: "var(--ork-green)" }} />
    api · nominal
  </div>
</div>
```

- [ ] **Step 1 : Modifier Topbar.tsx**

Remplacer le contenu de `frontend/src/components/layout/Topbar.tsx` par :

```tsx
"use client";

import { usePathname } from "next/navigation";
import { ThemeToggle } from "./ThemeToggle";

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
        <ThemeToggle />
        <div className="topbar__health">
          <span className="glow-dot" style={{ color: "var(--ork-green)" }} />
          api · nominal
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 2 : Déployer Topbar.tsx dans Docker**

```bash
DOCKER=/Applications/Docker.app/Contents/Resources/bin/docker
$DOCKER cp frontend/src/components/layout/Topbar.tsx \
  orkestra-frontend-1:/app/src/components/layout/Topbar.tsx
```

- [ ] **Step 3 : Vérifier visuellement — dark mode**

Ouvrir `http://localhost:3300`. Hard reload (`cmd+shift+r`).
- L'icône ☀ (Sun) doit apparaître dans la topbar à droite de `api · nominal`
- L'interface est en dark mode
- `<html data-theme="dark">` dans DevTools

- [ ] **Step 4 : Vérifier visuellement — light mode**

Cliquer sur l'icône ☀.
- L'interface bascule en mode clair (fonds gris-blanc, textes sombres)
- L'icône devient 🌙 (Moon)
- `<html data-theme="light">` dans DevTools

- [ ] **Step 5 : Vérifier la persistance**

Avec le light mode actif, recharger la page (`cmd+r`).
- Le light mode doit être restauré sans flash
- `localStorage.getItem('orkestra-theme')` dans la console doit retourner `"light"`

- [ ] **Step 6 : Vérifier le retour en dark**

Cliquer sur 🌙.
- Retour en dark mode, icône redevient ☀
- Toutes les pages de l'app fonctionnent normalement en dark (aucune régression)

- [ ] **Step 7 : Commit final**

```bash
git add frontend/src/components/layout/Topbar.tsx
git commit -m "feat(theme): ajouter ThemeToggle dans la Topbar"
```

---

## Checklist de validation finale

- [ ] Dark mode identique à avant (aucune régression)
- [ ] Light mode : fonds clairs, textes sombres, accents cyan/green/amber inchangés
- [ ] Switch ☀/🌙 visible dans la topbar (droite, avant `api · nominal`)
- [ ] Persistance localStorage fonctionne (rechargement restaure le bon thème)
- [ ] Aucun flash visible au rechargement
- [ ] `<html>` a `suppressHydrationWarning` (pas de warning React en console)
