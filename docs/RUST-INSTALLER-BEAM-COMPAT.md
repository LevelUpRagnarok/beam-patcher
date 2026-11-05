<!--
Dosya Yolu: REPO_ROOT/docs/RUST-INSTALLER-BEAM-COMPAT.md
Amac: Beam icin TurkuazInstaller Rust adayinin ayri ve yayinlamayan kabul sinirlarini belgelendirmek
Modul - Markdown integration / acceptance plan
Version: 1.0.0-candidate
Aciklama: Gercek Beam exe ile unsigned Rust .tzpkg deneyi; eski release gate degistirilmez
Bagimli Oldugu Katman: .github/workflows/rust-installer-beam-compat.yml | docs/INSTALLER-STRATEGY-TURKUAZ.md
-->

# BeamPatcher - TurkuazInstaller Rust compatibility (experimental)

**Status: DEVELOPMENT / UNSIGNED / NO INSTALL / NOT RELEASE READY.**

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
| Install entry | Velopack Setup.exe | Signed `.tzsetup` / native setup wrapper (future) |
| Release manifest | Old signed Velopack setup descriptor | Rust manifest describing the **.tzpkg bytes** |
| Recovery backup | Private NSIS, old protected workflow | Separate Rust-distribution pair, not yet integrated |
| User data | Legacy QA config beside install | Rust state/journal/versions under separate user-data root |
| Production signing | Required, unproven | Required, not attempted by candidate |

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

The Windows job performs **no game client launch or patch**, no
installation, no manifest signing, no setup/NSIS distribution, and
**no artifact upload**. A successful run proves only the limited
cross-repository package-generation contract at the stated commit.
It does not prove actual GUI asset loading, antivirus reputation,
Windows 10/11 compatibility or release provenance.

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
