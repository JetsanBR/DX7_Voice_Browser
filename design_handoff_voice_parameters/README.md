# Handoff: Voice Parameters Page (DX7 Voice Browser)

## Overview
A full-page view that shows **every parameter of a single DX7 voice** on one screen, grouped into sensible sections, with the amplitude/pitch envelopes and LFO drawn graphically alongside their numeric values. This is the "2c — Instrument dashboard" direction that was chosen from the layout explorations.

The sample voice used throughout is **MELLOW HORN** (ROM1A, position 01). All parameter values in the mock are representative sample data — the real page must bind these to the selected voice.

## About the Design Files
The files in this bundle are **design references authored in HTML** — a prototype showing the intended look, structure, and the envelope-graph behaviour. They are **not** production code to copy verbatim. The task is to **recreate this design inside the DX7 Voice Browser's existing codebase** (a Python/Flask app serving static HTML/JS/CSS — see `p0_build/` and the local `DX7_Voice_Browser/` project) using its established patterns, the design-system tokens in `design_handoff_dx7_redesign/tokens.css`, and its component conventions. Where the app already has header/badge/algorithm-diagram components, reuse them rather than rebuilding.

The one piece worth porting closely is the **envelope-drawing function** (`envSvg`) and the LFO **waveform function** (`waveSvg`) in the reference file's logic class — they compute an accurate DX7 EG contour from rate/level data. See "The envelope graph" below.

## Fidelity
**High-fidelity.** Final colors, typography, spacing, and the graph rendering are all specified. Recreate the UI pixel-accurately using the codebase's existing libraries. Exact hex values, fonts, and sizes are listed under Design Tokens.

## Screens / Views

### Voice Parameters Page
- **Purpose**: Let a user inspect the complete synthesis definition of one voice at a glance — read relative operator loudness and envelope shapes visually, and drop to exact numbers when needed.
- **Layout**: A single centered card, **1200px wide**, dark surface, on a `#1a1d22` page (36px padding around it). Inside, a fixed header band followed by four numbered sections stacked vertically. Section horizontal padding is **30px**; each section separated by ~38px bottom margin.

#### Header band
- Full-width, `#101317` background, 1px bottom border `#1c2127`, padding `22px 30px`, `display:flex; align-items:center; gap:22px; flex-wrap:wrap`.
- **Left cluster**: a 38×38px rounded-8px teal (`#2fe3c2`) tile with "DX" in `#06231d` (JetBrains Mono 700 13px); beside it the voice name **MELLOW HORN** (Space Grotesk 600, 23px, `#eaedf0`, letter-spacing −0.01em) with a **VOICE** pill (teal text on 10%-teal fill, 1px 30%-teal border, wave-square icon), and a metadata line below (`ROM1A.SYX · POS 01 · ALG 2`, JetBrains Mono 10.5px `#5a636b`).
- **Algorithm mini-diagram**: an 80×56px box with six 20×20px operator nodes positioned to represent the algorithm; carrier nodes use teal fill/border/text (`rgba(47,227,194,0.12)` / `#2fe3c2`), modulators use `#161a1f` / `#313942` / `#97a1aa`. Thin `#313942` connector ticks. In the app, bind this to the real algorithm routing.
- **Key-stat strip** (pushed right, `border-left:1px solid #1c2127`): six stat cells, each `padding:2px 16px` with a `border-right:1px solid #1c2127`. Label = JetBrains Mono 9px `#5a636b` letter-spacing 0.1em; value = JetBrains Mono 13px 600 `#c7cdd2`. Stats: ALGORITHM 2, FEEDBACK 7, OSC SYNC On, TRANSPOSE C2, KEY MODE Poly, P.MOD SENS 2.

#### Section 01 — Operators
- Heading row: a JetBrains Mono 12px teal index (`01`, letter-spacing 0.1em) + Space Grotesk 600 19px `#eaedf0` title "Operators".
- **3-column grid**, 16px gap, one tile per operator (6 tiles). Tile: `#101317` bg, 1px `#242a31` border, radius 10px, padding `16px 18px`.
- Tile contents, top to bottom:
  1. **Title row**: a 6px dot (teal `#2fe3c2` for carriers, `#5a636b` for modulators) + `OP{n}` (Space Grotesk 600 14.5px). A feedback operator additionally shows a small `fa-rotate-right` teal icon. Right-aligned role tag (`Carrier` / `Modulator`, JetBrains Mono 9px `#5a636b`).
  2. **Envelope graph** in a `#0b0d10` panel (1px `#1c2127`, radius 8px, padding `6px 8px 2px`): the filled EG contour, teal stroke `#2fe3c2` 1.75px with `rgba(47,227,194,0.14)` fill, KEY ON / KEY OFF dashed guides. Height 74px, full width.
  3. **Output-level meter**: a label row (`OUTPUT LEVEL` JetBrains Mono 9.5px `#5a636b` left, value right `#c0c7cd`) above a 7px track (`#0b0d10`, 1px `#1c2127`, radius 4px) with a teal fill whose width = level/99 as a percentage.
  4. **EG-R / EG-L numeric rows** (JetBrains Mono 11px; label `#5a636b`, values `#c0c7cd`, right-aligned) — the four rates and four levels.
  5. A `#1c2127` divider, then three JetBrains Mono 10.5px `#79828a` summary lines: oscillator (`RATIO 1.00/1.00 · DET 0 · RS 2`), scaling (`NORMAL · BP … · L … · R …`), sensitivity (`KEY VEL 1 · AM SENS 0`).

#### Section 02 — Modulation
- Two-column grid, `1fr 1.5fr`, 16px gap.
- **LFO card** (left): title with `fa-square-wave` teal icon + "LFO", right-aligned `TRIANGLE` tag. A `#0b0d10` panel showing the **LFO waveform** drawn as a teal line (triangle in the sample). Below, a 2-column key/value grid of the LFO rows: Wave Triangle, Speed 30, Delay 0, Mode Multi, PM Depth 0, AM Depth 0, Key Sync Off.
- **Pitch EG card** (right): title with `fa-chart-line` icon in **violet `#b58cff`** + "Pitch EG", right-aligned `RANGE 8 oct`. A `#0b0d10` panel with the pitch envelope drawn as a **violet** filled contour (`#b58cff` stroke, `rgba(181,140,255,0.14)` fill), gridlines, R1–R4 / L1–L4 point labels, KEY ON/OFF. Below, a wrap row of JetBrains Mono 11.5px stats: RATES `99 · 95 · 95 · 99`, LEVELS `50 · 48 · 50 · 50`, VELOCITY Off, RATE SCL 0.

#### Section 03 — Key Mode, Pitch Bend & Portamento
- Two equal columns (`1fr 1fr`, 16px gap), each a `#101317` card (1px `#242a31`, radius 10px, padding `20px 22px`) with an icon+title header and key/value rows (label Space Grotesk-ish 13px `#97a1aa`, value JetBrains Mono 13px `#c0c7cd`).
  - **Key Mode** (`fa-object-group`): Assign Polyphonic, Unison Detune 0.
  - **Pitch Bend & Portamento** (`fa-arrows-left-right`, 2-column value grid): Bend Mode Normal, Bend Range 2 semi, Bend Step 0, Porta Mode Sus-Key P Retain, Porta Time 0, Porta Step 0, Random Pitch 2.

#### Section 04 — Controllers
- Two equal columns, each a `#101317` card containing a compact table (`source × PM / AM / EG-bias / extra`). Header cells JetBrains Mono 10px `#5a636b` right-aligned; rows separated by `1px #1c2127` top borders; source cell 600 `#c0c7cd`, values `#97a1aa`, all JetBrains Mono 13px.
  - **BC / AT / MW** (`fa-lungs`), value columns PM · AM · EG BIAS · P.BIAS: BC 0/0/0/+0, AT 0/0/63/+0, MW 31/0/0/—.
  - **FC1 / FC2 / MIDI** (`fa-sliders`), value columns PM · AM · EG BIAS · VOL: FC1 0/0/0/0, FC2 0/0/0/99, MIDI 0/0/0/0. Footnote `FC1 → CS1: Off` (JetBrains Mono 11px `#5a636b`).

## The envelope graph (most important behaviour to port)
DX7 amplitude envelopes are 4 rates + 4 levels. The graph draws the contour in this order: **start at L4 → R1 → L1 → R2 → L2 → R3 → L3 (sustain) → KEY OFF → R4 → back to L4.** Segment horizontal widths are proportional to `|ΔLevel| / rate` (faster rate = shorter/steeper segment), with the pre-sustain portion given ~54% of the width, sustain ~16%, release ~30%. Levels map to vertical position (0 at baseline, 99 at top). KEY ON and KEY OFF are marked with dashed vertical guides.

The reference implementation is the `envSvg(rates, levels, opts)` function in the logic class of `Voice Parameters Page.dc.html` (and `DX7 Voice Parameters Page - Layout Options.dc.html`). `waveSvg(shape, opts)` draws the LFO waveform (triangle/saw/square/sine). Both return inline SVG with `vector-effect:non-scaling-stroke` so strokes stay crisp at any width. **Reuse this math** rather than re-deriving it; only the styling (stroke color, fill, labels, gridlines) changes between contexts.

Variants of the same graph appear in the exploration file: `egLine` (stroke only), `egFill` (filled — used here in 2c), `egPanel` (silk-screen style with labels+grid, from option 2b). The Pitch EG has matching `svgLine` / `svgFill` / `svgPanel`.

## Interactions & Behavior
The prototype is static. In the real page:
- All values bind to the currently selected voice; switching voice re-renders every graph and number.
- Feedback icon shows only on the operator carrying feedback; carrier vs modulator (dot color + role tag) is derived from the algorithm.
- Output-level meter width = `level / 99`.
- No hover/click behaviour is specified for this view beyond what the app already applies to cards; keep it a read view unless product decides to make values editable.

## State Management
- **Selected voice** (id / bank / position) → drives all displayed values.
- Derived per render: operator role (carrier/modulator) and feedback flag from the algorithm number; envelope SVG paths from each operator's rates/levels; LFO path from LFO wave; meter widths from output levels.
- No data fetching beyond loading the voice record the rest of the app already provides.

## Design Tokens
Colors (also in `design_handoff_dx7_redesign/tokens.css` — prefer those variables):
- Page background `#1a1d22`
- Card surface (outer) `#0a0c0f`; section card `#101317`; inset graph panel `#0b0d10` (darkest `#08090b` used in 2b)
- Borders: `#242a31` (card), `#1c2127` (inner divider), `#313942` (diagram lines)
- Text: `#eaedf0` (headings), `#c7cdd2` / `#c0c7cd` (values), `#97a1aa` (labels), `#79828a` (muted), `#5a636b` (faint/mono captions)
- Accent teal (signal / carriers) `#2fe3c2`; on-teal ink `#06231d`; teal tints `rgba(47,227,194,0.10–0.14)`
- Pitch-EG violet `#b58cff`; violet fill `rgba(181,140,255,0.14)`
- Silk-screen stroke (2b panel graphs) `#d6dbe0`

Typography:
- Display/UI: **Space Grotesk** 400/500/600/700
- Numeric/mono: **JetBrains Mono** 400/500/600/700
- Section titles 19px/600; voice name 23px/600; body labels ~13px; mono values 11–13px; mono captions 9–11px letter-spacing 0.06–0.1em

Radius: cards 10px, outer card 14px, inset panels 8px, pills/tiles 6–8px, meter track 4px.
Shadow (outer card): `0 24px 60px -24px rgba(0,0,0,.7)`.
Icons: Font Awesome 6 (`fa-square-wave`, `fa-chart-line`, `fa-object-group`, `fa-arrows-left-right`, `fa-lungs`, `fa-sliders`, `fa-rotate-right`, `fa-wave-square`).

## Assets
- No raster assets. All graphics (algorithm diagram, envelopes, LFO, meters) are drawn with CSS/SVG.
- Fonts via Google Fonts; icons via Font Awesome 6 CDN. Use whatever the app already bundles.

## Source of truth for parameters
- `yamaha_dx7s_voice_parameters.csv` — every parameter, its group, description, and value range. Use this to validate grouping and value formatting.
- `dx7s_section4_voice_features.md` — the DX7s manual section describing voice features (context for what each parameter does).

## Files
- `Voice Parameters Page.dc.html` — **the chosen design (2c), isolated as a standalone page.** Open in a browser to see the target. Contains the `envSvg` / `waveSvg` implementations.
- `DX7 Voice Parameters Page - Layout Options.dc.html` — the full exploration (options 1a/1b/1c and 2a/2b/2c) for context and alternate graph treatments.
- `support.js` — runtime needed to open the `.dc.html` files locally.
- `yamaha_dx7s_voice_parameters.csv`, `dx7s_section4_voice_features.md` — parameter data + manual.
- `tokens.css`, `DESIGN_SYSTEM.md` — the existing DX7 Voice Browser design system (authoritative for colors/type/spacing).
