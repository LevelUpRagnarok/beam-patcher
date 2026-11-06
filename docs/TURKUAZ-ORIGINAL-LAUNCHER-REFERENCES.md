<!--
Dosya Yolu: REPO_ROOT/docs/TURKUAZ-ORIGINAL-LAUNCHER-REFERENCES.md
Amac: Kullanici tarafindan saglanan orijinal Klasik ve Modern launcher konseptlerini korumak
Modul - Markdown visual acceptance contract
Version: 1.0.0-candidate
Aciklama: Gorsel aidiyet, kaynak dosyalar, garanti ve QA/paket ayristirmasi
Bagimli Oldugu Katman: turkuaz-reference-restore.css | test_turkuaz_reference_restore.py
-->

# Turkuaz Ragnarok Online — original launcher art (DO NOT silently replace)

## Source and intent

The two supplied user image references are:
- `Ragnarok Online Renkli Oyun Başlatıcısı(1).png` — original white launcher with illustrated header, Ragnarok logo, castle carousel, colorful promotion rail and round Start control
- `Ragnarok Online Türkçe Oyun Başlatıcısı.png` — original navy/gold launcher with illustrated character hero, news panel, promotional cards and Start control

Earlier drafts reduced these images to generic CSS/vector scenery. That is **not acceptable as a visual restoration**. From this PR onward the user's reference artwork must remain in the frontend or be explicitly replaced with the owner's approval and a visual diff.

The source concept screenshots are **reference artwork**; they are not evidence of an actual game, real online status, official licensed promotional assets or a shipped Windows build. Production rights for logo/characters must be checked separately.

## Versioned assets from the supplied images

- `assets/turkuaz-user-classic-header.svg` — raster crop embedded within a standalone local SVG wrapper; original logo, characters and Poring in classic header
- `assets/turkuaz-user-classic-castle.svg` — isolated center castle scenery, with baked text and arrows visually cropped out
- `assets/turkuaz-user-modern-hero.svg` — user-provided modern concept's actual illustrated hero, not placeholder scenery
- `assets/turkuaz-user-adventurers.svg` — modern hero crop for image card
- `assets/turkuaz-user-poring.svg` — classic Poring crop, excludes fake window buttons

The assets contain only user-supplied decorative pixels. No external images, scripts, web requests, executable files, original client binary or fake game state are required. They are maintained locally under `beam-ui/public/assets/`. The original source screenshot is still available in the user's Library and should not be overwritten.

## Native UI protection

- `turkuaz-reference-restore.css` applies **only** to the Klasik and Modern themes (with a hidden inert markup banner otherwise).
- The HTML controls and native handlers for **play, manual patch, reset cache, theme settings** remain real independent elements; no whole-window screenshot overlay.
- Theme IDs and stored preference keys remain unchanged; the offline QA blocks real game and patch actions.
- Browser Chromium QA validates that the local image files load. It does **not** prove real Tauri/WebView2 pixel matching or gameplay.
- `tools/tests/test_turkuaz_reference_restore.py` pins the exact embedded source JPEG hashes to reject silent substitution.
- The original concept slider, status widgets and server feed are **not claimed functional** by the cropped art. They require separate data-backed implementation, not fake connectivity statistics.

## Visual acceptance before merging

Read and compare actual CI `default.png`, `ragnar-legacy.png`, `ragnar-classic.png`, `levelup-modern.png` screenshots with the user's two originals. Require visual review, no duplicate baked controls, legible real buttons, correct offline QA text and real artwork. Release remains subject to BURAK-INS-001, signed TurkuazInstaller and native client gates.
