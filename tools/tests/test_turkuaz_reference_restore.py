#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/tests/test_turkuaz_reference_restore.py
# Amac: Kullanici tarafindan saglanan launcher gorsellerinin orijinal referansli geri donusunu denetler
# Modul - Python unittest
# Version: 1.0.0-candidate
# Aciklama: Gercek referans resimlerinin lokal, self-contained ve sadece dekoratif olmasi
# Bagimli Oldugu Katman: beam-ui/public/index.html | turkuaz-reference-restore.css | turkuaz-user-*.svg

import base64
import hashlib
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "beam-ui/public/assets"
HTML = (ROOT / "beam-ui/public/index.html").read_text(encoding="utf-8")
CSS = (ASSETS / "turkuaz-reference-restore.css").read_text(encoding="utf-8")
PINNED_REFERENCE_SHA256 = {
    "turkuaz-user-classic-header.svg": "1081e5035790de6d3816785bbf7f742422d828abf22912ebaea90c35f5e3a2c7",
    "turkuaz-user-classic-castle.svg": "333a8c8991f5e2de617f36e0bb6680196df5fab4c7886649514a8ce8603ce972",
    "turkuaz-user-modern-hero.svg": "2523c878fa289139d81bc5458d82c35118ddeed48f74153eb3af94940152bef3",
}
EXPECTED = (
    ("classic-header", "turkuaz-user-classic-header.svg"),
    ("classic-castle", "turkuaz-user-classic-castle.svg"),
    ("modern-hero", "turkuaz-user-modern-hero.svg"),
)


class TurkuazReferenceRestoreTests(unittest.TestCase):
    def test_reference_images_are_distinct_real_self_contained_jpegs(self):
        hashes = []
        ns = "{http://www.w3.org/2000/svg}"
        for name, filename in EXPECTED:
            source = ASSETS / filename
            self.assertTrue(source.is_file(), filename)
            root = ET.parse(source).getroot()
            self.assertEqual(root.tag, ns + "svg")
            images = root.findall(ns + "image")
            self.assertEqual(len(images), 1, filename)
            uri = images[0].attrib["href"]
            self.assertTrue(uri.startswith("data:image/jpeg;base64,"), filename)
            binary = base64.b64decode(uri.split(",", 1)[1], validate=True)
            self.assertTrue(binary.startswith(bytes([0xff, 0xd8, 0xff])), filename)
            self.assertTrue(binary.endswith(bytes([0xff, 0xd9])), filename)
            self.assertGreater(len(binary), 9000, filename)
            self.assertNotIn("<script", source.read_text(encoding="utf-8"))
            self.assertNotIn("<foreignObject", source.read_text(encoding="utf-8"))
            actual_digest = hashlib.sha256(binary).hexdigest()
            self.assertEqual(actual_digest, PINNED_REFERENCE_SHA256[filename], "Do not silently replace supplied artwork")
            hashes.append(actual_digest)
            self.assertIn(filename, CSS)
        self.assertEqual(len(hashes), len(set(hashes)), "No repeated placeholders")

    def test_reference_restoration_only_decorates_real_ui(self):
        self.assertIn('href="assets/turkuaz-reference-restore.css"', HTML)
        self.assertIn('class="turkuaz-reference-banner"', HTML)
        self.assertIn("body.theme-ragnar-classic .turkuaz-reference-banner", CSS)
        self.assertIn("body.theme-levelup-modern .modern-hero", CSS)
        self.assertIn("background:", CSS)
        self.assertEqual(CSS.count("{"), CSS.count("}"))
        for old_control in (
            'id="play-button" onclick="handlePlayButton()"',
            'id="theme-settings-open" onclick="openThemeSettings()"',
            'onclick="manualPatch()"',
            'onclick="resetCache()"',
        ):
            self.assertIn(old_control, HTML)
        self.assertEqual(HTML.count('id="play-button"'), 1)
        self.assertIn("'beam.launcher.theme.v1'", HTML)
        self.assertNotIn("fetch(", CSS)
        self.assertNotIn("https://", CSS)
        self.assertNotIn("http://", CSS)

    def test_reference_graphics_have_accessible_labels(self):
        self.assertRegex(HTML, r'class="turkuaz-reference-banner"[^>]*role="img"')
        self.assertIn("aria-label=\"Turkuaz Ragnarok Online\"", HTML)
        self.assertIn("clip-path: inset(50%)", CSS)


if __name__ == "__main__":
    unittest.main()
