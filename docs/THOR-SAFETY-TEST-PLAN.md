# BEAM THOR safety — phase A

File Path: /docs/THOR-SAFETY-TEST-PLAN.md
Purpose: Explain forked BEAM's initial THOR correctness and safety tests
Module: ClientDistribution — Markdown
Version: 1.5.0
Description: Persistent recovery journal, unsafe path rejection and client-root single-writer lock.
Dependency Layer: Tool

Source: MIT-licensed https://github.com/beamguides/beam-patcher; original LICENSE retained.
Our fork: https://github.com/LevelUpGT/beam-patcher. Upstream baseline pinned to feed97887090d121f796bc1b941390e28b7a2da5.

## Completed in this phase (subject to CI)

1. Preserve the original THOR header \`use_grf_merging\` and \`target_grf_name\` instead of discarding it.
2. Refuse corrupted or truncated compressed payloads; do not generate empty replacement files on decode errors.
3. Bound compressed-file expansion (256 MiB per entry), THOR table expansion (16 MiB), and total file count (100,000). Validate size and offset references before decoding and enforce the declared number of entries.
4. Validate internal paths against \`../\`, drive-absolute paths, UNC prefixes, unsafe Windows device filenames and case-folded duplicate names. Reject unsafe or non-UTF-8 THOR filenames; a future legacy codepage adapter may be needed for particular 2015 archives.
5. Round-trip writer metadata and prevent untrusted target GRF names from escaping the intended data archive.
6. **Phase A fail closed:** GRF-only installer rejected loose THOR, before Phase B added a staged client-folder writer. GRF target mismatch still fails closed.

## Phase B — experimental loose-file THOR writer

- `beam-core/src/patcher.rs` now routes **GRF-free THOR** archives to a loose-client file writer.
- All patch downloads, SHA checks and THOR parse checks complete before any client write. Files are staged and backed up on the game's volume before replacing originals.
- Loose-client packages in the same batch are applied in order, with later THOR entries winning. The patcher records completed patches only after a successful batch.
- Bad paths, unsafe Windows device names, symlinked ancestors and case-ambiguous duplicates are refused. Staging and best-effort rollback preserve previous files if an ordinary file operation fails.
- **Mixed GRF+loose THOR batches are intentionally rejected**; they need a joint persistent transaction journal and ordering integration tests.
- A **persistent PREPARING / COMMITTING / COMMITTED recovery journal** is now created on the client's volume. Backups and staged files are synchronized before changes begin. On the next patch check, a stale COMMITTING transaction is rolled back from verified backups; COMMITTED transaction leftovers are cleaned.
- Recovery is checked even if the remote patch list reports zero pending updates. Missing backups, unsafe recovery paths or unknown transaction folders stop patching rather than guessing or removing evidence.
- Windows junction/reparse points, THOR writes to `.patch_cache`, and updates to `.beam-patch-txn-*` are refused. Added simulated interrupted-update regression cases for restore, incomplete preparing, committed cleanup, missing backup and protected directories.
- **Still experimental:** journal/metadata directory durability, transactional coordination with the applied-patch cache, Windows lock contention and forced-power-loss acceptance remain unverified. Do not distribute to players until Windows and crash-injection tests pass.
- No 2015 historical patch state, Thor Patcher config, rPatchur feed or game EXE has been modified.

- A cross-process exclusive `.beam-patch.lock` prevents simultaneous writers from applying patches to the same client directory. The OS releases the lock when the process terminates. THOR entries cannot overwrite patcher lock or recovery metadata.

CI exercises `beam-formats` and `beam-core` parser and transaction tests. It is NOT equivalent to a Windows GRF + client acceptance test.

## Acceptance checklist

- [ ] GitHub Actions \`cargo test -p beam-formats --lib\`: PASS
- [ ] GitHub Actions \`cargo test -p beam-core --lib\`: PASS
- [ ] GitHub Actions \`cargo check -p beam-core\`: PASS
- [ ] Real Windows 10 x64 build on FURY: NOT_RUN
- [ ] Power-failure/journal recovery on Windows: NOT_RUN
- [ ] GRF vs loose file integration on a disposable client: NOT_RUN
- [ ] 2015 legacy THOR and 2022 Hybrid target file compatibility: NOT_RUN

**Do not distribute this branch as a production patcher.** Thor Patcher (old 2015) and rPatchur (new 2015 and 2022 Hybrid) remain unchanged.

## Live published Hybrid fixture and Windows CI

The CI downloads the exact pinned `turkuaz-2022-hybrid-8cfc3211f8eb.thor` file from the `b1glord/ROenglishRE` Hybrid test prerelease, verifies SHA-256 `e18d5368f44feaa1569c1b2f7893b4d51167bd6bb03ab93e4d6ae108a147b2c8`, parses the real THOR and applies its loose `SystemEN/` and `data/` entries inside a disposable directory. It compares the resulting bytes and asserts that no GRF was generated. This is **NOT an in-game Windows 2022 client acceptance**.

GitHub-hosted Windows CI checks the same parser, client file writer, crash recovery and single-writer lock without needing FURY online. The private FURY Windows smoke is **opt-in** for CI scheduling: set repository Actions variable `BEAM_FURY_THOR_RUNNER_ENABLED=true` only when the authorized Windows x64 runner is online. When unset, the FURY job reports **SKIPPED**, never PASS; the hosted Windows job remains mandatory. This removes the permanent offline-runner queue without claiming FURY hardware acceptance.

**Release gate unchanged:** a skipped FURY job is not evidence of real Windows 10 / game-client testing. FURY-specific acceptance, mixed GRF+loose transaction scenarios, crash/power-loss recovery, and signed product distribution still require separate review before production merge/release.

## BEAM vs rPatchur patch-list compatibility

Upstream BEAM originally interpreted `10000 file.thor` as filename `10000` with checksum `file.thor`. The new parser accepts both:
- Native BEAM: `file.thor SHA256 SIZE`
- Numbered rPatchur: `INDEX file.thor`
- BEAM-compatible numbered with verification: `INDEX file.thor SHA256 SIZE`

Commented `//` entries, duplicate filenames/indices, out-of-order indices, unsafe names and invalid digests are handled explicitly.

**Security boundary:** rPatchur's legacy `INDEX file.thor` has no cryptographic digest. When BEAM `verify_checksums` is enabled, digest-less manifests are rejected. To test published THOR securely, distribute a separate signed/pinned BEAM manifest with SHA-256 values rather than disabling verification. Whenever a checksum is present it is always verified, even with permissive legacy mode. Declared sizes are checked before application.

BEAM's current patch list and archive download mirror architecture still needs a signed-manifest/updater-channel acceptance review before a public Windows release.
