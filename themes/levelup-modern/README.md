<!--
Dosya Yolu: themes/levelup-modern/README.md
Amac: Turkuaz Modern Beam temasi gorunumu, secim akisi ve guvenli QA sinirlari
Modul - Markdown Theme Documentation
Version: 0.2.1-candidate
Aciklama: Bagimsiz secilebilir gorunume dair kaynak ve browser kontrol rehberi
Bagimli Oldugu Katman: beam-ui/public/index.html | assets/levelup-modern.css
-->

# Turkuaz Modern - selectable launcher theme

**Status:** DRAFT / offline visual QA; no production 2022 patch feed, game launch,
GRF installation, DATA.INI modification, installer or release approval.

## Available themes

| UI theme key | Appearance |
| --- | --- |
| `default` | Original Beam appearance |
| `ragnar-legacy` | 2015 THOR-inspired cream/rose |
| `ragnar-classic` | White/dark screenshot-referenced layout |
| `levelup-modern` | Blue/gold Turkuaz Ragnarok Online layout |

`levelup-modern` is a responsive CSS interpretation of the previously
previously approved LevelUp Games concept (historical source). It includes a castle-silhouette hero banner,
three activity tiles, an existing live news container, a patch progress bar
and original Play/pause/setup event handlers. The mockup's literal screenshot
is **not** used as a clickable background (its labels, player counts and progress
were illustrative). No licensed character artwork or fabricated server figures
are embedded. Source art can be added via a separate authorized asset QA step.

## Switching in Settings

The existing gear control opens **Gorunum ve Ayarlar**. Select any of four
themes in **Tema sec** and the UI redraws without reloading or patching.
The selection is saved as a device-local WebView localStorage preference
(`beam.launcher.theme.v1`) and is applied before the first rendered news load
on later starts. The UI reports explicitly if storage is unavailable.
New/unknown theme values are ignored; the deployment `config.yml` remains
unchanged. A separate **Oyun Ayarlari** button retains the existing
`open_setup` command for the installed client.

A clean profile without a saved preference continues to respect the
deployment's original `ui.theme` value. Device-local storage can be cleared
by the OS/WebView profile reset; it is **not** synced between computers.

## Visual theme gallery

The Settings dialog now shows four color previews (swatch cards) with the
same options as the accessible select element. The selected card exposes
`aria-pressed=true`. Choosing a card updates the actual Beam layout immediately
and saves the local preference. **Oyun Ayarlari** still calls the original
native `open_setup` command; theme choice never changes patch settings.

## Repeatable browser screenshot QA

The `chromium-theme-smoke` GitHub Actions job uses pinned Playwright/Chromium
to open the **real** `beam-ui/public/index.html` at a 900x620 viewport.
It supplies inert local Tauri command doubles, verifies each clickable theme
card, checks preference restoration after page reload, and uploads four
short-lived PNG screenshots plus a SHA-256 evidence report.

```powershell
python -m pip install playwright==1.56.0
# Use an installed Chrome/Chromium browser
python tools/QA-THEME-BROWSER.py --output-dir build/theme-visual-qa
```

The command is repo-root independent; the script resolves its own location.
Its output directory must be empty; previous QA proof is never overwritten.
The browser blocks outgoing HTTP requests, and no real update/game command
is allowed. This is **Chromium browser QA**, not Windows WebView2 or native
Tauri GUI acceptance. Images are available as a temporary Actions artifact;
no release is created.

## Offline read-only preview

Checkout `feat/ragnar-legacy-beam-theme-qa-20261022` as a separate QA copy,
then open this file in a browser:

```text
beam-ui/public/index.html?theme=levelup-modern
```

This preview uses offline sample news and CSS artwork. It disables game launch,
manual patch, cache reset, registration and native game setup. The appearance
settings stay enabled for comparing all four themes. The query parameter does
not override a theme in a real Tauri application.

## Test boundary

Source and JavaScript syntax checks run in the `ragnar-legacy-theme-qa.yml`
workflow. Visual acceptance on real Windows Tauri at the pinned head and
personal preference persistence across an actual app restart remain separate
manual QA gates. Successful source tests do not authorize production release.
