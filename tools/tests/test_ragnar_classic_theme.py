#!/usr/bin/env python3
# Dosya Yolu: tools/tests/test_ragnar_classic_theme.py
# Amac: Screenshot-derived THOR classic layout safe opt-in, isolation, and preview contract
# Modul - Python unittest offline-only source
# Version: 0.2.0-candidate
# Aciklama: No patch downloads, game execution, network, or GRF writes.
# Bagimli Oldugu Katman: beam-ui/public/index.html | assets/ragnar-classic.css
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "beam-ui/public/index.html").read_text("utf-8")
CSS = (ROOT / "beam-ui/public/assets/ragnar-classic.css").read_text("utf-8")
OLD = (ROOT / "beam-ui/public/assets/ragnar-legacy.css").read_text("utf-8")
DOC = (ROOT / "themes/ragnar-classic/README.md").read_text("utf-8")


class RagnarClassicThemeTests(unittest.TestCase):
    def test_three_themes_available_and_classic_is_explicit_opt_in(self):
        self.assertEqual(HTML.count('id="ragnar-classic-theme-css"'), 1)
        self.assertIn('href="assets/ragnar-classic.css" disabled>', HTML)
        self.assertIn('href="assets/ragnar-legacy.css" disabled>', HTML)
        self.assertIn("const classic = choice === 'ragnar-classic';", HTML)
        self.assertIn("if (classicSheet) classicSheet.disabled = !classic;", HTML)
        self.assertIn("if (sheet) sheet.disabled = !legacy;", HTML)
        self.assertIn("(config?.ui?.theme || 'default')", HTML)
        self.assertTrue(OLD)

    def test_classic_layout_matches_regions_without_rerouting_patch_commands(self):
        self.assertEqual(HTML.count('class="classic-ad-rail"'), 1)
        self.assertEqual(HTML.count('class="classic-ad-card '), 3)
        self.assertIn("grid-template-columns: 148px minmax(0, 1fr) 142px;", CSS)
        self.assertIn(".news-section-main", CSS)
        self.assertIn(".image-grid-section", CSS)
        self.assertIn(".grid-image-item:nth-child(n + 3) { display: none; }", CSS)
        self.assertIn(".progress-bar-container", CSS)
        self.assertIn(".btn-play-now", CSS)
        self.assertIn("onclick=\"handlePlayButton()\"", HTML)
        self.assertIn('id="theme-settings-open" onclick="openThemeSettings()"', HTML)
        self.assertIn("await openSetup(); // Preserve the existing native game setup action.", HTML)
        self.assertIn("onclick=\"manualPatch()\"", HTML)
        self.assertIn("onclick=\"resetCache()\"", HTML)

    def test_preview_is_browser_only_and_cannot_patch_or_start_game(self):
        self.assertIn("const previewClassic = !isTauri &&", HTML)
        self.assertIn("get('theme') === 'ragnar-classic'", HTML)
        self.assertIn("const isThemePreview = previewTheme || previewClassic || previewModern;", HTML)
        self.assertIn("classList.toggle('theme-preview-only', isThemePreview)", HTML)
        self.assertIn("if (isThemePreview) {", HTML)
        self.assertIn("'#play-button, .btn-action-small, #register-btn-main'", HTML)
        self.assertIn("if (button.id !== 'theme-settings-open') button.disabled = true", HTML)
        self.assertIn("if (previewClassic) return [", HTML)
        self.assertIn("url: 'about:blank'", HTML)
        self.assertIn("video_background_enabled: !isThemePreview", HTML)

    def test_distinct_classic_theme_is_scoped_and_cannot_change_default_beam(self):
        self.assertIn("body.theme-ragnar-classic {", CSS)
        self.assertIn("body.theme-ragnar-classic .top-grid {", CSS)
        self.assertIn("body.theme-ragnar-classic .news-section-main {", CSS)
        self.assertIn("body.theme-ragnar-classic .btn-play-now {", CSS)
        self.assertNotRegex(CSS, r"(?m)^\s*:root\s*{")
        self.assertNotRegex(CSS, r"(?m)^\s*body\s*{")
        self.assertEqual(CSS.count("{"), CSS.count("}"))
        self.assertIn("body.theme-ragnar-classic .classic-ad-rail {", CSS)

    def test_does_not_reuse_old_thor_patch_endpoints_or_fake_assets(self):
        for needle in (
            "raw.githubusercontent.com",
            "ragnar/Patcher/thor/Web/data",
            "patchlist.txt", "file_url=", "2015/data",
            "goatmmo.com", "client_exe_sha256", "data.grf",
            "custom-login-theme.thor",
        ):
            self.assertNotIn(needle, CSS)
        self.assertNotIn("padxp.jpg", CSS)
        self.assertNotIn("newsBG.jpg", CSS)
        self.assertIn("No old THOR binaries or patch lists are installed", DOC)

    def test_theme_keeps_old_styles_and_has_installation_instructions(self):
        self.assertIn("ragnar-classic", DOC)
        self.assertIn("ragnar-legacy", DOC)
        self.assertIn("ui:", DOC)
        self.assertIn("theme: ragnar-classic", DOC)
        self.assertIn("?theme=ragnar-classic", DOC)
        self.assertIn("No GRF or DATA.INI changes", DOC)

    def test_theme_uses_existing_beam_progress_and_news_for_real_ui(self):
        self.assertIn('id="progress-bar"', HTML)
        self.assertIn('id="progress-label"', HTML)
        self.assertIn('id="play-button"', HTML)
        self.assertIn('id="news-cards"', HTML)
        self.assertIn('id="image-grid"', HTML)
        self.assertIn("await invoke('check_patches_available')", HTML)
        self.assertIn("await invoke('start_patching')", HTML)
        self.assertNotIn("window.__TAURI__", CSS)


if __name__ == "__main__":
    unittest.main()
