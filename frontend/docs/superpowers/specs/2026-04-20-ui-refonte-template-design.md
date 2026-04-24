# UI Refonte — Fidélité 100% Orkestra-Mesh-template

**Date :** 2026-04-20  
**Statut :** Approuvé  
**Périmètre :** Refonte visuelle totale — logique métier intacte

---

## Objectif

Transformer l'interface du projet Orkestra pour qu'elle soit visuellement identique au projet **Orkestra-Mesh-template** (référence design). Le comportement fonctionnel, la logique métier, les appels API et le state management ne sont pas modifiés.

---

## Décisions de design

| Décision | Choix retenu | Raison |
|---|---|---|
| Architecture CSS | Migration complète — CSS natif + custom properties | Fidélité maximale, zéro dualité |
| Tailwind | Conservé uniquement pour utilities layout ; preflight désactivé | Évite conflits, garde flex/grid/overflow |
| Typographie | Geist + Geist Mono (package `geist` npm) | Police du template, identité distinctive |
| Couleurs | Tokens OKLCH identiques au template | Rendu perceptuellement uniforme |

---

## Section 1 — Foundation (CSS Design System)

### globals.css — remplacement total

Le fichier actuel (90 lignes) est entièrement remplacé par un nouveau fichier (~1200 lignes) portant fidèlement le design system du template.

Contenu du nouveau globals.css :

**Tokens :root OKLCH :**
```css
--ork-bg:       oklch(0.16 0.004 80)   /* fond principal */
--ork-surface:  oklch(0.185 0.004 80)  /* panneaux/cartes */
--ork-panel:    oklch(0.21 0.005 80)   /* panneaux secondaires */
--ork-panel-2:  oklch(0.24 0.005 80)   /* panneaux tertiaires */
--ork-hover:    oklch(0.225 0.005 80)  /* état hover */
--ork-border:   oklch(0.28 0.006 80)   /* bordures */
--ork-border-2: oklch(0.33 0.007 80)   /* bordures hover */
--ork-dim:      oklch(0.48 0.006 85)   /* séparateurs */
--ork-text:     oklch(0.96 0.004 85)   /* texte primaire */
--ork-text-1:   oklch(0.82 0.005 85)   /* texte secondaire */
--ork-muted:    oklch(0.62 0.006 85)   /* texte tertiaire */
--ork-muted-2:  oklch(0.48 0.006 85)   /* texte quaternaire */
--ork-green:    oklch(0.78 0.17 145)   /* succès/actif */
--ork-green-dim: oklch(0.52 0.12 145)
--ork-green-bg: oklch(0.26 0.07 145)
--ork-cyan:     oklch(0.78 0.13 200)   /* accent primaire */
--ork-cyan-bg:  oklch(0.26 0.06 200)
--ork-amber:    oklch(0.82 0.15 75)    /* warning */
--ork-amber-bg: oklch(0.28 0.07 75)
--ork-red:      oklch(0.70 0.19 25)    /* erreur */
--ork-red-bg:   oklch(0.26 0.08 25)
--ork-purple:   oklch(0.72 0.12 305)   /* accent secondaire */
--ork-purple-bg: oklch(0.26 0.06 305)
--accent:       var(--ork-green)       /* accent dynamique */
--radius:       3px
--radius-lg:    6px
--font-sans:    "Geist", "Inter Tight", system-ui, sans-serif
--font-mono:    "Geist Mono", "JetBrains Mono", ui-monospace, monospace
```

**Classes composants portées depuis le template :**
- `.btn`, `.btn--cyan`, `.btn--purple`, `.btn--red`, `.btn--ghost`
- `.badge`, `.badge--active`, `.badge--tested`, `.badge--draft`, `.badge--deprecated`, `.badge--failed`, `.badge--designed`, `.badge--running`, `.badge--disabled`, `.badge--registered`
- `.chip`, `.chip--mini`
- `.tablewrap`, `.table` (thead sticky 28px, rows 40px, hover surface)
- `.field`, `.fieldwrap` (inputs/selects/textareas — height 28px, mono 11.5px)
- `.glass-panel`, `.glass-panel-hover`
- `.stat`, `.stat--green`, `.stat--cyan`, `.stat--amber`, `.stat--purple`
- `.topbar`, `.topbar__crumbs`, `.topbar__btn`, `.topbar__health`
- `.sidebar`, `.navlink`, `.navlink--active` (barre 2px accent gauche)
- `.tabs`, `.tabs__btn`, `.tabs__btn--active`
- `.split` (grid 1fr 540px)
- `.filters` (grid search + dropdowns)
- `.kv`, `.kv .k`, `.kv .v`
- `.gate`, `.gate__title`, `.blocker`, `.blocker--ok`, `.blocker--warning`, `.blocker--error`
- `.chat`, `.chat__bubble.u`, `.chat__bubble.a`
- `.promotion`, `.promopath`, `.promopath__dot`, `.promopath__dot--done`, `.promopath__dot--current`, `.promopath__dot--locked`
- `.density-compact`, `.density-roomy` (variants hauteur tableau)
- Utilities : `.row`, `.col`, `.sep`, `.muted`, `.dim`, `.mono`, `.cyan`, `.right`
- Scrollbar styling webkit

**Keyframes :**
- `fadeIn`, `slideUp`, `pulseSlow`, `dotBlink`, `caret`, `ringPulse`
- Conservation de `edgeDash`, `nodeRingPulse`, `verdictPulse` (spécifiques RunGraph)

### tailwind.config.ts

- Suppression de tous les tokens `ork-*` hex (remplacés par CSS vars)
- Ajout `corePlugins: { preflight: false }` (évite reset conflictant avec globals.css)
- Conservation de `content`, `theme.extend` pour les animations Tailwind nécessaires au RunGraph

### layout.tsx (root)

- Installation package `geist` (`npm install geist`)
- Import `GeistSans` + `GeistMono` depuis `geist/font`
- Application via `className` sur `<html>` avec les variables CSS

---

## Section 2 — Layout Global

### Nouveau composant : Topbar (`components/layout/topbar.tsx`)

```tsx
// Structure
<header className="topbar">
  <div className="topbar__crumbs">{breadcrumbs}</div>
  <div className="topbar__right">
    <div className="topbar__health">
      <span className="glow-dot" /> api · nominal
    </div>
  </div>
</header>
```

- Hauteur : 44px, sticky top-0, z-index 5
- Breadcrumbs : dynamiques via `usePathname()` (Next.js)
- Health indicator : appel `/api/health` existant (si disponible), sinon statique

### app-shell.tsx

Avant :
```tsx
<div className="flex min-h-screen">
  <Sidebar />
  <main className="flex-1 overflow-hidden">{children}</main>
</div>
```

Après :
```tsx
<div className="app">  {/* CSS: grid 224px 1fr */}
  <Sidebar />
  <div className="flex flex-col min-h-screen">
    <Topbar />
    <main className="flex-1 overflow-hidden">{children}</main>
  </div>
</div>
```

### sidebar.tsx

- Remplacement de toutes les classes Tailwind par les classes du template
- Active state : `navlink--active` (fond panel + barre 2px verte à gauche) au lieu de `bg-ork-cyan/10 text-ork-cyan`
- Sections labellisées : "Registries", "Monitoring", "Configuration"
- Logo compact : carré 22px + texte "Orkestra"
- Badge counters sur certains liens (agents, runs)

---

## Section 3 — Composants

### StatusBadge (`components/ui/status-badge.tsx`)

Mapping statuts → classes template (`.badge .badge--{variant}`) :

| Statut actuel | Classe template |
|---|---|
| active, running, nominal | `badge--active` (vert) |
| tested, registered | `badge--tested` (cyan) |
| designed, in_progress | `badge--designed` (purple) |
| draft, pending, unknown | `badge--draft` (gris) |
| deprecated, warning | `badge--deprecated` (amber) |
| failed, error, disabled | `badge--failed` (rouge) |

- Passage en **lowercase** (au lieu de uppercase)
- Dot indicator 5px au lieu de texte seul

### StatCard (`components/ui/stat-card.tsx`)

- Structure : `.stat .stat--{accent}` + `.stat__label` + `.stat__value` + `.stat__bar`
- Valeur : 22px mono (`-0.01em`)
- Label : 10px mono uppercase
- Micro progress bar : 2px hauteur

### AgentForm (`components/agents/agent-form.tsx`)

- Tous les `<input>`, `<select>`, `<textarea>` → classe `.field`
- Labels → `.field-label` (monospace 10.5px uppercase)
- Sections de formulaire → `.gate` avec `.gate__title`
- Boutons → `.btn .btn--{variant}`
- Tags multi-select → `.chip .chip--mini`

---

## Section 4 — Périmètre des pages

### Fichiers modifiés

**CSS (2 fichiers) :**
- `frontend/src/globals.css` — remplacement total
- `frontend/tailwind.config.ts` — nettoyage tokens + preflight

**Couche globale (4 fichiers) :**
- `frontend/src/app/layout.tsx` — Geist fonts
- `frontend/src/components/layout/app-shell.tsx` — grid layout + Topbar
- `frontend/src/components/layout/sidebar.tsx` — refonte complète classes
- `frontend/src/components/layout/topbar.tsx` — **nouveau fichier**

**Composants UI (3 fichiers) :**
- `frontend/src/components/ui/status-badge.tsx`
- `frontend/src/components/ui/stat-card.tsx`
- `frontend/src/components/ui/confirm-danger-dialog.tsx`

**Pages (~15 fichiers) :**
- `frontend/src/app/page.tsx` (Dashboard)
- `frontend/src/app/agents/page.tsx` (split view)
- `frontend/src/app/agents/[id]/page.tsx`
- `frontend/src/app/agents/new/page.tsx`
- `frontend/src/app/agents/[id]/edit/page.tsx`
- `frontend/src/app/agents/families/page.tsx`
- `frontend/src/app/agents/skills/page.tsx`
- `frontend/src/app/test-lab/page.tsx`
- `frontend/src/app/test-lab/runs/[id]/page.tsx`
- `frontend/src/app/mcps/page.tsx` (split view)
- `frontend/src/app/mcps/[id]/page.tsx`
- `frontend/src/app/runs/page.tsx`
- `frontend/src/app/audit/page.tsx`
- `frontend/src/app/approvals/page.tsx`
- `frontend/src/app/requests/page.tsx`

**Composants agents (~5 fichiers) :**
- `frontend/src/components/agents/agent-form.tsx`
- `frontend/src/components/agents/lifecycle/AgentLifecyclePanel.tsx`
- `frontend/src/components/agents/lifecycle/PromotionPath.tsx`
- `frontend/src/components/agents/lifecycle/TransitionGate.tsx`
- `frontend/src/components/agents/lifecycle/OperationalStates.tsx`

**Test Lab (~4 fichiers) :**
- `frontend/src/components/test-lab/run-graph/RunGraph.tsx`
- `frontend/src/components/test-lab/run-graph/RunTopbar.tsx`
- `frontend/src/components/test-lab/run-graph/DetailPanel.tsx`
- `frontend/src/components/test-lab/run-graph/nodes/AgentNode.tsx`

### Ce qui NE change PAS

- Toute la logique dans `frontend/src/lib/` (API, services, types)
- Les handlers d'événements, callbacks, state management
- Les appels API et contrats de données
- Le routing Next.js
- Les tests existants
- Le backend

---

## Contraintes techniques

1. **Preflight Tailwind désactivé** : le reset CSS vient de globals.css (comme le template)
2. **OKLCH** : supporté par tous les navigateurs modernes (Chrome 111+, Firefox 113+, Safari 15.4+)
3. **Geist** : package npm officiel Vercel, licence MIT — pas de dépendance Google Fonts CDN
4. **Split view interaction** : clic sur une ligne de la liste → `useState<string | null>(selectedId)` dans la page (UI state pur, pas de logique métier). Le pane droite affiche un résumé. Le bouton "View details" navigue vers `/agents/[id]` (navigation existante conservée). Si aucune ligne sélectionnée, le pane affiche un placeholder.
5. **Split view CSS** : implémenté via CSS grid natif (`grid-template-columns: minmax(0,1fr) 400px`) sans lib externe
6. **Animations RunGraph** : les keyframes Framer Motion sont conservées ; seules les classes d'enrobage CSS changent

---

## Critères de succès

- [ ] L'interface est visuellement indistinguable du Orkestra-Mesh-template
- [ ] Toutes les actions métier fonctionnent identiquement à avant
- [ ] Aucun test existant n'est cassé par les changements
- [ ] La sidebar, le topbar et les pages principales sont cohérents
- [ ] Les badges sont en lowercase avec dot indicator
- [ ] Les formulaires utilisent les champs compacts 28px
- [ ] Le split view fonctionne sur les pages Agents et MCPs
- [ ] Geist est chargé correctement (pas de FOUT)
- [ ] Responsive desktop/tablette préservé
