<!--
Dosya Yolu: themes/ragnar-legacy/README.md
Amac: Turkuaz Ragnarok Online nostalji Beam theme and safety boundaries
Modul - Markdown theme documentation
Version: 0.1.0-candidate
Aciklama: Visual-only theme, based on known 2015 THOR patcher web assets
Bagimli Oldugu Katman: beam-ui/public/assets/ragnar-legacy.css | beam-ui/public/index.html
-->

# Turkuaz Nostalji — historical launcher-inspired theme

**Status: Visual QA only; no real client patch, game launch, or release.**

## Historical references, and what is *not* imported

- `LevelUpGT/RagnarokClient/patcher/web/legacy/index.html`: "Welcome to Ragnar Online",
  Overlook Dungeon, Daily Rewards, PvP/Rank feature announcements.
- `patcher/web/legacy/style.css`: light backgrounds, dark gray text, vintage
  navigation colors, rose-pink scrollbar accents (`#F1B9C4`) and orange hover (`#FF7D00`).
- `b1glord/ragnarokclientpatch/2015/beam/config.yml` and
  `2015/rpatchur/config.yml`: historic **Ragnar Ragnarok Online** brand,
  900x620 patcher window.
- **Do NOT import** `custom-login-theme.thor` into Beam: its 813
  items are *game-login assets* targeting the 2015 `ragnardata.grf`,
  not Beam frontend images. `skin-*.thor` packages install in-game UI skins.
- The resulting new `ragnar-legacy.css` is original CSS inspired by
  these historical cues. No old THOR binary assets, music, executable,
  2015 patchlist or client DLL are bundled in this theme.

## What is installed

The theme is shipped as an opt-in CSS file already included in the
Beam UI web assets:
`beam-ui/public/assets/ragnar-legacy.css`.

**The Turkuaz default theme stays selected** unless the config contains:

```yaml
app:
  name: "Turkuaz Ragnarok Online"
  window_title: "Turkuaz Ragnarok Online"
  server_name: "Turkuaz Ragnarok Online"

ui:
  theme: "ragnar-legacy"
```

The above is a **partial snippet only**. Do not overwrite the real
`config.yml` with it: keep every existing required app/patcher/ui/sso
key, network setting and region/channel guard unchanged. The theme is
independent of patch endpoints and does not set a game executable.

It works through `ui.theme` (opt-in enum `ragnar-legacy`), not
`ui.custom_css`: that field is not connected to a runtime stylesheet
in the existing Beam web UI. Unknown theme names leave the original
Beam colors/appearance unchanged.

## Safe local preview (no patcher binary needed)

On a checked out branch with this theme, open:

```powershell
Start-Process "file:///E:/Github/beam-patcher/beam-ui/public/index.html?theme=ragnar-legacy"
```

Or change the path to your local checkout; a dedicated QA worktree
is preferable. This **browser-only** query flag is ignored by Tauri.
It shows clearly marked *preview-only* historical announcement examples
and disables Play/Manual Patch/Settings/Cache operations. No update
channel, EXE or GRF is installed or written. The browser may still
load existing third-party font/icon resources from the upstream HTML.

Verify:
- Turkuaz Ragnarok Online title and cream/rose theme appear instead of the standard indigo layout.
- Legacy-derived mock historical announcements appear without a news API call.
- Preview-only banner and disabled patch/game controls are visible.
- Other theme/default config retains the existing Beam design.
- Layout fits Beam's current fixed 900x620 desktop viewport.

## Actual client / GRF deployment gate

**This visual theme is not a 20220406 runtime profile.** Real Beam
patcher profile must remain disabled until exact active Ragexe identity,
DATA.INI GRF order, safe isolated apply+rollback and protected loader
compatibility are proven. The 2022 feed in
`b1glord/ragnarokclientpatch/2022/` is still `ready: false`.

Do **not** copy the 2015 THOR packages or activate the public patchlist
to test a theme. Browser preview is the authorized visual QA phase.
