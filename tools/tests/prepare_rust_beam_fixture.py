#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/tests/prepare_rust_beam_fixture.py
# Amac: Make a Python-encoded fixture for independent Rust BeamArchive reader QA
# Modul - Python Test Fixture
# Version: 0.1.0
# Aciklama: Synthetic assets only, under explicitly chosen temporary directory
# Bagimli Oldugu Katman: tools/build_map_beam.py
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_map_beam import build


def main(root):
    root.mkdir(exist_ok=False, parents=True)
    maps = root / "maps"
    entries = []
    for group, name in [
        ("anotherdungeon", "qa_map1"),
        ("overlookwaterdungeon", "iz_dun00t"),
    ]:
        folder = maps / "data" / group
        folder.mkdir(parents=True)
        data = {
            "gat": b"GRAT\x01\x02" + struct.pack("<II", 2, 2) +
                   struct.pack("<ffffI", 0., 0., 0., 0., 1) * 4,
            "gnd": b"GRGN\x01\x02",
            "rsw": b"GRSW\x02\x02",
        }
        row = {"group": group, "name": name}
        for ext, payload in data.items():
            (folder / f"{name}.{ext}").write_bytes(payload)
            row[f"{ext}_sha256"] = hashlib.sha256(payload).hexdigest()
        entries.append(row)
    manifest = maps / "manifest.json"
    manifest.write_text(json.dumps({"schema": "levelupgt.addon-map-assets.v2", "maps": entries}))
    archive = root / "custom-maps.beam"
    result = build(maps, manifest, archive)
    print(f"BEAM_RUST_FIXTURE_READY archive={archive} assets={result['asset_count']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Provide fresh test output directory")
    main(Path(sys.argv[1]))
