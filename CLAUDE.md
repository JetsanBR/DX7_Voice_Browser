# DX7 Voice Browser — project guide for Claude Code

This file tells you (Claude Code) how to keep all future work visually
consistent with the established design system. Read it before any UI change.

## Design system — non-negotiable

The visual system is defined in **`DESIGN_SYSTEM.md`** (repo root) and
implemented as tokens in **`static/tokens.css`**. Design handoff folders named
`design_handoff_*/` (e.g. `design_handoff_voice_parameters/`) contain
per-feature mockups and specs used to build a specific page — they are
reference material for that feature's build, not the live source of truth;
once a feature ships, `DESIGN_SYSTEM.md` and `static/tokens.css` are.

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

## Packaging (don't break)

The app ships to end users as a single portable Windows `.exe`
(`pyinstaller dx7_voice_browser.spec` → `dist\DX7VoiceBrowser.exe`, ~19 MB), which
opens a native pywebview window. There are now **two entry points over the same
code** — `main.py` (desktop) and `app:app` (dev, via `start.ps1`). Change one and
check the other still works.

Four invariants that a frozen build breaks the moment you violate them:

1. **Never use a relative path for a resource or the database.** Go through
   `paths.py`: `resource_path("static")` for bundled read-only assets,
   `user_data_dir()` / `db_path()` for anything writable. Under a onefile build
   the CWD is wherever the user double-clicked, and bundled assets live in an
   ephemeral `%TEMP%\_MEIxxxxxx` directory that is deleted on exit — so an
   absolute path into it must never be written to the database.
2. **No CDN links in `static/index.html`.** Fonts and Font Awesome are vendored
   in `static/vendor/` so the packaged app works offline; a CDN `<link>` renders
   as blank icons for anyone offline. Keep `fontawesome/css/` and
   `fontawesome/webfonts/` as siblings (the CSS uses `url(../webfonts/…)`), and
   don't strip the attribution comment from `all.min.css`. Regenerate with
   `tools/fetch_vendor.ps1`. Font Awesome **Free** only — `fa-radar` and
   `fa-square-wave` are Pro and silently render as nothing.
3. **Assume no stdout.** A `--windowed` build has `sys.stdout`/`stderr` set to
   `None`. Log via the `logging` module (it goes to a file), never `print()`, and
   pass explicit `DEVNULL` handles to every `subprocess` call.
4. **Scanning is destructive** — `run_background_scan()` calls
   `database.clear_db()` first. Anything that triggers a scan automatically (the
   first-run demo seeding does) must first confirm the database is empty, or it
   will silently destroy a user's index.

## Architecture (don't break)
- Backend: FastAPI (`app.py`), SQLite (`database.py`).
- SysEx byte access is split into two reusable layers — keep it that way for
  future features (export, editing, comparison, etc.):
  - `parser.py` — finds voices/performances inside a `.syx` file. Its public
    `parse_syx_file(path)` returns name/position/patch_type only (unchanged
    contract, used by the scan flow); `extract_voice_blocks(path)` returns the
    same list in the same order but also keeps the raw 128-byte VMEM /
    35-byte AMEM byte blocks for full decoding. Both are built from one shared
    internal scan (`_scan_all_patches`) — don't reimplement the F0/43 message
    scanning loop a third time; add to that shared function instead.
  - `voice_params.py` — pure byte-to-parameters decoders (`decode_core_voice`,
    `decode_additional_voice`, `build_voice_parameters`, `DX7_ALGORITHMS`). No
    file I/O; takes raw bytes from `parser.py`, returns structured dicts. This
    is the module any new voice-data feature should build on.
- Frontend: vanilla ES2020 (`static/app.js`), no framework, no build step. The
  Voice Parameters page is an in-page view (`#section-detail`, toggled like
  the Explorer/Cleanup tabs) rather than a separate route — follow that
  pattern for any future full-page drill-down rather than adding a router.
- All search/filter is **server-side**, capped at `RESULT_LIMIT = 200`. The
  frontend never loads the full dataset. Keep it that way for performance.
- Patch types: `"Voice"`, `"Performance"`, `"Gen 2 Extended"` — map each to its
  token set and FontAwesome icon (see design system §2). `"Performance"` isn't
  a single voice (it's a combination of up to 4 voice slots) — don't add
  per-voice-parameter features to it without a product decision first.

## Migration status / next steps
The dark, token-driven redesign (DESIGN_SYSTEM.md §1–6: tokens, Patch Explorer,
Cleanup tab, duplicate-files modal, toasts, empty states) has **shipped** —
`tokens.css` already loads in `static/index.html` and `style.css` already
consumes `--ds-*` tokens throughout. Don't restart that rollout; just keep new
work on tokens per the rules above.

The **Voice Parameters page** (DESIGN_SYSTEM.md §7) has also shipped: a
per-voice "View Details" button opens a full-page breakdown of every operator,
envelope, LFO, and (Gen 2 Extended only) key mode/pitch bend/controller
setting. See `voice_params.py` and the "Voice Parameters Flow" section of
`README.md` for how it's wired end to end.

**Desktop packaging** has shipped too — see the Packaging section above.
`main.py` + `dx7_voice_browser.spec` produce the portable `.exe`; fonts and icons
are vendored in `static/vendor/`; all paths route through `paths.py`.

Open follow-ups, not yet done:
- **Code signing** — the `.exe` is unsigned, so SmartScreen shows "Windows
  protected your PC" on first run and users must click *More info → Run anyway*.
  Only an Authenticode certificate removes that (an EV cert bypasses SmartScreen
  immediately; an OV cert still has to accumulate reputation).
- **Onefile cold start** — the bundle re-extracts ~19 MB to `%TEMP%` on every
  launch (~1.7 s here, slower on a cold disk or with aggressive AV) with no
  feedback. If that gets worse on real users' machines, switching the spec to
  onedir-in-a-zip makes launch instant and trips AV heuristics less; it's a
  one-flag change but gives up the single-file property.
- **Deleting to the Recycle Bin** — the Cleanup tab still uses `shutil.rmtree`,
  which is permanent. That was an acceptable risk for a developer-run script; it
  is a sharper edge now that non-technical users get the app. `send2trash` would
  make it recoverable.
- **A11y pass** — focus rings, keyboard nav, contrast audit across the whole app.
- **`DX7_ALGORITHMS` verification** — the carrier/modulator/feedback-operator
  table in `voice_params.py` is reconstructed from general DX7 knowledge, not
  the sysex byte spec (which never stores per-algorithm routing). Only
  algorithm 2 is cross-checked; spot-check the rest against the official
  Yamaha algorithm chart before trusting it beyond the Voice Parameters page's
  decorative operator coloring.
