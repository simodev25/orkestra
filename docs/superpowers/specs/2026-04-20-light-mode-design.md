# Light Mode Implementation Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ajouter un mode clair (slate cool) au frontend Orkestra avec un switch ☀/🌙 dans la topbar, sans modifier le mode sombre existant.

**Architecture:** CSS custom properties override sous `[data-theme="light"]` + `next-themes` pour la gestion React (persistance localStorage, pas de flash SSR). Le dark mode actuel reste intact dans `:root`.

**Tech Stack:** Next.js 15 App Router, next-themes, OKLCH CSS variables, Tailwind v3.4

---

## Contrainte principale

**Le dark mode existant ne doit PAS être modifié.** Toutes les variables `--ork-*` définies dans `:root` de `globals.css` restent inchangées. On ajoute uniquement un bloc `[data-theme="light"]` en dessous.

---

## Fichiers concernés

| Action | Fichier |
|--------|---------|
| Modifier | `frontend/src/globals.css` |
| Modifier | `frontend/src/app/layout.tsx` |
| Créer   | `frontend/src/components/layout/ThemeToggle.tsx` |
| Modifier | `frontend/src/components/layout/Topbar.tsx` |

---

## Section 1 — Palette light mode (globals.css)

Ajouter après le bloc `:root` existant. Lightness inversée en OKLCH, même chroma/hue que le dark.

### Fonds & surfaces (miroir du dark)

| Variable | Dark (actuel) | Light (nouveau) |
|----------|--------------|-----------------|
| `--ork-bg` | `oklch(0.16 0.004 80)` | `oklch(0.97 0.004 80)` |
| `--ork-surface` | `oklch(0.185 0.004 80)` | `oklch(0.945 0.004 80)` |
| `--ork-panel` | `oklch(0.21 0.005 80)` | `oklch(0.92 0.005 80)` |
| `--ork-panel-2` | `oklch(0.24 0.005 80)` | `oklch(0.89 0.005 80)` |
| `--ork-hover` | `oklch(0.225 0.005 80)` | `oklch(0.905 0.005 80)` |
| `--ork-border` | `oklch(0.28 0.006 80)` | `oklch(0.82 0.006 80)` |
| `--ork-border-2` | `oklch(0.33 0.007 80)` | `oklch(0.76 0.007 80)` |

### Textes (sombres en light mode)

| Variable | Dark (actuel) | Light (nouveau) |
|----------|--------------|-----------------|
| `--ork-text` | `oklch(0.96 0.004 85)` | `oklch(0.15 0.006 265)` |
| `--ork-text-1` | `oklch(0.82 0.005 85)` | `oklch(0.30 0.006 265)` |
| `--ork-muted` | `oklch(0.62 0.006 85)` | `oklch(0.50 0.006 265)` |
| `--ork-muted-2` | `oklch(0.48 0.006 85)` | `oklch(0.44 0.006 265)` |
| `--ork-dim` | `oklch(0.48 0.006 85)` | `oklch(0.65 0.006 265)` |

### Accents — teintes identiques, variantes `-bg` inversées

Les couleurs d'accent (`--ork-cyan`, `--ork-green`, `--ork-amber`, `--ork-red`, `--ork-purple`) **restent identiques** — elles fonctionnent sur les deux thèmes. Seules les variantes `-bg` (fonds colorés) sont adaptées pour être claires :

| Variable | Dark (actuel) | Light (nouveau) |
|----------|--------------|-----------------|
| `--ork-green-bg` | `oklch(0.26 0.07 145)` | `oklch(0.92 0.04 145)` |
| `--ork-cyan-bg` | `oklch(0.26 0.06 200)` | `oklch(0.92 0.04 200)` |
| `--ork-amber-bg` | `oklch(0.28 0.07 75)` | `oklch(0.93 0.04 75)` |
| `--ork-red-bg` | `oklch(0.26 0.08 25)` | `oklch(0.92 0.05 25)` |
| `--ork-purple-bg` | `oklch(0.26 0.06 305)` | `oklch(0.92 0.04 305)` |
| `--ork-green-dim` | `oklch(0.52 0.12 145)` | `oklch(0.40 0.14 145)` |

### Bloc CSS à ajouter

```css
[data-theme="light"] {
  /* Fonds & surfaces */
  --ork-bg:       oklch(0.97 0.004 80);
  --ork-surface:  oklch(0.945 0.004 80);
  --ork-panel:    oklch(0.92 0.005 80);
  --ork-panel-2:  oklch(0.89 0.005 80);
  --ork-hover:    oklch(0.905 0.005 80);

  /* Bordures */
  --ork-border:   oklch(0.82 0.006 80);
  --ork-border-2: oklch(0.76 0.007 80);

  /* Textes */
  --ork-text:     oklch(0.15 0.006 265);
  --ork-text-1:   oklch(0.30 0.006 265);
  --ork-muted:    oklch(0.50 0.006 265);
  --ork-muted-2:  oklch(0.44 0.006 265);
  --ork-dim:      oklch(0.65 0.006 265);

  /* Variantes -bg des accents */
  --ork-green-bg:  oklch(0.92 0.04 145);
  --ork-cyan-bg:   oklch(0.92 0.04 200);
  --ork-amber-bg:  oklch(0.93 0.04 75);
  --ork-red-bg:    oklch(0.92 0.05 25);
  --ork-purple-bg: oklch(0.92 0.04 305);
  --ork-green-dim: oklch(0.40 0.14 145);
}
```

---

## Section 2 — ThemeProvider (layout.tsx)

Installer next-themes : `npm install next-themes`

Modifier `frontend/src/app/layout.tsx` pour wrapper le contenu avec `ThemeProvider` :

```tsx
import { ThemeProvider } from 'next-themes';

// Dans le body, wrapper AppShell :
<ThemeProvider
  attribute="data-theme"
  defaultTheme="dark"
  themes={['dark', 'light']}
  storageKey="orkestra-theme"
>
  <AppShell>{children}</AppShell>
</ThemeProvider>
```

`attribute="data-theme"` → next-themes pose `data-theme="dark"` ou `data-theme="light"` sur `<html>`.
`defaultTheme="dark"` → dark par défaut (comportement actuel préservé).
`storageKey="orkestra-theme"` → clé localStorage pour la persistance.

---

## Section 3 — ThemeToggle component

Créer `frontend/src/components/layout/ThemeToggle.tsx` :

```tsx
"use client";
import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Évite le mismatch hydration SSR
  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="w-7 h-7" />;

  const isLight = theme === "light";

  return (
    <button
      onClick={() => setTheme(isLight ? "dark" : "light")}
      className="flex items-center justify-center w-7 h-7 rounded text-ork-muted hover:text-ork-text hover:bg-ork-hover transition-colors"
      title={isLight ? "Passer en mode sombre" : "Passer en mode clair"}
    >
      {isLight ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
    </button>
  );
}
```

- `mounted` guard : évite le flash d'icône au SSR (next-themes recommandation officielle).
- Icône ☀ quand dark (cliquer → passer en light), 🌙 quand light (cliquer → passer en dark).
- Placeholder `w-7 h-7` pendant SSR pour éviter le layout shift.

---

## Section 4 — Topbar integration

Dans `frontend/src/components/layout/Topbar.tsx`, ajouter `<ThemeToggle />` dans `<div className="topbar__right">`, juste avant `<div className="topbar__health">`.

```tsx
import { ThemeToggle } from "./ThemeToggle";

// Remplacer topbar__right par :
<div className="topbar__right">
  <ThemeToggle />
  <div className="topbar__health">
    <span className="glow-dot" style={{ color: "var(--ork-green)" }} />
    api · nominal
  </div>
</div>
```

---

## Comportement attendu

- **Défaut** : dark mode (identique à aujourd'hui, aucun changement visible)
- **Clic ☀** : bascule en light, icône devient 🌙
- **Persistance** : choix sauvegardé dans `localStorage['orkestra-theme']`
- **Rechargement** : thème restauré sans flash (next-themes script inline)
- **Dark mode** : `:root` inchangé, identique à ce qui existe

---

## Non-inclus (YAGNI)

- Détection automatique `prefers-color-scheme` système (peut être ajouté plus tard via `enableSystem: true`)
- Transition animée entre les thèmes
- Thèmes supplémentaires (high contrast, etc.)
