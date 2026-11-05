<!--
Dosya Yolu: docs/INSTALLER-STRATEGY-TURKUAZ.md
Amac: Beam QA paketlemesinden TurkuazInstaller'a guvenli gecis plani ve kabul sinirlari
Modul - Markdown documentation
Version: 0.3.1-candidate
Aciklama: Inno/NSIS tekli dagitimi yasak; Turkuaz signed primary gate tamamlanmadan paylasim yok
Bagimli Oldugu Katman: installer/windows/BeamPatcher-QA.iss | TurkuazLabs/TurkuazInstaller/docs/PROJECT_INTEGRATION.md
-->

# Beam installer: BURAK-INS-001, Turkuaz primary + NSIS private backup

## Binding distribution policy — 2026-10-25

**Never share Inno or NSIS as the user-facing setup.** One Windows
CI orchestrator builds the actual TurkuazInstaller Community bootstrapper
with the Beam Velopack package, plus an NSIS backup from the exact same
commit/version. The NSIS fallback is private; the user-facing download
is always the verified Turkuaz primary. Missing signer, detached CMS
`.p7s`, independently pinned trust, product E2E or NSIS smoke is a
fatal distribution blocker. A failed Turkuaz build does NOT promote NSIS.

The previous Inno installer is retired from automatic artifact upload
but retained as non-published historical QA source until migration
testing is complete. The `windows-setup-patch-qa.yml` job now performs
private NSIS smoke ONLY. The manual
`.github/workflows/dual-installer-policy.yml` is the sole
user-facing distribution path. Until its signed-metadata gate passes,
**no new setup may be provided**. The earlier distributed QA executable
is not a TurkuazInstaller package.

This is a staged migration: **policy and build orchestration implemented;
production signing, real Turkuaz product E2E and shareable primary
NOT COMPLETE**.


## Why Inno was used

The October 25 Beam QA pipeline had a directly testable x64 Inno
Setup compilation/quiet-install/upgrade/uninstall chain. This was a
**scoped test artifact**, NOT an installer-platform decision. User-facing
production distribution should be tracked as a separate TurkuazInstaller
migration, not silently made dependent on the transient Inno QA flow.

Upstream community:
https://github.com/TurkuazLabs/TurkuazInstaller

Upstream project integration contract:
https://github.com/TurkuazLabs/TurkuazInstaller/blob/main/docs/PROJECT_INTEGRATION.md

The upstream Windows Desktop, Velopack E2E and local unsigned test
packaging checks are passing. But their unsigned local test ZIP cannot be
redistributed as a signed product installer.

## Current tools and acceptance gates

- Main Beam patch motor: Rust/Windows x64, independent of setup system.
- New policy/negative tests: `tools/check_installer_workflows.py`,
  `tools/tests/test_installer_distribution_policy.py`.
- Build/pair gate: `tools/verify_installer_pair.py` checks exact source
  SHA, version, primary/fallback role, supplied E2E results and independent
  checksums; this is *not a standalone signature verifier*.
- The Windows workflow checks genuine Turkuaz Authenticode, but a
  signing-protected E2E bundle and real detached CMS/trust verifier remain
  REQUIRED. No unsigned development build is end-user shareable.
- NSIS source: `installer/windows/BeamPatcher-NSIS-Backup.nsi`.
  It installs only QA launcher/config and preserves the user's config.
- Pinned upstream Turkuaz source commit:
  `1048931bf7498ab4d4440414c4463e6ee5e7421e` (Community).


## Signed initial Setup binding and offline trust regressions - 2026-11-05

The protected Windows gate now requires two independent CI jobs before
signed TurkuazInstaller publication: the source/policy contract and
Windows synthetic negative tests in tools/Test-BeamTrustNegative.ps1.

tools/Confirm-TurkuazTrust.ps1 validates bounded CMS metadata,
Windows trusted certificate chain, pinned signer SHA-256/publisher and
certificate validity dates. Only **after** checking the detached CMS,
tools/Assert-BeamManifestSetupBinding.ps1 matches signed Stable v1
package.id, package.version, artifact.sha256 and artifact.size_bytes
to the **actual initial Velopack Setup.exe**. A digest existing only
in an unrelated comment, or belonging to a full nupkg instead of Setup,
is refused for initial-install approval. Full nupkg is bound by the
separate pair/evidence gate and native update/repair/rollback E2E.

The Windows negative fixture suite contains **no production signer**:
its parsing, tamper and metadata-size tests do not prove a signed
Turkuaz product. The protected build-both-and-gate still needs an
explicit dispatch, independently provisioned real signing/trust and
native product acceptance. A green PR/negative test is NOT a release.

## Pinned upstream provenance - 2026-11-05

The dual installer checkout is pinned to TurkuazInstaller Community commit
`1048931bf7498ab4d4440414c4463e6ee5e7421e` and `tools/verify_installer_pair.py`
now requires `turkuaz_source_sha` in the protected evidence to match that
**exact** commit. A 40-character but unrelated SHA no longer passes.
The same source SHA is included in the resulting structural gate report.
A source-pin change must update the reviewed checkout, verifier, tests and
signed Windows acceptance together; it is not approved by editing evidence.

The pinned upstream revision is the legacy .NET Community integration, while
upstream `main` has a newer Rust source tree. This branch deliberately
retains the tested pin, **not** a claim that the new Rust installer has
passed Beam product integration. Rust installer adoption requires its own
separate compatibility and native Windows signing/E2E acceptance.

## Required work before switching Beam installers

1. Pin permanent package ID `levelupgt.beampatcher` and per-user Windows x64
   destination. Decide whether QA remains a separate package identity
   `levelupgt.beampatcher.qa` before a public installer is issued.
2. Place writable `config.yml`, theme choice, game-directory selection and
   patch cache in user-writable app data, not versioned/replaceable Velopack
   `current`. Maintain explicit migration from existing Inno app directory.
3. Produce a **full Velopack nupkg + Setup.exe** using the actual Beam UI/EXE
   with the four local theme image assets, then verify correct WebView2
   rendering and theme selection after install.
4. Generate a versioned project manifest from the real artifact SHA-256,
   byte size, package/channel and per-user target. Do NOT commit placeholder
   artifact digest as a release manifest.
5. Sign the exact raw manifest with a detached CMS `.p7s` and separately
   provision package-scoped signer subject / certificate SHA256 pins in
   `%LOCALAPPDATA%/TurkuazInstaller/config/manifest-trust.yml`.
   Production TurkuazInstaller binaries and distributable artifacts need
   their corresponding signing and preflight approvals.
6. Execute isolated Windows clean install, same-version repair, next-version
   update, previous-version rollback, uninstall, shortcut and config
   preservation tests against a **signed test fixture**.
7. Verify non-admin install, Unicode/spaces in path, older Inno install
   migration, duplicate installed-app detection and tampered manifest/artifact
   refusal. Never target a real player's GRF for installer testing.
8. Only after all gates pass, retire Inno Setup from the production pipeline.
   The current QA script must remain available until replacement passes.

## Known current artifact state

- `installer/windows/BeamPatcher-QA.iss`: operational unsigned standalone
  QA installer. It is not a TurkuazInstaller package.
- `installer/windows/config.qa.yml`: offline/loopback-only, QA GRF;
  client launch and real game settings are disabled.
- `beam-ui/public/assets/1.png` through `4.png` are currently identical
  blobs. Separate approved LevelUp Games promotional art is an asset task,
  not a dependency on the remote Ragnarok patch feed.
- `b1glord/ragnarokclientpatch` is a game update channel containing THOR
  archives, not an approved source of launcher-specific banner PNG/JPG.
- Release signing keys/cert identities and real Ragnarok 2022 client
  compatibility are **not established** by the Beam QA tests.

The **signed product distribution gate is NOT ACCEPTED / NOT RELEASED**. Do not describe it as
production-ready until a separate pinned Turkuaz integration PR runs the
upstream signed manifest + full-package acceptance.

**Documentation alignment (2026-11-05):** The old PR #13 standalone installer download steps are retired. See [Windows Setup and Patch QA](WINDOWS-SETUP-PATCH-QA.md) for the current private NSIS smoke and protected dual installer workflow distinction. A passing PR policy contract is not signed product acceptance.
