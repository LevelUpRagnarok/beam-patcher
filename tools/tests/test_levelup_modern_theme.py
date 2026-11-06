#!/usr/bin/env python3
# Dosya Yolu: tools/tests/test_levelup_modern_theme.py
# Amac: Turkuaz Modern gorunumu ve offline QA guvenlik kontratini dogrular
# Modul - Python unittest / Node source behavior QA
# Version: 0.3.1-candidate
# Aciklama: CSS tema scope, browser-only preview, local preference ve native setup sinirlari
# Bagimli Oldugu Katman: beam-ui/public/index.html | assets/levelup-modern.css

import re
import runpy
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "beam-ui/public/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "beam-ui/public/assets/levelup-modern.css").read_text(encoding="utf-8")
DOC = (ROOT / "themes/levelup-modern/README.md").read_text(encoding="utf-8")


class LevelupModernThemeTests(unittest.TestCase):
    def test_four_themes_are_explicit_opt_in(self):
        for name in ("default", "ragnar-legacy", "ragnar-classic", "levelup-modern"):
            self.assertIn(f'<option value="{name}">', HTML)
        self.assertIn('id="levelup-modern-theme-css"', HTML)
        self.assertEqual(HTML.count('data-launcher-theme="'), 4)
        self.assertIn("option.setAttribute('aria-pressed',", HTML)
        self.assertIn('class="theme-gallery" role="group"', HTML)
        self.assertIn(".modern-nav, .modern-hero, .classic-ad-rail { display: none; }", HTML)
        self.assertIn('href="assets/levelup-modern.css" disabled>', HTML)
        self.assertIn("if (modernSheet) modernSheet.disabled = !modern", HTML)
        self.assertIn("const isThemePreview = previewTheme || previewClassic || previewModern;", HTML)
        self.assertIn("const previewModern = !isTauri &&", HTML)
        self.assertIn("document.body.classList.toggle('theme-levelup-modern', modern)", HTML)

    def test_settings_do_not_write_deployment_or_change_game_commands(self):
        self.assertIn('id="theme-settings-open" onclick="openThemeSettings()"', HTML)
        self.assertIn("window.localStorage.setItem(themePreferenceKey, theme)", HTML)
        self.assertIn("window.localStorage.getItem(themePreferenceKey)", HTML)
        self.assertIn("allowedLauncherThemes.includes(theme)", HTML)
        self.assertIn("await openSetup(); // Preserve the existing native game setup action.", HTML)
        self.assertIn("if (isThemePreview) return;", HTML)
        self.assertIn('onclick="handlePlayButton()"', HTML)
        self.assertIn('onclick="manualPatch()"', HTML)
        self.assertIn('onclick="resetCache()"', HTML)
        self.assertNotIn("invoke('set_theme'", HTML)
        self.assertNotIn("invoke('save_config'", HTML)

    def test_preview_disables_game_but_keeps_settings(self):
        self.assertIn("if (button.id !== 'theme-settings-open') button.disabled = true", HTML)
        self.assertIn("document.getElementById('theme-game-setup').disabled = true", HTML)
        self.assertIn("Offline theme preview - no patches or game launches", HTML)
        self.assertIn("if (previewModern) return [", HTML)
        self.assertIn("url: 'about:blank'", HTML)
        self.assertIn("const builtInGridImages = Object.freeze([", HTML)
        self.assertIn("img.src = new URL(imagePath, document.baseURI).href;", HTML)
        self.assertIn("img.onerror = null;", HTML)
        self.assertIn("tile?.classList.add('is-image-missing')", HTML)
        self.assertNotIn("https://via.placeholder.com", HTML)

    def test_styles_are_scoped_and_have_no_external_asset_requests(self):
        self.assertIn("body.theme-levelup-modern .modern-hero", CSS)
        self.assertIn("body.theme-levelup-modern .news-section-main", CSS)
        self.assertIn("body.theme-levelup-modern .btn-play-now", CSS)
        self.assertIn("body.theme-levelup-modern .progress-bar", CSS)
        self.assertNotRegex(CSS, r"(?m)^\s*(?:body|:root)\s*\{")
        self.assertNotIn("https://", CSS)
        self.assertEqual(CSS.count("{"), CSS.count("}"))
        self.assertIn("Tauri", DOC)
        self.assertIn("No licensed character artwork", DOC)

    def test_browser_qa_embedded_tauri_mock_has_valid_javascript(self):
        if not shutil.which("node"):
            self.skipTest("Node.js missing; CI validates mock syntax")
        globals_ = runpy.run_path(str(ROOT / "tools/QA-THEME-BROWSER.py"))
        mock_js = globals_["MOCK_TAURI"]
        check = subprocess.run(
            ["node", "--check", "-"], input=mock_js,
            text=True, capture_output=True, timeout=15, check=False
        )
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn("OFFLINE_QA_COMMAND_BLOCKED", mock_js)

    def test_inline_javascript_syntax_and_ui_behavior(self):
        if not shutil.which("node"):
            self.skipTest("Node.js missing; CI runner validates JS")
        scripts = re.findall(r"<script>\s*(.*?)</script>", HTML, flags=re.S)
        self.assertEqual(len(scripts), 1)
        check = subprocess.run(
            ["node", "--check", "-"],
            input=scripts[0], text=True, capture_output=True, timeout=15,
            check=False,
        )
        self.assertEqual(check.returncode, 0, check.stderr)
        probe = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync('beam-ui/public/index.html', 'utf8');
const a = source.indexOf('        const isTauri =');
const b = source.indexOf('        // Mock Tauri API', a);
assert(a !== -1 && b > a);
const logic = source.slice(a, b);
function scenario(tauri, query, preference) {
    const nodes = new Map();
    function node(id) {
        if (!nodes.has(id)) nodes.set(id, {id, disabled: false, hidden: true,
            value: '', textContent: '', dataset: {},
            attributes: {}, setAttribute(key, value) {this.attributes[key] = value;},
            focus() {}});
        return nodes.get(id);
    }
    const buttons = [node('play-button'), node('theme-settings-open'),
        node('manual-patch-button'), node('register-btn-main')];
    const gallery = ['default', 'ragnar-legacy', 'ragnar-classic', 'levelup-modern']
        .map(theme => {const element = node('choice-' + theme);
            element.dataset.launcherTheme = theme; return element;});
    const classes = {};
    const store = new Map(preference ? [['beam.launcher.theme.v1', preference]] : []);
    const doc = {activeElement: node('theme-settings-open'),
        body: {classList: {toggle(k,v) {classes[k] = v;}}},
        getElementById: node, querySelectorAll(selector) {
            return selector === '[data-launcher-theme]' ? gallery : buttons;
        }};
    const window = {location: {search: query}, localStorage: {
        getItem(k) {return store.get(k) ?? null;},
        setItem(k,v) {store.set(k,v);}
    }};
    if (tauri) window.__TAURI__ = {};
    const context = vm.createContext({window, document: doc, URLSearchParams, console});
    vm.runInContext(logic, context);
    return {context, node, classes, store};
}
let q = scenario(false, '?theme=levelup-modern', 'ragnar-legacy');
vm.runInContext("lastLoadedConfig = {ui:{theme:'ragnar-classic'}}; applyConfiguredTheme(lastLoadedConfig)", q.context);
assert.equal(q.classes['theme-levelup-modern'], true);
assert.equal(q.node('levelup-modern-theme-css').disabled, false);
assert.equal(q.node('choice-levelup-modern').attributes['aria-pressed'], 'true');
assert.equal(q.node('ragnar-classic-theme-css').disabled, true);
assert.equal(q.node('play-button').disabled, true);
assert.equal(q.node('theme-settings-open').disabled, false);
assert.equal(q.node('theme-game-setup').disabled, true);
vm.runInContext("openThemeSettings(); chooseLauncherTheme('ragnar-classic')", q.context);
assert.equal(q.node('theme-settings-modal').hidden, false);
assert.equal(q.classes['theme-ragnar-classic'], true);
assert.equal(q.node('choice-ragnar-classic').attributes['aria-pressed'], 'true');
assert.equal(q.store.get('beam.launcher.theme.v1'), 'ragnar-classic');
vm.runInContext("chooseLauncherTheme('invalid'); closeThemeSettings()", q.context);
assert.equal(q.store.get('beam.launcher.theme.v1'), 'ragnar-classic');
assert.equal(q.node('theme-settings-modal').hidden, true);
q = scenario(true, '?theme=levelup-modern', 'levelup-modern');
vm.runInContext("applyConfiguredTheme({ui:{theme:'ragnar-classic'}})", q.context);
assert.equal(q.classes['theme-levelup-modern'], true);
assert.equal(q.node('play-button').disabled, false);
assert.equal(q.node('theme-game-setup').disabled, false);
console.log('LEVELUP_THEME_BEHAVIOR_OK');
"""
        run = subprocess.run(
            ["node", "-"], input=probe, cwd=ROOT, text=True,
            capture_output=True, timeout=15, check=False
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("LEVELUP_THEME_BEHAVIOR_OK", run.stdout)


if __name__ == "__main__":
    unittest.main()
