<!--
Dosya Yolu: themes/ragnar-classic/README.md
Amac: Document last-used Ragnar THOR launcher look and safe Beam theme QA
Modul - Markdown theme documentation
Version: 0.1.0-candidate
Aciklama: Pixel-region reference only; no legacy binaries, live patches or GRFs
Bagimli Oldugu Katman: beam-ui/public/index.html | assets/ragnar-classic.css
-->

# Turkuaz Klasik — historical THOR-inspired launcher layout

Status: **DRAFT / VISUAL QA ONLY**, opt-in Beam UI. Screenshot is user-provided
local launcher view of D:\Ragnarok; the matching executable itself is NOT
in the GitHub theme sources and has not been used as code.

## Evidence inventory — what exists and what does not

- The RagnarokClient repo has a *single* archived THOR web patcher set
  at `patcher/web/legacy` with `index.html`, `notice.html`, `style.css`,
  `main.ini`, and `slider/index.html` plus `slide.css` and old PikaChoose
  and jCarousel JavaScript. That slider has ~491x311 stage with thumbnails
  at right, which supports the screenshot-based central/right framing.
- However the old archived slider references `jquery.js`, `newsBG.jpg`,
  `padxp.jpg`, `padCards.png`, `padHTF.jpg` and others **not present** in
  the current tracked tree. None were fabricated or downloaded.
- Multiple theme-named THOR files do exist: `custom-login-theme.thor`,
  `skin-Phieti Renewal.thor`, and `skin-raPzLight.thor`. Those affect
  **in-game resources** and are NOT interchangeable launcher themes.
- User screenshot is the definitive reference for *last used* layout:
  white chrome/window, left three promo banners, dominant dark central
  content, two small right preview panes, two rainbow-toned lower tracks,
  social buttons, settings icons and a silver circular START button.
- Old banners and the TRRO vHost web text in the screenshot were specific
  external website content; the Beam theme creates original generic cards
  until user-provided matching art is available. No old third-party ads,
  dead web links or remote hosted HTML are embedded.

## Three independent styles

- `default`: Turkuaz Standart launcher (original Beam layout).
- `ragnar-legacy`: rose/cream old web palette, unchanged.
- `ragnar-classic`: screenshot-inspired **layout** and white/dark/teal
  design, close to the last-used legacy THOR launcher.

**Installation after review:** Keep the complete existing Beam `config.yml`
including mirrors, required fields and release gates. Change ONLY:

```yaml
ui:
  theme: ragnar-classic
```

This is a partial example, NOT a complete runnable configuration. Do NOT
copy a live 2015 THOR config to the 2022 client or enable patch publishing.

## Read-only browser preview

Checkout the PR to an isolated theme QA directory and open:

```powershell
$Root = 'E:\RagnarokMapcache-QA\beam-ragnar-theme-preview'
$File = (Resolve-Path "$Root\beam-ui\public\index.html").Path
$Url = 'file:///' + ($File -replace '\', '/') + '?theme=ragnar-classic'
Start-Process $Url
```

Browser preview uses offline example news and original CSS banner cards.
It disables Play, Manual Patch, Settings, Reset Cache and Register.
Browser preview query parameters have NO EFFECT in a real Tauri launcher.
Existing UI event handlers, backend patch events and progress percentage
remain untouched in Tauri mode; this is not a working 2022 patch profile.

Visual acceptance target: approximately 900x620 Beam window, left banner
rail 148px, right mini-panels 142px, dark central news area, lower
rainbow-inspired dual bars and circular START. Banner labels are examples
and can later be replaced by licensed server artwork.

## Release safety

**No GRF or DATA.INI changes**. No old THOR binaries or patch lists are installed.
The 2022 public BEAM feed remains locked (`ready: false`); no
`custom-maps.beam` binary was uploaded. The AES protected GRF experimental
format is still NOT an actual client-loadable encrypted tdata1.grf.
To test a real installer, first verify exact active 20220406 Ragexe
identity, client loader compatibility, target GRF policy and rollback
in an isolated game copy. Do not release the theme as a working patcher
until Tauri desktop QA and patcher safety checks pass.
