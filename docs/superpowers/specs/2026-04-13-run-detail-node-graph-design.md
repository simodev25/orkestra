# Run Detail — Node Graph UI (2030 Design)

**Date:** 2026-04-13  
**Scope:** `frontend/src/app/test-lab/runs/[id]/page.tsx` + composants associés  
**Stack ajouté:** `@xyflow/react` (ReactFlow v12) + `framer-motion`

---

## 1. Objectif

Remplacer la timeline verticale d'événements de la page run detail par un **canvas interactif de type n8n** : chaque agent/phase devient un nœud draggable, les appels d'outils sont des chips positionnés sur les edges, un panel latéral affiche les détails du nœud sélectionné.

---

## 2. Périmètre

| Fichier | Action |
|---|---|
| `app/test-lab/runs/[id]/page.tsx` | Refonte complète |
| `components/test-lab/run-graph/RunGraph.tsx` | Nouveau — canvas ReactFlow |
| `components/test-lab/run-graph/nodes/AgentNode.tsx` | Nouveau — nœud agent custom |
| `components/test-lab/run-graph/nodes/OrchestratorNode.tsx` | Nouveau — nœud orchestrateur |
| `components/test-lab/run-graph/edges/AnimatedEdge.tsx` | Nouveau — edge avec animation |
| `components/test-lab/run-graph/ToolChip.tsx` | Nouveau — chip outil sur edge |
| `components/test-lab/run-graph/DetailPanel.tsx` | Nouveau — panel latéral |
| `components/test-lab/run-graph/RunTopbar.tsx` | Nouveau — topbar run |
| `lib/test-lab/graph-layout.ts` | Nouveau — calcul positions dagre |

Aucun autre fichier de l'app n'est modifié.

---

## 3. Architecture

```
page.tsx
  ├── RunTopbar          (breadcrumb, verdict pill, score, view toggle, RE-RUN)
  └── RunGraphView
        ├── ReactFlow canvas
        │     ├── OrchestratorNode   (1 nœud)
        │     ├── AgentNode[]        (N nœuds — un par phase/agent)
        │     ├── AnimatedEdge[]     (edges Bézier animés avec glow)
        │     └── ToolChipEdge[]     (chips positionnés sur chaque edge)
        └── DetailPanel             (panel droit, slide-in Framer Motion)
```

### Mapping événements → nœuds

La page reçoit déjà les 25 événements du run. On les transforme en nœuds + edges selon cette logique :

| Phase détectée | Type de nœud | Icône |
|---|---|---|
| `orchestrator` | `OrchestratorNode` | Soleil/hub (rayons) |
| `preparation` | `AgentNode` | Checklist |
| `runtime` + agent cible | `AgentNode` | Icône par agent_id (voir §4) |
| `assertions` | `AgentNode` | Bouclier avec check |
| `diagnostics` | `AgentNode` | Loupe |
| `verdict` / `report` | `AgentNode` | Médaille/trophée |

Les `orchestrator_tool_call` deviennent des **ToolChipEdge** positionnés au milieu du Bézier correspondant.

---

## 4. Icônes par agent_id

Un registre `AGENT_ICONS` dans `lib/test-lab/graph-layout.ts` mappe les `agent_id` connus vers une icône SVG Lucide et une couleur :

| agent_id | Icône Lucide | Couleur |
|---|---|---|
| `identity_resolution_agent` | `Fingerprint` | `#00d4ff` |
| `chat_agent` | `MessageSquare` | `#a78bfa` |
| `routing_agent` | `GitFork` | `#f59e0b` |
| `classifier_agent` | `Tag` | `#10b981` |
| `preparation_agent` | `ClipboardCheck` | `#c4b5fd` |
| `assertion_agent` | `ShieldCheck` | `#10b981` |
| `diagnostic_agent` | `FileSearch2` | `#f59e0b` |
| `verdict_agent` / `report` | `Award` | `#10b981` |
| *(fallback)* | `Bot` | `#71717a` |

---

## 5. Layout automatique (dagre)

On utilise **`@dagrejs/dagre`** (déjà dépendance de ReactFlow) pour calculer les positions des nœuds automatiquement à partir du graphe d'événements, avec :
- Direction : gauche → droite (`rankdir: 'LR'`)
- `ranksep: 120`, `nodesep: 60`
- Layout recalculé à chaque chargement (le run est immuable une fois terminé)

Cela évite des positions codées en dur et fonctionne pour n'importe quel run avec n'importe quel nombre de phases.

---

## 6. Interactions

### Canvas (ReactFlow)
- **Drag** nœud : positions libres après layout initial
- **Zoom** : molette / pinch, limites `[0.3, 2.0]`
- **Pan** : clic-glisser sur fond
- **Fit view** : bouton ⊡ en bas à droite
- **Minimap** : en bas à gauche, nœuds colorés par phase
- **Click nœud** : sélection → ouvre/met à jour DetailPanel

### Detail Panel (Framer Motion)
- **Slide-in** depuis la droite au premier clic (`x: 40 → 0, opacity: 0 → 1`)
- **Spring** physics : `stiffness: 300, damping: 28`
- **Sections** : stats (durée, score, statut), sortie JSON, liste d'événements, connexions, diagnostic lié
- **Fermeture** : clic sur ✕ ou clic sur le fond du canvas

### Animations CSS / Framer Motion
| Élément | Animation |
|---|---|
| Nœuds à l'entrée | `scale 0.85→1 + translateY 12→0`, stagger 80ms, spring |
| Edges | `stroke-dashoffset` animé en CSS (`@keyframes`) |
| Edge glow | `stroke-width: 3, blur: 2px, opacity: 0.3` superposé à l'edge principal |
| Verdict pill | Pulse (`box-shadow` 0→4px→0, 2s ease-in-out infinite) |
| Status dots | Pulse glow sur `completed` et `warning` |
| Tool chips | Fade-in avec délai staggeré |

---

## 7. TopBar

Remplace le header actuel. Contient de gauche à droite :

1. Logo hexagone Orkestra (lien `/`)
2. Breadcrumb : `TEST LAB / trun_79ea...` (tronqué 12 chars)
3. Verdict pill animé (`PASSED` / `FAILED` / `WARN`)
4. Score `100/100` mono
5. Durée, events count, date
6. Séparateur
7. Toggle `Graph | Timeline` (Timeline = vue actuelle conservée)
8. Bouton `Export` (download JSON du run)
9. Bouton `RE-RUN` (existant)

---

## 8. Vue Timeline (conservée)

Le toggle `Timeline` affiche l'ancienne vue (liste verticale d'événements). Elle reste accessible pour les utilisateurs qui préfèrent la vue linéaire. Implémenté via un state `view: 'graph' | 'timeline'` dans la page.

---

## 9. Dépendances à installer

```bash
cd frontend
npm install @xyflow/react framer-motion @dagrejs/dagre
npm install -D @types/dagre
```

| Package | Version cible | Taille |
|---|---|---|
| `@xyflow/react` | `^12.x` | ~180KB gzip |
| `framer-motion` | `^11.x` | ~50KB gzip |
| `@dagrejs/dagre` | `^0.8.x` | ~40KB gzip |

---

## 10. Ce qui NE change pas

- Tout le reste de l'app (sidebar, agents, MCP catalog, dashboard)
- La logique de fetch des données (`lib/test-lab/api.ts`)
- Le design system Tailwind existant (`ork-*` colors)
- Les types (`lib/test-lab/types.ts`)
- La vue Timeline (conservée en toggle)

---

## 11. Critères de succès

- [ ] Le graph se charge en < 300ms pour un run de 25 événements
- [ ] Chaque nœud est draggable, les edges suivent en temps réel
- [ ] Le panel latéral s'ouvre/ferme avec animation spring
- [ ] Chaque agent connu a son icône Lucide et sa couleur
- [ ] Le toggle Graph/Timeline fonctionne sans rechargement
- [ ] La page reste fonctionnelle si ReactFlow échoue à charger (fallback Timeline)
- [ ] Le layout dagre produit un graphe lisible pour des runs de 10 à 40 événements
