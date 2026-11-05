#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/tests/test_build_map_beam.py
# Amac: Offline grouped map BEAM encoder, source-integrity and overwrite tests
# Modul - Python unittest
# Version: 0.1.0-candidate
# Aciklama: Fake assets in TEMP only; never touches live client or GRF.
# Bagimli Oldugu Katman: tools/build_map_beam.py

import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "build_map_beam.py"
spec = importlib.util.spec_from_file_location("build_map_beam", TOOL)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fake_gat():
    return b"GRAT\x01\x02" + struct.pack("<II", 1, 1) + struct.pack("<ffffI", 0., 0., 0., 0., 1)


def assets():
    return {"gat": fake_gat(), "gnd": b"GRGN\x01\x02", "rsw": b"GRSW\x02\x02"}


class BeamGroupedMapTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(prefix="beam-map-fixture-")
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.maps = self.root / "maps"
        (self.maps / "data").mkdir(parents=True)
        self.output = self.root / "custom-maps.beam"
        self.manifest = self.maps / "manifest.json"
        self.rows = []

    def add(self, group, name):
        base = self.maps / "data" / group
        base.mkdir(exist_ok=True)
        row = {"group": group, "name": name}
        for ext, raw in assets().items():
            (base / f"{name}.{ext}").write_bytes(raw)
            row[ext + "_sha256"] = hashlib.sha256(raw).hexdigest()
        self.rows.append(row)

    def catalog(self):
        self.manifest.write_text(json.dumps({
            "schema": "levelupgt.addon-map-assets.v2",
            "maps": sorted(self.rows, key=lambda r: (r["group"], r["name"]))
        }))

    def test_two_map_packs_flatten_into_single_beam(self):
        self.add("overlookwaterdungeon", "iz_dun00t")
        self.add("secondpack", "map_qa01")
        self.catalog()
        result = mod.build(self.maps, self.manifest, self.output)
        self.assertEqual(result["map_count"], 2)
        self.assertEqual(result["asset_count"], 6)
        self.assertEqual(result["target_grf_candidate"], "tdata1.grf")
        self.assertEqual(result["sha256"],
                         hashlib.sha256(self.output.read_bytes()).hexdigest())
        flat = mod.gather(self.maps, self.manifest)
        self.assertEqual(set(n for n, _ in flat),
                         {f"data\\{name}.{ext}" for name in ("iz_dun00t", "map_qa01")
                          for ext in ("gat", "gnd", "rsw")})
        mod.verify_archive(self.output.read_bytes(), flat)
        self.assertNotIn(b"overlookwaterdungeon", self.output.read_bytes())
        self.assertEqual(mod.make_archive(flat), self.output.read_bytes())

    def test_hash_mutation_blocks_output(self):
        self.add("overlookwaterdungeon", "iz_dun00t")
        self.catalog()
        (self.maps / "data/overlookwaterdungeon/iz_dun00t.rsw").write_bytes(b"GRSW\x02\x03")
        with self.assertRaisesRegex(ValueError, "MAP_SHA256_MISMATCH"):
            mod.build(self.maps, self.manifest, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_trio_and_extra_file_block(self):
        self.add("overlookwaterdungeon", "iz_dun00t")
        self.catalog()
        p = self.maps / "data/overlookwaterdungeon/iz_dun00t.rsw"
        raw = p.read_bytes()
        p.unlink()
        with self.assertRaisesRegex(ValueError, "MISSING_OR_LINKED_ASSET"):
            mod.build(self.maps, self.manifest, self.output)
        p.write_bytes(raw)
        (self.maps / "data/overlookwaterdungeon/unlisted.rsw").write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "CLIENT_MAP_CATALOG_STALE"):
            mod.build(self.maps, self.manifest, self.output)

    def test_collision_across_packs_rejected(self):
        self.add("firstpack", "iz_dun00t")
        self.add("secondpack", "iz_dun00t")
        self.catalog()
        with self.assertRaisesRegex(ValueError, "MAP_NAME_COLLISION"):
            mod.build(self.maps, self.manifest, self.output)

    def test_existing_output_never_replaced(self):
        self.add("overlookwaterdungeon", "iz_dun00t")
        self.catalog()
        self.output.write_bytes(b"original-owned-candidate")
        with self.assertRaises(FileExistsError):
            mod.build(self.maps, self.manifest, self.output)
        self.assertEqual(self.output.read_bytes(), b"original-owned-candidate")

    def test_corrupted_beam_rejected_on_roundtrip(self):
        self.add("overlookwaterdungeon", "iz_dun00t")
        self.catalog()
        entries = mod.gather(self.maps, self.manifest)
        data = bytearray(mod.make_archive(entries))
        data[-1] ^= 0xff
        with self.assertRaises((ValueError, Exception)):
            mod.verify_archive(bytes(data), entries)

    def test_wrong_output_file_basename_denied(self):
        self.add("overlookwaterdungeon", "iz_dun00t")
        self.catalog()
        with self.assertRaisesRegex(ValueError, "ONLY_CUSTOM_MAPS_BEAM"):
            mod.build(self.maps, self.manifest, self.root / "override-client.thor")


if __name__ == "__main__":
    unittest.main()
