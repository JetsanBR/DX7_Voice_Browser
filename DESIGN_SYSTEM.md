# DX7 Voice Browser — Design System

> The single reference for how the app looks and behaves. Every new screen,
> component, and tweak must be built from the tokens and rules below. Per-page
> visual references live in each feature's `design_handoff_*/` folder (e.g.
> `design_handoff_voice_parameters/`) — open the `.dc.html` files there in a
> browser; they're the mockup a given section was built from, not a live
> reference for the whole app.

---

## 1. Principles

1. **Calm by default, loud on purpose.** One signal color carries primary
   action, selection, and brand. Everything else is neutral. If everything
   glows, nothing matters.
2. **Color means something.** Accent = action or selection. The three patch-type
   hues = data, never decoration. Red = destructive only.
3. **Name leads, metadata recedes.** In any list the human-readable label is the
   only element in UI-weight type; positions, paths, counts are quiet monospace.
4. **One elevation level.** Surfaces are solid and layered by lightness, not by
   blur or glow. Max one soft shadow (modals/app window only).
5. **Everything snaps to a 4px grid.** No one-off paddings or font sizes.

### Anti-patterns (these caused the "amateurish" feel — do not reintroduce)
- ❌ `text-shadow`/`box-shadow` glow on text, badges, borders, or buttons
- ❌ More than one accent color competing on a screen
- ❌ `backdrop-filter: blur()` glass cards; animated background orbs
- ❌ Orbitron, or any decorative/sci-fi display face
- ❌ Font sizes below **11px**; one-off sizes outside the scale

---

## 2. Color

All values are tokens in `tokens.css`. Reference tokens, never raw hex.

### Neutrals
| Token | Hex | Use |
|---|---|---|
| `--ds-bg` | `#0a0c0f` | App background |
| `--ds-sunken` | `#08090b` | Inputs, wells |
| `--ds-surface` | `#101317` | Panels, cards |
| `--ds-elevated` | `#161a1f` | Raised chips, pos pills |
| `--ds-elevated-2` | `#1c2228` | Row hover |
| `--ds-border` | `#242a31` | 1px hairlines |
| `--ds-border-2` | `#313942` | Stronger dividers / control outlines |

### Text
| Token | Hex | Use |
|---|---|---|
| `--ds-text` | `#eaedf0` | Titles, patch names |
| `--ds-text-2` | `#c0c7cd` | Body, cell text |
| `--ds-text-3` | `#97a1aa` | Descriptions |
| `--ds-text-4` | `#5f6870` | Captions, paths, placeholders |

### Signal (the one accent)
| Token | Hex | Use |
|---|---|---|
| `--ds-signal` | `#2fe3c2` | Primary button, selection, brand, focus |
| `--ds-signal-ink` | `#06231d` | Text/icon **on** a signal-filled surface |
| `--ds-signal-fill` | `rgba(47,227,194,.10)` | Tinted background |
| `--ds-signal-line` | `rgba(47,227,194,.30)` | Tinted border |
| `--ds-signal-ring` | `rgba(47,227,194,.12)` | Focus ring (3px) |

### Semantic — patch types (data only)
| Type | Color token | Fill | Line | Icon |
|---|---|---|---|---|
| Voice | `--ds-voice` `#2fe3c2` | `--ds-voice-fill` | `--ds-voice-line` | `fa-wave-square` |
| Performance | `--ds-perf` `#b58cff` | `--ds-perf-fill` | `--ds-perf-line` | `fa-layer-group` |
| Gen 2 Extended | `--ds-gen2` `#f5b860` | `--ds-gen2-fill` | `--ds-gen2-line` | `fa-sliders` |

### Status
`--ds-success #4fe09a` · `--ds-warning #f5b860` · `--ds-danger #ff5a6a`
(`--ds-danger-fill`, `--ds-danger-line` for destructive controls)

---

## 3. Typography

Two families only, **vendored locally** in `static/vendor/fonts/` (weights
400/500/600/700, latin subset). Do not load them from Google Fonts: the app ships
as a packaged desktop executable that must render correctly with no network.

```html
<link rel="stylesheet" href="vendor/fonts/fonts.css">
```

- **Space Grotesk** (`--ds-font-ui`) — display + all UI. Weights 400/500/600/700.
- **JetBrains Mono** (`--ds-font-mono`) — every piece of data: patch names in the
  table stay UI-weight, but positions, file names, folder paths, counts, status,
  and numeric readouts are mono.

### Scale (never invent sizes between these)
| Token | px / weight | Use |
|---|---|---|
| `--ds-fs-display` | 32 / 600 | Page / hero title |
| `--ds-fs-title` | 24 / 600 | Section title |
| `--ds-fs-h3` | 17 / 600 | Card / group heading |
| `--ds-fs-body` | 16 / 400 | Body copy |
| `--ds-fs-ui` | 14 / 500 | Buttons, labels, table cells |
| `--ds-fs-sm` | 13 | Dense UI, secondary buttons |
| `--ds-fs-cap` | 12 | Mono captions, pills, badges |
| `--ds-fs-micro` | 11 | Table-header eyebrows ONLY |

Letter-spacing: tighten display (`-.02em`); widen mono eyebrows/labels
(`.12–.18em`, uppercase).

---

## 4. Spacing, Radius, Elevation

- **Spacing (4px grid):** `--ds-1`=4 · `--ds-2`=8 · `--ds-3`=12 · `--ds-4`=16 ·
  `--ds-5`=24 · `--ds-6`=32 · `--ds-7`=48 · `--ds-8`=72.
  Card padding = `--ds-5`/`--ds-6`; table cell = `13px 16px`; control = `8–9px`.
- **Radius:** `--ds-r-ctrl`=6 (buttons/inputs/badges) · `--ds-r-card`=10 ·
  `--ds-r-panel`=14 (app window) · `--ds-r-pill`=999 (filter pills, count chips).
- **Elevation:** `--ds-shadow` for the rare raised element; `--ds-shadow-lg` for
  modals and the app window only. No glow shadows, ever.
- **Motion:** `--ds-dur` 150ms, `--ds-ease`. Honor `prefers-reduced-motion`
  (handled in `tokens.css`).

---

## 5. Components

### Buttons
- **Primary:** bg `--ds-signal`, text `--ds-signal-ink`, weight 600,
  padding `9px 16px`, radius `--ds-r-ctrl`. Hover: lift lightness ~6%. No glow.
- **Secondary/ghost:** transparent bg, `1px solid --ds-border-2`, text `--ds-text-2`.
- **Danger:** bg `--ds-danger-fill`, `1px solid --ds-danger-line`, text `--ds-danger`.
  Solid red fill only on hover/confirm.
- **Icon button:** 32×32, `1px solid --ds-border`, icon `--ds-text-4`; hover border
  `--ds-border-2`, icon `--ds-text-2`.

### Inputs
Sunken bg `--ds-sunken`, `1px solid --ds-border`, radius `--ds-r-ctrl`,
padding `8–9px 12px`, mono text for paths. **Focus:** border `--ds-signal` +
`box-shadow: 0 0 0 3px --ds-signal-ring`. Placeholder `--ds-text-4`.

### Type badge (table)
Mono, 11px, weight 600, `padding:3px 8px`, radius `--ds-r-ctrl`, icon 9px.
Color/fill/line from the patch-type token set. One size everywhere.

### Pills
- **Filter pill:** `--ds-r-pill`, mono 12px. Active = bg `--ds-signal` +
  `--ds-signal-ink`. Inactive = `1px solid --ds-border`, text `--ds-text-3`.
- **Count chip (Files):** `--ds-r-pill`. Duplicate (>1) = `--ds-signal-fill` +
  `--ds-signal-line` + `--ds-signal`, clickable. Single (=1) = `--ds-border`,
  `--ds-text-4`, static.
- **Position pill:** square `--ds-r-ctrl`, `--ds-elevated` bg, `--ds-border`,
  mono 12px `--ds-text-3`.

### Tabs
Underline style. Active = text `--ds-signal` + 2px bottom border `--ds-signal`.
Inactive = `--ds-text-4`, no border.

### Folder tree node
Mono 12.5px. Default text `--ds-text-3`, icon `--ds-text-4`. **Selected** =
bg `--ds-signal-fill`, text `--ds-signal`, 2px left border `--ds-signal` (solid
fill, **not** glow). Hover = bg `rgba(255,255,255,.03)`.

### Table
Header row bg `--ds-sunken`, eyebrow labels mono 11px `--ds-text-4` uppercase,
bottom border `--ds-border`. Cells `13px 16px`, bottom border `#15191d`.
Zebra: alternate `--ds-surface` / `--ds-bg`. Hover row → `--ds-elevated-2`.
Patch name = Space Grotesk 14px/600 `--ds-text`; all other cells mono.

### Surfaces
Card = `--ds-surface`, `1px solid --ds-border`, radius `--ds-r-card`. App window /
modal = radius `--ds-r-panel` + `--ds-shadow-lg`. **No `backdrop-filter`.**

---

## 6. Migration map (old → new)

| Remove | Replace with |
|---|---|
| Orbitron / Share Tech Mono / Inter | Space Grotesk + JetBrains Mono |
| `--accent-teal-glow`, all `text-shadow` glows | nothing (delete) |
| `.glow-orb-1/2` + `@keyframes orb-float` | delete; flat bg + one subtle radial |
| `backdrop-filter: blur(12px)` on `.card` | solid `--ds-surface` |
| LCD panel (4-row faux display) | inline status row (dot + count) in top bar |
| 5 simultaneous accents | one signal + semantic-only type/status colors |
| `0.52rem` / `0.62rem` font sizes | nearest scale step (≥11px) |

Loading `tokens.css` before `style.css` re-skins the app via the legacy aliases
immediately; then migrate `style.css` rules to `--ds-*` names and delete the
glow/glass/orb rules.

---

## 7. Voice Parameters Page
Full-page drill-down (`#section-detail` in `static/index.html`, rendered by the
`renderDetailHeader/Operators/Modulation/KeyMode/Controllers` functions in
`static/app.js`) showing every parameter of one voice. Source design:
`design_handoff_voice_parameters/Voice Parameters Page.dc.html`. Reached via a
"View Details" icon button (`.btn-reveal` + `fa-circle-info`) next to the reveal
button on voice rows and duplicate-files-modal rows; hidden for `Performance`
patches. A back button (`.detail-back-btn`) returns to whichever tab was active.

- **Outer card** (`.vd-card`): `--ds-bg` background, `1px solid --ds-border`,
  radius `--ds-r-panel`, `--ds-shadow-lg`.
- **Header band** (`.vd-header`): `--ds-surface` bg, bottom `--ds-border`, holds
  the brand mark, voice name + patch-type badge (reuses `.type-badge*`), a mono
  meta line, the algorithm mini-diagram, and a key-stat strip.
  - **Algorithm mini-diagram** (`.vd-alg-diagram` / `.vd-alg-node`): a fixed 2×3
    grid of 20×20px nodes; carrier operators get `.vd-alg-node-carrier`
    (`--ds-signal` fill/border/text), modulators stay neutral (`--ds-elevated` /
    `--ds-border-2` / `--ds-text-3`). Node positions are decorative and constant
    across algorithms — only the carrier/modulator coloring is data-driven (see
    `voice_params.DX7_ALGORITHMS` in the backend).
  - **Key-stat strip** (`.vd-key-stats` / `.vd-stat`): mono label (9px,
    `--ds-text-4`) over a bold mono value (`--ds-fs-sm`, `--ds-text-2`), cells
    separated by `--ds-border` verticals.
- **Section heading** (`.vd-section-heading`): mono 2-digit index in
  `--ds-signal` + Space Grotesk `<h2>` title, per numbered section (Operators /
  Modulation / Key Mode & Pitch Bend & Portamento / Controllers).
- **Operator tile** (`.op-tile`, 3-column `.op-grid`): `--ds-surface` card with
  title row (carrier/modulator dot `.op-dot`/`.op-dot-carrier`, feedback icon
  `.vd-fb-icon` shown only on the algorithm's feedback operator, role tag), an
  inset envelope graph (`.op-eg-panel`), an output-level meter
  (`.op-meter-track` / `.op-meter-fill`), numeric EG-R/EG-L rows, and a muted
  oscillator/scaling/sensitivity summary.
- **Inset graph panel** (`.op-eg-panel`, `.vd-inset-panel`): `--ds-sunken`
  background, `1px solid --ds-border`, radius 8px — houses the SVG envelope/LFO
  graphs drawn by `envSvg()` / `waveSvg()` in `app.js` (ported from the source
  design's React logic; same math, plain string-returning functions). Envelope
  stroke/fill use `--ds-signal` / `--ds-signal-fill-strong` for amplitude EGs and
  `--ds-perf` / `--ds-perf-fill-strong` for the Pitch EG (reuses the existing
  "Performance" violet hue for this one other purpose).
- **Card-with-title** (`.vd-card-inner`, used for LFO / Pitch EG / Key Mode /
  Pitch Bend & Portamento): `--ds-surface`, `1px solid --ds-border`, radius
  `--ds-r-card`; `.vd-card-title` icon + label row, `.vd-kv-grid`/`.vd-kv-stack`
  for label/value rows.
- **Controller table** (`.vd-controller-table`): compact `source × PM/AM/EG
  BIAS/extra` table, mono throughout, row top-borders `--ds-border`, source
  column bold `--ds-text-2`.
- New tokens added for this page (`static/tokens.css`): `--ds-signal-fill-strong`
  and `--ds-perf-fill-strong` — a slightly stronger (14%) tint of the existing
  signal/perf hues, used specifically for envelope-graph fill areas where the
  standard 10-12% fills were too faint against the sunken panel background.
