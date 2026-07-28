---
name: rheinwerk-mes-design
description: Core design skill for the Rheinwerk MES platform UI. Apply whenever building, modifying, or reviewing any screen, page, component, or front-end asset in the rheinwerk-mes-core repository. Encodes the design system, interaction rules, and adoption principles that let three very different audiences — shop-floor operators who have used legacy terminals for decades, planners and QC professionals, and business stakeholders — fully embrace one modern application.
---

# Rheinwerk MES — Core Design Skill

## Design thesis: modern, not novel

This UI replaces systems people have trusted for twenty years. Adoption fails when a new interface asks veterans to relearn what they already know; it succeeds when the new screen is *obviously better at the same job*. Every design decision follows one rule: **change the surface, never the mental model.** Same vocabulary, same order states, same keyboard reflexes — rendered with modern clarity, speed, and polish. The person who ran the Qcadoo terminal for a decade should feel competent in the first five minutes; the graduate engineer should never suspect they are using legacy software.

Corollary: spend novelty in exactly one place (the Trace Ribbon, below). Everything else is quiet, disciplined, and dense with information.

## The three audiences (design for all, every screen)

**Veteran operators and warehouse staff** — work standing, at arm's length, often gloved, under plant lighting, interrupted constantly. They value density, keyboard/scanner speed, and predictability. They distrust animation, hidden data, and anything that moves a button.

**Professional planners, technologists, QC** — work seated with keyboard and large screens. They live in grids and queues; they measure the UI in keystrokes per task. Progressive disclosure insults them — show the data.

**Business and management** — occasional users. They need orientation, plain language, and drill-down from summary to evidence without training.

Rule of thumb: operators get *density + size*, professionals get *density + speed*, business gets *clarity + narrative*. Never design a screen for only one of them; decide which is primary and keep the others functional.

## Design tokens

### Color — "Rheinwerk Petrol" palette
Industrial, calm, chemical-works heritage. Semantic colors are *reserved*: status meaning is sacred to people who have watched these colors for decades, so they are never used decoratively.

- `--rw-petrol-900: #0E3038` — primary surface accents, nav, headers
- `--rw-petrol-600: #16606E` — interactive elements, links, focus
- `--rw-graphite-900: #1D2226` — primary text
- `--rw-graphite-500: #5A6670` — secondary text, borders
- `--rw-paper: #F6F7F5` — app background (low-glare, not pure white)
- `--rw-surface: #FFFFFF` — cards, tables, panels
- `--rw-signal-amber: #C77D0A` — warnings, holds, expiring batches
- `--rw-signal-red: #B4232A` — blocked, failed QC, stop states
- `--rw-signal-green: #1E7A46` — released, passed, completed
- `--rw-signal-blue: #1F5FA8` — informational, in-progress

Status is **never color-only**: every status pill pairs color + icon + label (color-blind safe, print safe, plant-lighting safe). Contrast minimum WCAG AA everywhere; AAA for shop-floor text.

### Typography
- **UI and data:** `Inter` (or system grotesk fallback) — legible at density, excellent numerals.
- **Identifiers:** `IBM Plex Mono` for batch numbers, order codes, lot IDs, tag values — always mono, always tabular, so codes align in columns and are scannable/read-aloud safe over a plant radio.
- **Display (sparingly):** `Inter` at heavy weight for page titles and the Trace Ribbon header. No decorative faces anywhere — this is an instrument, not a brochure.
- Numerals in tables are always `font-variant-numeric: tabular-nums`.

### Density modes (a first-class token, not a preference buried in settings)
- **Desk mode** (default): 13–14px base, 32px row height, full data density.
- **Terminal mode** (shop floor): 16–18px base, 48px minimum touch targets, high-contrast, larger status pills, reduced chrome. Auto-selected by station profile; manually switchable in one tap.
- Both modes render the *same information* — terminal mode enlarges, it never hides.

## Layout patterns (use these; do not invent new shells per screen)

1. **Work Queue → Detail**: the universal professional pattern. Left: dense, filterable, keyboard-navigable queue (orders, inspections, batches). Right: full detail with actions in a fixed action bar. State never lost on navigation.
2. **Terminal Card**: shop-floor pattern. One task at a time, giant primary action, scanner field permanently focused, current order/operation always visible in the header. Everything reachable with scanner + four keys (arrows, Enter, Esc).
3. **Command Dashboard**: business pattern. Plain-language KPI tiles (words, then numbers) that drill straight into the professional queue views — the dashboard is a lens on the same data, never a separate report world.
4. **The Trace Ribbon (signature element)**: batch genealogy rendered as a horizontal flowing ribbon — supplier batches on the left, the batch in focus center, downstream products right; blocked branches rendered in signal-red with a hard visual "break." Interactive (expand levels, jump to any batch), printable, and identical in the CoA and recall views. This is the one screen that should make a 20-year veteran say "we could never see this before." It is the emotional core of adoption; execute it superbly and keep everything else restrained.

## Interaction rules (non-negotiable)

- **Keyboard-first parity.** Every action a mouse can do has a keyboard path. Preserve legacy muscle memory where it exists: Enter confirms, Esc cancels, arrow keys move rows. Publish a shortcut sheet per screen (`?` opens it).
- **Scanner is a first-class input.** On any screen expecting material, batch, or order identification, an invisible always-focused scan field accepts barcode input; a successful scan gives a full-row visual + audible confirmation.
- **State names are law.** Order and batch states use the exact vocabulary carried from the consolidation glossary (Pending, Accepted, In Progress, Completed, Blocked…). Never introduce synonyms; the words are part of the plant's spoken language.
- **Hard gates look hard.** When an execution gate blocks an action (material availability, batch evidence, expiry), the UI states *which rule*, *which record*, and *what resolves it* — in the interface's voice, no apology, no vague error. Gate refusals are modal and logged, never a dismissable toast: these are compliance moments.
- **Legacy bridge affordance.** During the migration programme, any field mapped from a legacy system offers its old name on hover/long-press ("was: Technology → now: Recipe"). Removable by feature flag after cutover; invaluable during it.
- **No dead air.** Every action under 100ms feels instant; anything longer shows progress on the control itself. Optimistic UI only for non-compliance actions — gated actions always confirm from the server.
- **Motion budget: near zero.** Micro-transitions ≤150ms for state changes only. No entrance animations, no parallax, nothing ambient. Respect `prefers-reduced-motion` by default posture, not as an exception.
- **Nothing hides on desktop.** No hamburger menus, no hover-only actions, no data behind "show more" in professional views. Density is respect.

## Content and language

Write from the operator's side of the screen. Controls say what happens: "Release order," "Block batch," "Record output" — the same verb persists through confirmation and audit log. Empty queues direct ("No inspections due — next scheduled 14:00"), never decorate. Business surfaces translate, professional surfaces do not: a KPI tile may say "Batches on hold," but the queue behind it says `blockedForQualityControl` semantics with full precision. German-first i18n discipline: all strings externalized, no concatenation, dates/units locale-correct (this plant thinks in DD.MM.YYYY and kg).

## Component rules

- **Tables:** sticky headers, resizable columns, saved views per user, mono identifiers, right-aligned tabular numerals, inline status pills, row-level keyboard actions. Virtualized beyond 200 rows.
- **Status pill:** icon + label + color, one component everywhere; the pill *is* the status API of the UI.
- **Forms:** label above field, units suffixed inside the input, validation inline at the field on blur and summarized on submit; never lose entered data.
- **Batch chip:** mono ID + status dot + one-click to Trace Ribbon; used anywhere a batch is mentioned, so traceability is always one action away.

## Anti-patterns (reject in review)

Consumer-app whimsy (mascots, confetti, playful microcopy) · low-density card walls where a table belongs · color-only status · toast-only errors for gated/compliance actions · icon-only buttons for destructive actions · hiding legacy users' data behind progressive disclosure · renaming states for "friendliness" · unannounced layout changes between releases (position stability is a feature; moving a button costs a retraining).

## Definition of done (every screen)

Renders correctly in Desk and Terminal modes · complete keyboard path + shortcut sheet · scanner path where identification is expected · WCAG AA contrast, visible focus, 48px targets in Terminal mode · status pills conform · state vocabulary matches the glossary · gate refusals name rule/record/resolution · strings externalized · screenshot reviewed against this skill before merge.
