#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/tests/test_turkuaz_premium_theme.py
# Amac: Dort tema icin ozgun, gecerli ve lokal Turkuaz goruntu sozlesmesi
# Modul - Python unittest
# Version: 1.0.0-candidate
# Aciklama: SVG parser ve CSP-guvenli yerel artwork; onceki tema kimliklerini korur
# Bagimli Oldugu Katman: beam-ui/public/index.html | turkuaz-premium.css | QA-THEME-BROWSER.py

from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "beam-ui/public/assets"
HTML = (ROOT / "beam-ui/public/index.html").read_text(encoding="utf-8")
CSS = (ASSETS / "turkuaz-premium.css").read_text(encoding="utf-8")
QA = (ROOT / "tools/QA-THEME-BROWSER.py").read_text(encoding="utf-8")
PROFILE = (ROOT / "installer/windows/config.qa.yml").read_text(encoding="utf-8")
FILES = (
    "turkuaz-castle.svg", "turkuaz-skycity.svg",
    "turkuaz-poring.svg", "turkuaz-dungeon.svg",
)
THEMES = ("default", "ragnar-legacy", "ragnar-classic", "levelup-modern")


class TurkuazPremiumThemeTests(unittest.TestCase):
    def test_four_distinct_local_artworks_are_valid_svg(self):
        contents = []
        for filename in FILES:
            file = ASSETS / filename
            self.assertTrue(file.is_file(), filename)
            payload = file.read_text(encoding="utf-8")
            svg = ET.fromstring(payload)
            self.assertEqual(svg.tag, "{http://www.w3.org/2000/svg}svg", filename)
            self.assertEqual(svg.attrib.get("viewBox", "").split()[:2], ["0", "0"])
            self.assertGreater(len(payload), 2500, filename)
            for forbidden in ("<script", "<foreignObject", "<image", "https://", "http://",
                              "javascript:", "data:", "onload=", "onclick="):
                # SVG root XML namespace URL is a required exception.
                if forbidden in ("https://", "http://"):
                    self.assertNotIn(forbidden, payload.replace("http://www.w3.org/2000/svg", ""))
                else:
                    self.assertNotIn(forbidden, payload)
            contents.append(payload)
        self.assertEqual(len(set(contents)), len(FILES), "Artwork must not repeat the same placeholder")
        # Original vector concepts remain optional; default cards use user references.
        selected = (
            "turkuaz-user-classic-castle.svg",
            "turkuaz-user-adventurers.svg",
            "turkuaz-user-poring.svg",
            "turkuaz-dungeon.svg",
        )
        for name in selected:
            self.assertIn("assets/" + name, HTML)
            self.assertIn("assets/" + name, QA)
            self.assertIn("assets/" + name, PROFILE)

    def test_premium_styles_are_scoped_and_keep_native_handlers(self):
        self.assertIn('href="assets/turkuaz-premium.css"', HTML)
        for theme in THEMES[1:]:
            self.assertIn("body.theme-" + theme, CSS)
        self.assertIn("body:not(.theme-ragnar-legacy)", CSS)
        self.assertIn("url('turkuaz-castle.svg')", CSS)
        self.assertIn("url('turkuaz-poring.svg')", CSS)
        self.assertIn("url('turkuaz-dungeon.svg')", CSS)
        self.assertNotIn("@import", CSS)
        self.assertNotIn("https://", CSS)
        self.assertNotIn("http://", CSS)
        self.assertEqual(CSS.count("{"), CSS.count("}"))
        for action in ('onclick="handlePlayButton()"', 'onclick="manualPatch()"',
                       'onclick="resetCache()"', 'onclick="openThemeSettings()"'):
            self.assertIn(action, HTML)
        self.assertIn("'beam.launcher.theme.v1'", HTML)
        self.assertIn("isThemePreview", HTML)
        self.assertIn("qa_only: true", PROFILE)

    def test_local_svg_renderer_is_allowed_in_bundled_asset_path(self):
        self.assertIn('(?:png|jpe?g|webp|gif|svg)', HTML)
        self.assertIn("img.src = new URL(imagePath, document.baseURI).href;", HTML)
        self.assertIn("img.onerror = () => {", HTML)
        self.assertIn("tile?.classList.add('is-image-missing')", HTML)
        self.assertIn("img.naturalWidth > 0", QA)
        self.assertIn("OFFLINE_QA_COMMAND_BLOCKED", QA)


if __name__ == "__main__":
    unittest.main()
