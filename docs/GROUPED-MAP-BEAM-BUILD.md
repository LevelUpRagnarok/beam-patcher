<!--
Dosya Yolu: docs/GROUPED-MAP-BEAM-BUILD.md
Amac: New custom-map BEAM v1 offline packaging contract
Modul - Markdown Documentation
Version: 0.1.0-candidate
Aciklama: Historical THOR and live game remain untouched
Bagimli Oldugu Katman: tools/build_map_beam.py | beam-formats/src/beam.rs
-->
# LevelUpGT custom map BEAM v1 build contract

Legacy RagnarokClient rPatchur/THOR is an INDEPENDENT archive channel.
New 20220406 custom maps must originate at LevelUpGT/RagnarokClient
`maps/data/<pack>/<map>.gat/.gnd/.rsw` and `maps/manifest.json` (v2).

The BEAM v1 wire format is owned by this repository, Rust module
`beam-formats/src/beam.rs`. The offline Python builder
`tools/build_map_beam.py` writes the matching 64-byte header,
filename/MD5/compressed size/uncompressed size/offset/GRF alias table,
zlib payloads, no GRF aliases and exact `data\<map>.<ext>` GRF filenames.

The builder validates all map asset SHA256 digests, required trios, unique
map names, catalog coverage and GAT headers. It reopens every BEAM payload
to verify MD5 and source byte-for-byte equality, before writing a file.
It refuses overwriting a pre-existing candidate.

Offline QA:
```powershell
python -B -m unittest discover -s tools/tests -p test_build_map_beam.py -v
python -B tools/build_map_beam.py --assets-root ../RagnarokClient/maps --manifest ../RagnarokClient/maps/manifest.json --output ../RagnarokClient/patches/output/custom-maps.beam
```

**Never** publish this candidate automatically. The BEAM v1 archive has
no embedded target GRF. The intended `tdata1.grf` requires a verified
client DATA.INI priority-0 registration, verified 20220406 EXE, correct
Beam patcher profile, tested real GRF save/readback and rollback, plus game smoke.
Draft Beam PR #7 implements additional checks but is NOT a released guard.
Only use a pinned source commit and record tool and output SHA256 provenance.
Never overwrite the existing rAthena, THOR patchlist or game client.
