# DX7 Voice Browser — project guide for Claude Code

This file tells you (Claude Code) how to keep all future work visually
consistent with the established design system. Read it before any UI change.

## Design system — non-negotiable

The visual system is defined in **`design_handoff_dx7_redesign/DESIGN_SYSTEM.md`**
and implemented as tokens in **`design_handoff_dx7_redesign/tokens.css`**.
A rendered reference of every component and the redesigned browse screen lives in
**`DX7 Browser — Design Review.dc.html`** (open in a browser).

**Rules:**
1. **Use tokens, never raw values.** Every color, font, space, radius and shadow
   must reference a `--ds-*` custom property. If you need a value that has no
   token, add a token to `tokens.css` first, then use it — do not hardcode hex,
   px font sizes, or one-off paddings.
2. **`tokens.css` loads before `static/style.css`** in `index.html`. Keep it that way.
3. **Two fonts only:** Space Grotesk (UI/display) and JetBrains Mono (all data:
   paths, positions, file names, counts, status). Never add a third family.
4. **One accent.** `--ds-signal` is the only brand/action color. Patch-type hues
   (`--ds-voice/perf/gen2`) are for data badges only. Red is destructive only.
5. **No glow, no glass, no orbs.** Do not add `text-shadow`/`box-shadow` halos,
   `backdrop-filter: blur()`, or animated background elements. One subtle shadow
   (`--ds-shadow` / `--ds-shadow-lg`) is the only elevation.
6. **Respect the scale.** Font sizes come from the type scale in the design system;
   never below 11px. Spacing snaps to the 4px grid (`--ds-1`…`--ds-8`).
7. **Accessibility:** every interactive element needs a visible focus ring
   (border `--ds-signal` + `0 0 0 3px --ds-signal-ring`); keep text contrast
   AA; `prefers-reduced-motion` is already handled in `tokens.css` — don't
   override it.

## When adding a new component
- Check `DESIGN_SYSTEM.md` §5 first — reuse an existing component spec.
- Match the patterns already in `static/style.css` (BEM-ish class names, the
  card/badge/pill/button conventions).
- If it's genuinely new, document it in `DESIGN_SYSTEM.md` §5 so the next
  session stays consistent.

## Architecture (don't break)
- Backend: FastAPI (`app.py`), SQLite (`database.py`), SysEx parser (`parser.py`).
- Frontend: vanilla ES2020 (`static/app.js`), no framework, no build step.
- All search/filter is **server-side**, capped at `RESULT_LIMIT = 200`. The
  frontend never loads the full dataset. Keep it that way for performance.
- Patch types: `"Voice"`, `"Performance"`, `"Gen 2 Extended"` — map each to its
  token set and FontAwesome icon (see design system §2).

## Migration status / next steps
The redesign is rolled out in this order (see DESIGN_SYSTEM.md §6):
1. **P0** — add `tokens.css`, swap fonts, delete glow/glass/orb rules. *(do first)*
2. **P1** — rebuild the Patch Explorer (command bar, pills, tree, results table).
3. **P2** — Cleanup tab, duplicate-files modal, toasts, empty states.
4. **A11y pass** — focus rings, keyboard nav, contrast audit.

Implement top-down; each step ships independently and the app keeps working.
