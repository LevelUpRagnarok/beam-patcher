<!--
Dosya Yolu: REPO_ROOT/docs/WINDOWS-SETUP-PATCH-QA.md
Amac: Beam Windows QA test adimlarini ve imzali kurulum dagitim sinirini anlatmak
Modul - Markdown deployment/testing guide
Version: 0.3.0-candidate
Aciklama: BURAK-INS-001 tekli Inno ve NSIS kurulum dagitimini reddeder
Bagimli Oldugu Katman: .github/workflows/windows-setup-patch-qa.yml | .github/workflows/dual-installer-policy.yml
-->

# Turkuaz Ragnarok Online - Windows Setup and Patch QA

**Status: DEVELOPMENT / NOT PRODUCTION / NO DOWNLOADABLE STANDALONE SETUP.**

This project contains a Rust/Tauri Beam launcher and four opt-in visual
themes. The candidate QA profile contains **no** licensed Ragnarok client
EXE, original GRFs, DATA.INI, private keys or game patch feeds.

## Active Windows installer policy: BURAK-INS-001

- The `Beam Windows Patch QA and Private NSIS Smoke` workflow builds the
  actual Rust launcher and runs an isolated synthetic patch download/GRF
  regression. It privately builds, installs and uninstalls an NSIS backup
  on the GitHub-hosted Windows runner. **It deliberately uploads no setup.**
- `installer/windows/BeamPatcher-QA.iss` is retained for historical
  reference only. It is not a supported standalone distribution channel.
- `Beam Dual Installer (Turkuaz Primary, NSIS Private)` provides the
  only conditional distribution gate. It is manually dispatched in a
  protected signing environment and must verify signed Turkuaz binaries,
  a detached CMS manifest, independent certificate pin, Velopack package,
  native install/update/repair/rollback/uninstall and NSIS recovery smoke.
- The private NSIS backup is **never** a public fallback if Turkuaz signing
  or acceptance fails. No successful source or Chromium CI run overrides
  this requirement.
- The installer policy contract runs on every relevant PR. A
  `policy-contract` PASS **does not** mean `build-both-and-gate` PASS:
  the signed Windows product test must complete separately.

**Do not download/share previous standalone Inno/NSIS setup artifacts as
current Beam installers.** The earlier `levelup-beam-windows-setup-qa`
artifact and `LevelUpGames-BeamPatcher-QA-Setup.exe` are retired,
unsigned historical test products and not the current distribution path.

## How to verify the current developer build

1. Open the [Windows Patch QA workflow](../.github/workflows/windows-setup-patch-qa.yml)
   for the exact commit on the intended development PR.
2. Check that the format/core Rust tests, Windows executable build,
   `tools/QA-PATCH-E2E.py`, installer policy check and **private**
   NSIS install/uninstall smoke all pass. No separate setup artifact is
   expected from this workflow.
3. Check the [dual installer policy workflow](../.github/workflows/dual-installer-policy.yml).
   Its PR contract job confirms that no standalone setup bypass exists.
   A signed product build is **NOT_RUN** unless the protected manual
   workflow was dispatched and every signature and native test passed.
4. The [theme QA workflow](../.github/workflows/ragnar-legacy-theme-qa.yml)
   exercises all four visual themes with mocked/offline browser tests and
   may upload screenshots. Screenshots are not a Windows setup or native
   WebView2 acceptance result.
5. For a local developer smoke test, compile the candidate from source
   in a disposable Windows VM and use an **empty synthetic** QA game
   directory. Do not replace a production installation or point the
   launcher at the actual Ragnarok client.

## Offline QA profile

`installer/windows/config.qa.yml` is loopback-only and sets
`patcher.qa_only: true`, `client_exe: NO_CLIENT_CONFIGURED.exe`,
`target_grf: levelup-qa.grf` and `updater.enabled: false`.
It is a test guard, **not** a tamper-resistant security boundary.

For the old PR #13 implementation, the QA launcher accepts only an
absolute existing directory that is empty or holds its own expected QA GRF
and cache. It rejects existing game EXE/GRF/DATA.INI, remote patch feeds,
symlink/junction paths and an unconfigured or mismatched profile before
new GRF/cache writes. Manual patch tests use synthetic fixtures only.
The public game feed remains disabled.

`tools/QA-PATCH-E2E.py` tests synthetic BEAM SHA-256 verification, a
disposable GRF 0x200, applied-patch cache behavior, corrupt archive
refusal and unsafe directory rejection. This is **not** an in-game
Ragnarok login, map loading or patch rollback acceptance test.

## Before a user-facing installer exists

Signing credentials and independently pinned trust must be provisioned
outside GitHub source. The full Turkuaz primary must pass protected
Windows native install, update, repair, rollback, uninstall, shortcut,
non-admin, Unicode-path and user-config preservation checks. The signed
primary must match the exact source SHA and tested Velopack payload.

A normal source/QA CI PASS, an unsigned installer, a private NSIS smoke
or a temporary artifact must never be presented as an approved release.
No `main` merge, player update feed or production deployment is
authorized by this document.
