<!--
Dosya Yolu: REPO_ROOT/docs/INSTALLER-STRATEGY-TURKUAZ.md
Amac: BeamPatcher tek TurkuazInstaller Windows dagitim ve guvenlik politikasini tanimlar
Modul - Markdown / Installer Policy
Version: 2.1.0-candidate
Aciklama: Ikinci kurulum kaldirildi; imzasiz/test-signed dagitim yasaktir
Bagimli Oldugu Katman: AGENTS.md | tools/verify_installer_primary.py
-->

# BeamPatcher Windows installer — TurkuazInstaller only

**Status: POLICY CANDIDATE — NOT A SIGNED PRODUCT RELEASE.**

The only supported user-facing Windows installer for BeamPatcher is
**TurkuazInstaller**. The former NSIS backup script, its compilation
and install smoke, dual-output evidence and compulsory fallback policy
are retired. No other independent installer may be distributed.
The obsolete Inno QA source has also been deleted; neither an Inno
nor an NSIS installer script is permitted in the current tree.
CI rejects the reintroduction of .iss and .nsi installer source files.

## Three independent test layers

**Beam Windows Patch Core QA** builds and tests native Beam/Tauri and
synthetic GRF 0x200 download/cache/integrity without producing a setup.

**Beam Rust Installer Candidate Compatibility** pins current Rust
TurkuazInstaller source, builds a real Beam QA EXE, generates a .tzpkg
and manifest, checks package bytes and inventory, and exercises
install/update/repair/rollback/uninstall with an ephemeral self-signed
CMS certificate. It also builds **one** temporary TurkuazSetup.exe,
test-signs it with Authenticode and uses its CLI install-self path.
The GUI wizard and actual game client are **not** executed.
No test EXE is uploaded or distributed.

**Beam TurkuazInstaller Primary Only** performs contract and Windows
security negatives on PR. Its protected product job requires manual
workflow_dispatch and signing-environment authorization, signed
manifest/CMS, an independently provisioned publisher certificate
and successful native Windows acceptance. Missing real trust or
E2E evidence must fail closed; no standalone artifact is shareable.

## Current source generations

The protected legacy-compatible primary workflow still builds the
pinned **.NET TurkuazInstaller + Velopack** distribution from revision
1048931bf7498ab4d4440414c4463e6ee5e7421e.
The separate **Rust** integration uses upstream revision
456a34679661978afc717cc5b08ece11cb0b9a94 and the Rust
.tzpkg / .tzsetup formats. A successful Rust QA test does not prove
that the new Rust format has real publisher-signed production E2E.
Never mix the two formats or silently update pinned source revisions.

## Required product acceptance

Before publishing any Turkuaz primary EXE, verify the exact Beam and
Turkuaz source commits, win-x64 QA product/version, artifact hashes,
real signed raw manifest and detached CMS, external certificate
subject/SHA-256 pin, valid Windows Authenticode trust, and real native
install, update, repair, rollback, uninstall and user-file preservation.

Acceptance must also cover non-admin installs, Unicode/space paths,
shortcuts, registry, the actual GUI wizard and clean Windows 10/11.
Prior installations may have their own uninstaller and user files:
migration must require explicit consent and avoid automatic deletion.

The Python structural check in tools/verify_installer_primary.py is
NOT a cryptographic signature verifier. Protected workflow calls
tools/Confirm-TurkuazTrust.ps1 separately, and independent native
product evidence is still required. The protected signing job remains
NOT_RUN unless explicitly dispatched with actual signing materials.

No main merge or production release is authorized by a green QA run.
See docs/RUST-INSTALLER-BEAM-COMPAT.md and
docs/WINDOWS-SETUP-PATCH-QA.md for test boundaries.
