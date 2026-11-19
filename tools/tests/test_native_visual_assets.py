#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/tests/test_native_visual_assets.py
# Amac: Native tema fallback'inin sadece yerel tasarim verisini kullanmasini kontrol et
# Modul - Python unittest / Static native UI contract
# Version: 0.1.0-candidate
# Aciklama: Gercek Windows Tauri kabul testi degildir; build ve GUI CI ayri calisir
# Bagimli Oldugu Katman: beam-ui/src/native_visual_assets.rs | beam-ui/src/lib.rs

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NATIVE = (ROOT / "beam-ui/src/native_visual_assets.rs").read_text(encoding="utf-8")
LIB = (ROOT / "beam-ui/src/lib.rs").read_text(encoding="utf-8")
ASSETS = ROOT / "beam-ui/public/assets"


class NativeVisualAssetContracts(unittest.TestCase):
    def test_tauri_page_load_installs_adapter(self):
        self.assertIn("mod native_visual_assets;", LIB)
        self.assertIn(".on_page_load(|window, _| native_visual_assets::install(&window))", LIB)

    def test_all_embedded_sources_exist_and_are_checked_in(self):
        refs = re.findall(r'include_str!\("\.\./public/assets/([^"]+)"\)', NATIVE)
        self.assertEqual(len(refs), 14)
        self.assertEqual(len(refs), len(set(refs)))
        for basename in refs:
            with self.subTest(asset=basename):
                self.assertTrue((ASSETS / basename).is_file())
                self.assertNotIn("/", basename)
        for required in (
            "ragnar-legacy.css", "ragnar-classic.css",
            "levelup-modern.css", "turkuaz-premium.css",
            "turkuaz-reference-restore.css",
            "turkuaz-user-classic-header.svg",
            "turkuaz-user-classic-castle.svg",
        ):
            self.assertIn(required, refs)

    def test_css_is_scoped_and_native_fallback_cannot_patch_game(self):
        self.assertIn("window.eval(&script)", NATIVE)
        self.assertIn("document.getElementById('beam-native-visual-assets')", NATIVE)
        self.assertIn("document.createElement('style')", NATIVE)
        self.assertIn("encodeURIComponent(svg)", NATIVE)
        self.assertIn("img.dataset.beamEmbeddedFallback", NATIVE)
        self.assertNotIn("https://", NATIVE)
        self.assertNotIn("invoke(", NATIVE)
        self.assertNotIn("start_patching", NATIVE)
        self.assertNotIn("launch_game", NATIVE)


if __name__ == "__main__":
    unittest.main()
