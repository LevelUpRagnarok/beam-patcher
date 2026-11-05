<!--
Dosya Yolu: REPO_ROOT/docs/RUST-INSTALLER-BEAM-COMPAT.md
Amac: Beam icin Rust TurkuazInstaller tek-primary uyumluluk ve kabul sinirlari
Modul - Markdown / Rust Windows QA
Version: 1.4.0-candidate
Aciklama: Gercek Beam QA, tek TurkuazSetup; product signer/release ayri
Bagimli Oldugu Katman: tools/Test-BeamRustEphemeralLifecycle.ps1 | tools/check_rust_installer_candidate.py
-->

# BeamPatcher / TurkuazInstaller Rust compatibility

**Draft integration: test-signed Windows acceptance only.**

Rust upstream revision is pinned to
456a34679661978afc717cc5b08ece11cb0b9a94.
The legacy Turkuaz product gate uses a different .NET revision
and Velopack; never assume a cross-format upgrade is automatic.

## What real hosted-Windows CI tests

The pipeline builds the actual Beam QA x64 EXE and the upstream Rust
CLI with locked dependencies. It stages the Beam executable, safe
loopback-only configuration, README and local theme assets. It creates
a Rust v2 .tzpkg and manifest and runs the offline package checker:
exact package ID, version, SHA-256, whole-package byte count, entrypoint,
each payload hash, path containment and case-collision rejection.

tools/Test-BeamRustEphemeralLifecycle.ps1 creates a short-lived test
certificate in GitHub-hosted Windows and checks:

- Edited detached CMS manifest is rejected.
- QA 1.0.1 installs; QA 1.0.2 updates.
- Tampered managed file is rejected; repair restores it.
- Signed-policy rollback returns to QA 1.0.1.
- Uninstall preserves a separate unmanaged user-owned file.
- A single TurkuazSetup.exe is created from the signed QA .tzsetup,
  using the pinned Rust setup-gui stub.
- The single primary has a valid PE header, a temporary Authenticode
  signature pinned to the CI signer, and a wrong-publisher test fails.
- Primary install-self and uninstall preserve unmanaged user data.

The GUI wizard is **not automated**, only the self-extractor CLI
entry point. The setup-gui binary is built with the Windows GUI subsystem;
the Windows smoke uses a separate ProcessStartInfo with argument-vector
quoting, asynchronous pipe draining and a bounded wait for the real native
exit code before checking installed state. A PowerShell direct invocation
with a stale LASTEXITCODE is never accepted as installation proof. Neither test certificate nor test EXE is authorized for
end-user distribution. No game client is launched. CI deletes test
certificates and temporary installs; no setup artifact is uploaded.

## Remaining release blockers

A real publisher-signed Rust release requires independently
provisioned certificate trust, protected source/artifact provenance,
real native Windows 10/11 setup UI acceptance, update/repair/rollback,
shortcuts, registry, user-consented migration from earlier installs,
Unicode/space paths and cancellation/failed-install recovery.
Passing the ephemeral signing fixture does not satisfy these.

Current protected Turkuaz primary workflow still validates a
legacy-compatible .NET distribution; migration to the Rust primary
needs separate reviewed production signing and rollout acceptance.
The retired secondary installer is not a release dependency.

Run the synthetic offline tests:

    python -m unittest discover -s tools/tests -p test_rust_installer_candidate.py -v

See docs/INSTALLER-STRATEGY-TURKUAZ.md.
