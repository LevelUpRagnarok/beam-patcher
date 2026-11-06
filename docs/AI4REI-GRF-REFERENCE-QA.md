<!--
Dosya Yolu: REPO_ROOT/docs/AI4REI-GRF-REFERENCE-QA.md
Amac: Ai4rei rsu.ts ve legacy GRF araclarini Beam icin harici, kontrollu QA referansi olarak tanimlar
Modul - Documentation Markdown
Version: 0.1.0
Aciklama: Kaynak ve karsilastirma matrisi; dis binary dagitimi veya otomatik yurutme icermez
Bagimli Oldugu Katman: beam-formats / Documentation
-->
<!-- docs-meta: owner=LevelUpGT; reviewed=2026-10-23; source=GitHub-PR -->

# External GRF reference QA — Ai4rei rsu.ts / legacy tools

**Status:** REFERENCE REGISTERED / IMPLEMENTATION BLOCKED / TESTS NOT RUN.
**Priority:** P2, developer-only research. This page is NOT an installed integration.

## Authoritative external references

- Modern tools catalog: https://nn.ai4rei.net/dev/rotools/
- Legacy catalog: https://nn.ai4rei.net/dev/rotools/legacy.htm
- Modern **rsu.ts 4.0.0** is described by the author as an all-in-one GRF archive
  test suite that contains the legacy GRF command-line tools in one binary.
  Prefer evaluating this over automatically bundling eight old executables.
- Webpage footer: CC BY-NC-ND 4.0 notice. The exact redistribution, integration,
  derivative and commercial-use terms for the downloadable programs have **not**
  been separately verified. Do NOT infer source-code availability, open-source
  license or permission to redistribute the binaries.

## External command map (research only; CLI syntax unknown)

| Reference command | Documented behavior | BEAM local QA question |
| --- | --- | --- |
| rsu.test 2.1 | Detects unreadable/invalid GRF entries | Grf reader integrity comparison, corrupt fixture |
| rsu.unpack 2.3 | Extracts archive contents | Byte-for-byte extracted entry SHA-256 parity |
| rsu.cherry 1.1 | Selective GRF-to-GRF copy | Subset/encoding behavior vs our own isolated fixture |
| rsu.diff 2.3 | Delta from two GRFs | Reproducible patch delta semantics |
| rsu.merge 1.9 | Merge GRFs / apply patches | Delta application versus current GRF writer |
| rsu.antimerge 1.2 | Subtract one GRF from another | Deletion/removal semantics and rollback limits |
| rsu.pack 1.7 stable, 2.2 experimental | Create GRF from data folder | Synthetic GRF 0x200 writer/readback |
| rsu.split 1.4 | Split a GRF into bounded pieces | Large archive chunk ordering and integrity |

Version numbers above are *catalog labels*, not tested or bundled artifacts.
rsu.ts subcommands/options must be confirmed from the tool's own --help or
vendor documentation in a permitted, isolated environment; do not guess them.

## Existing Beam capability, boundary and related work

- Current first-party engine: `beam-formats` regular GRF reader/writer, with
  version/unsupported-encryption fail-closed rules documented in
  `docs/GRF-PROTECTION-QA.md`.
- Existing test pipeline: `tools/build_map_beam.py` and isolated GRF
  readback/verification workflows; never bypass BEAM manifest/checksum guard.
- Existing sensitive work: custom `tdata1.grf`, protected GRF, 2015 THOR
  compatibility, auto-update/rollback and player deployment remain unchanged.
- Client test entrypoint: https://github.com/LevelUpGT/RagnarokClient/issues/15
- Unreal import/reference test: https://github.com/LevelUpGT/RagnarokUnrealClient/issues/10
- Separate Beam crash analysis plan:
  https://github.com/LevelUpGT/beam-patcher/pull/9

## Future acceptance gates

1. **Rights/provenance:** Confirm author and distribution terms for actual
   binaries. Independently obtained tool must have recorded source URL, version,
   size, verified SHA-256, and malware/PE static-audit evidence. Record what is
   UNKNOWN instead of inventing a trusted hash.
2. **Sandbox:** Optional *manual* reference tool execution only, in a
   disposable Windows VM or isolated non-networked sandbox, non-admin, with
   synthetic GRFs. No access to personal folders, active game installation,
   player credentials, production configs or deployment keys.
3. **Inputs and output safety:** Treat files and output from external binaries
   as untrusted. Validate trusted root, path traversal, relative path segments,
   symlinks/junctions, file sizes and failure codes. New output directory for
   each run; never overwrite client GRFs or DATA.INI.
4. **Parity:** Cover standard GRF 0x200 with deterministic fixtures:
   duplicate paths, CP949/Unicode names, nested folders, empty files, corrupted
   compressed entries, truncated headers, and unknown/encrypted flags.
   Unknown formats must fail closed; do not infer support from successful
   header parsing.
5. **Evidence:** Compare per-entry bytes and SHA-256, full archive SHA-256 only
   where stable/meaningful, error categories, version, exact tool hash and
   read/write status. Distinguish legacy tool behavior from normative format
   validity. Record failures, NOT RUN and incompatibilities without claiming
   suite compatibility.
6. **Validation lanes:** Rust cargo fmt, clippy, unit/integration (first-party)
   separate from optional Windows external reference smoke and genuine 20220406
   client smoke. Neither builds nor archive-readback prove live client support.
7. **Approval:** No vendor EXE/ZIP checked into repository, installer, release,
   CI downloads, GitHub Actions artifacts or production patchlist until
   licensing and security gates are satisfied and distribution is explicitly
   authorized.

## Current evidence

- Source catalog and legacy descriptions reviewed 2026-10-23.
- Actual `rsu.ts` / legacy binary provenance, binary license, checksum,
  CLI flags, sandbox outcome: **UNKNOWN / NOT RUN**.
- Implementation, Rust tests, Windows runtime tests, client tests: **NOT RUN**.
- This PR changes documentation only. No release/merge is authorized.

BURAK DEV STANDARD v3.0.0:
https://github.com/TurkuazSoft/DevStandards/blob/main/standards/documentation-lifecycle.md
