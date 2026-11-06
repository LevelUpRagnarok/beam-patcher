<!--
Dosya Yolu: REPO_ROOT/docs/INSTALLER-STRATEGY-TURKUAZ.md
Amac: BeamPatcher tek TurkuazInstaller Windows dagitim ve guvenlik politikasini tanimlar
Modul - Markdown / Installer Policy
Version: 3.0.0-candidate
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

**Beam Rust TurkuazInstaller Primary Only** performs contract and Windows
security negatives on PR. Its protected product job requires manual
workflow_dispatch and signing-environment authorization, signed
manifest/CMS, an independently provisioned publisher certificate
and successful native Windows acceptance. Missing real trust or
E2E evidence must fail closed; no standalone artifact is shareable.

## Single pinned Rust installer upstream

The protected workflow uses only Rust TurkuazInstaller from pinned SHA
`456a34679661978afc717cc5b08ece11cb0b9a94`.
The single user-facing output is `TurkuazSetup.exe`. Rust
`.tzpkg`/`.tzsetup`, `release.yaml`, `release.p7s` and public
`manifest-trust.yaml` are verified package inputs, not extra installers.

Manual protected `windows-installer-signing` requires independently
supplied signed Rust files and `turkuaz-primary-e2e.json` native
acceptance evidence through `BEAM_VERIFIED_RUST_TURKUAZ_BUNDLE`.
The publisher subject and SHA-256 pin come from protected variables
`BEAM_TURKUAZ_PUBLISHER_SUBJECT` and `BEAM_TURKUAZ_CERT_SHA256`.
The exact signed release package bytes must match the freshly compiled
Beam Rust package; a bounded ZIP layout, manifest identity, detached
CMS, Authenticode and hosted Windows install/uninstall are independently
verified. Windows 10/11 GUI and migration approvals must also be present
in external native acceptance evidence. Otherwise upload is prohibited.

No legacy installer runtime, secondary setup, public signer key or
automatic release remains in this active product workflow.

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
