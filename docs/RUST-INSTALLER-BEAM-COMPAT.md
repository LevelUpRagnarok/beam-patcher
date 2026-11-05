<!--
Dosya Yolu: REPO_ROOT/docs/RUST-INSTALLER-BEAM-COMPAT.md
Amac: Beam icin TurkuazInstaller Rust adayinin ayri ve yayinlamayan kabul sinirlarini belgelendirmek
Modul - Markdown integration / acceptance plan
Version: 1.2.0-candidate
Aciklama: Ephemeral CMS lifecycle + Turkuaz GUI primary/private NSIS pair smoke; release gate degismez
Bagimli Oldugu Katman: .github/workflows/rust-installer-beam-compat.yml | docs/INSTALLER-STRATEGY-TURKUAZ.md
-->

# BeamPatcher - TurkuazInstaller Rust compatibility (experimental)

**Status: DEVELOPMENT / NO PRODUCT SIGNING / TEST-ONLY CI INSTALL / NOT RELEASE READY.**

## Why this is a separate PR

The approved BURAK-INS-001 distribution policy currently runs the
legacy pinned TurkuazInstaller Community checkout at
`1048931bf7498ab4d4440414c4463e6ee5e7421e`.
It produces a Velopack Setup.exe and full nupkg alongside a private
NSIS recovery installer. Its production signing and native product
acceptance are still **NOT_RUN**; a green PR policy job is not a
distributable setup.

Rust Community is independently pinned for this candidate to commit
`456a34679661978afc717cc5b08ece11cb0b9a94`.
Its own packaging is different:

| Capability | Existing Beam path | Rust candidate |
| --- | --- | --- |
| Package archive | Velopack full nupkg | Turkuaz v2 `.tzpkg` |
| Install entry | Velopack Setup.exe | Test-signed `.tzsetup` plus Turkuaz GUI-stub-based primary; product signing NOT_RUN |
| Release manifest | Old signed Velopack setup descriptor | Rust manifest describing the **.tzpkg bytes** |
| Recovery backup | Private NSIS, old protected workflow | Ephemeral pair build/PE/signature CI probe; NSIS GUI acceptance NOT_RUN |
| User data | Legacy QA config beside install | Rust state/journal/versions under separate user-data root |
| Production signing | Required, unproven | Required, not attempted; ephemeral CI CMS test signer only |

**The old signed Setup.exe validator must not be silently reused as
a validator for a Rust .tzpkg manifest.** Signature trust, Authenticode
and artifact content identity are separate gates.

## Read-only, unsigned candidate workflow

`Beam Rust Installer Candidate Compatibility` checks out the exact Beam
PR and the pinned upstream Rust revision into a separate CI directory.
It builds actual `beam-patcher.exe` on a hosted Windows runner, then
builds the upstream Rust CLI with committed `Cargo.lock` (`--locked`).
The CLI creates a **temporary, unsigned** v2 `.tzpkg` containing
the real Beam EXE, the loopback-only QA configuration, README and existing
local assets; `describe-package` produces an unsigned manifest draft.

`tools/check_rust_installer_candidate.py` verifies the pinned upstream
source revision, zip structure, package id/version/entrypoint, exact file
inventory and SHA-256 of every staged payload file, and draft
`artifact.sha256`/`size_bytes` against the **whole .tzpkg**.
It rejects missing files, foreign archive entries, path traversal,
duplicate/case-colliding entries, SHA drift and unexpected identities.
Offline unit fixtures exercise rejection paths independently.

The Windows package-generation step performs no game client launch or patch,
no public setup/NSIS distribution, and **no artifact upload**. An additional
test-only step exercises the actual Rust install lifecycle with an
**ephemeral, self-signed CMS fixture certificate** in the disposable
GitHub-hosted Windows runner. The temporary test root is under RUNNER_TEMP,
no publisher trust store is modified, and all test materials are cleaned
up after the run. This is not a publisher-signed Windows installer.

The test signs an offline QA manifest that binds the actual Beam .tzpkg;
it checks altered manifest rejection, installs version 1.0.1, updates
to version 1.0.2 containing the same Beam EXE plus a changed QA README,
refuses modified managed files, repairs, rolls back by the test-signed
policy and uninstalls while preserving an unmanaged user-owned file.
**No client executable is launched.** Production certificate-chain and
real publisher Authenticode trust, installer wizard, native shortcuts/registry behavior,
real user-data migrations and clean Windows 10/11 VM acceptance remain
NOT_RUN. A successful run is limited to an ephemeral CI signed-bundle
lifecycle and does not grant distribution approval.

The same hosted-Windows CI further compiles the pinned Rust CLI's
`setup-gui` feature (without replacing the independently tested CLI) and
installs NSIS for **temporary packaging only**. From the *same* test-signed
version 1.0.2 `.tzsetup`, `build-distribution-pair` must atomically
produce `TurkuazSetup.exe` and the private
`TurkuazInstallerBackup.exe`. CI checks both PE headers, nonempty and
distinct files, refuses a deliberately wrong publisher certificate
pin without leaving a published pair, and signs/verifies both PE files
with the ephemeral **untrusted** CI certificate. It then installs
version 1.0.2 using `TurkuazSetup.exe install-self`, verifies managed
state and uninstalls without disturbing the unmanaged user file.
No end-user GUI is opened; the NSIS backup EXE is **not executed**,
and neither EXE is uploaded, released or made available for download.
A pass is a test-only pair-build and CLI self-extractor proof, not
real GUI usability or NSIS recovery acceptance.

## Mandatory blockers before any Rust installer can replace legacy

1. Create an isolated *signed* Rust .tzpkg/.tzsetup acceptance path with
   independent trust provisioning, signed raw manifest and protected
   Authenticode publisher pin. Never import test signer material.
2. Prove the Rust archive and release manifest correspond to the actual
   Beam source commit; include reproducible CI provenance and an exact
   source SHA in protected evidence. The unsigned candidate checksum
   alone is not publisher authentication.
3. Produce Rust Turkuaz primary + private NSIS backup from the same
   protected package identity/version and require full Windows native
   install/update/repair/rollback/uninstall acceptance.
4. Preserve user config, chosen theme/assets, selected game directory,
   shortcuts, QA-only restrictions and uninstall ownership when moving
   from the legacy layout; reject ambiguous migrations.
5. Verify signed prerequisite, shortcut/protocol and `preserve_paths`
   parity, current unresolved areas in the upstream Rust CLI.
   Test on clean Windows 10 and 11 VMs with non-admin, Unicode/space,
   duplicate-install, tamper, cancellation and power-loss cases.
6. Require review/approval to change BURAK-INS-001's legacy source
   checkout or public primary. A passing candidate PR never modifies
   the protected `build-both-and-gate` and never promotes NSIS.

Source: the pinned
[TurkuazInstaller Rust CLI](https://github.com/TurkuazLabs/TurkuazInstaller/blob/456a34679661978afc717cc5b08ece11cb0b9a94/rust/CLI.md)
and [Rust readiness](https://github.com/TurkuazLabs/TurkuazInstaller/blob/456a34679661978afc717cc5b08ece11cb0b9a94/rust/RUST_READINESS.md).

## QA commands

```sh
python -m unittest discover -s tools/tests -p test_rust_installer_candidate.py -v
```

On Windows, review the exact-head Actions result from
`.github/workflows/rust-installer-beam-compat.yml`.
**This document does not authorize a setup download or production release.**
