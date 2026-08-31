# Vendored front-end assets

These files were served from CDNs (Google Fonts and cdnjs) until the app was
packaged as a desktop application. A packaged app must work offline, and every
control in the UI is a Font Awesome glyph — without local copies the whole
interface renders as blank boxes in fallback fonts.

**Do not edit anything in this directory by hand.** Regenerate it with
`tools/fetch_vendor.ps1` from the repo root.

## Contents

| Path | Version | Source |
|---|---|---|
| `fontawesome/css/all.min.css` | Font Awesome Free 6.4.0 | `use.fontawesome.com/releases/v6.4.0/fontawesome-free-6.4.0-web.zip` |
| `fontawesome/webfonts/fa-solid-900.woff2` | " | " |
| `fontawesome/webfonts/fa-regular-400.woff2` | " | " |
| `fonts/space-grotesk-latin-*.woff2` | Space Grotesk v22, latin subset | `gwfh.mranftl.com` |
| `fonts/jetbrains-mono-latin-*.woff2` | JetBrains Mono v24, latin subset | `gwfh.mranftl.com` |

Font Awesome zip SHA256:
`55A75EBA37B67ECC9F715291B2B0D121FBF41A425044590177A25F236DA9813B`

## Two things that will break if you rearrange this

1. **`fontawesome/css/` and `fontawesome/webfonts/` must stay siblings.**
   `all.min.css` references its fonts as `url(../webfonts/…)`. Flattening the
   directory breaks every icon.
2. **Do not minify or reformat `all.min.css`.** Its leading
   `/*! Font Awesome Free 6.4.0 by @fontawesome … */` comment is the required
   CC BY 4.0 attribution.

## What was deliberately left out

- `fa-brands-400.*` (~108 KB) — no `.fa-brands`/`.fab` class appears anywhere in
  `index.html` or `app.js`. Its `@font-face` is declared but never instantiated,
  so the browser never requests it.
- `fa-v4compatibility.*` — legacy v4 icon-name shims, unused here.
- All `.ttf` files (~650 KB) — second in each `src:` list, only reached if woff2
  is unsupported. The app renders in WebView2 (Chromium), where woff2 always wins.

`fa-solid-900` and `fa-regular-400` are both kept: the UI uses 52 `fa-solid` and
6 `fa-regular` classes.

## Licensing

- **Space Grotesk** © Florian Karsten — SIL OFL 1.1 (`fonts/OFL-SpaceGrotesk.txt`)
- **JetBrains Mono** © JetBrains s.r.o. — SIL OFL 1.1 (`fonts/OFL-JetBrainsMono.txt`)
- **Font Awesome Free 6.4.0** — icons CC BY 4.0, fonts SIL OFL 1.1, code MIT
  (`fontawesome/LICENSE.txt`)

The OFL requires the license text to ship alongside the fonts, which is why the
`.txt` files live here and are bundled into the executable. It also reserves the
font names: do not rename or re-subset these files and keep the original name.
