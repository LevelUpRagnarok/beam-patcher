<!--
Dosya Yolu: REPO_ROOT/docs/WINDOWS-SETUP-PATCH-QA.md
Amac: Windows patch QA ile TurkuazInstaller primary kabulunu ayri tutar
Modul - Markdown / Windows QA
Version: 0.5.0-candidate
Aciklama: NSIS smokeleri kaldirildi; yalniz TurkuazInstaller kurulum politikasina uygun
Bagimli Oldugu Katman: .github/workflows/windows-setup-patch-qa.yml | .github/workflows/turkuaz-primary-policy.yml
-->

# Windows BeamPatcher patch and installer QA

**Policy: TURKUAZ-ONLY-001.** Verified TurkuazInstaller primary is
the only permitted Windows installer. No independent backup installer
is built by BeamPatcher.

## Core patch and cache test

The Beam Windows Patch Core QA workflow runs real Cargo format/core
tests, builds the x64 Beam/Tauri executable and exercises synthetic
BEAM download, GRF 0x200, cached rerun and SHA-mismatch refusal with
tools/QA-PATCH-E2E.py. It also checks the installer workflow policy.
It does not build or upload a setup.

installer/windows/config.qa.yml is loopback-only; the deliberate
NO_CLIENT_CONFIGURED.exe guard prevents accidental live client use.
Patch-engine QA PASS is not game-client acceptance.

## Rust Turkuaz candidate

The Beam Rust Installer Candidate Compatibility workflow packages a
real Beam QA EXE and theme assets with the pinned Rust CLI, creates
.tzpkg and unsigned manifest and validates SHA-256, size, archive
inventory and entry point.

In isolated hosted Windows, a temporary self-signed CMS certificate
is used for test bundles and install/update/repair/rollback/uninstall.
One TurkuazSetup.exe is generated from the same QA bundle using
the setup-gui stub. The test verifies an Authenticode test signature,
wrong-publisher trust rejection, install-self and user-data
preservation. No real publisher certificate is used, no GUI wizard
is automated, no game client is launched and no test setup uploaded.

## Protected product acceptance

The Beam Rust TurkuazInstaller Primary Only workflow runs policy and
Windows negative fixtures on pull requests. Its production job
runs only through protected manual workflow_dispatch. Real publisher
signing, detached CMS trust, source provenance and native Windows
acceptance are required. A green CI without these remains
NOT RELEASE READY.

See docs/INSTALLER-STRATEGY-TURKUAZ.md.
