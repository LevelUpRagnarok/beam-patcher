<!--
Dosya Yolu: REPO_ROOT/docs/RUST-INSTALLER-BEAM-COMPAT.md
Amac: Beam icin Rust TurkuazInstaller tek-primary uyumluluk ve kabul sinirlari
Modul - Markdown / Rust Windows QA
Version: 2.0.0-candidate
Aciklama: Gercek Beam QA, tek TurkuazSetup; product signer/release ayri
Bagimli Oldugu Katman: tools/Test-BeamRustEphemeralLifecycle.ps1 | tools/check_rust_installer_candidate.py
-->

# BeamPatcher / TurkuazInstaller Rust compatibility

**Draft integration: test-signed Windows acceptance only.**

Rust upstream revision is pinned to
456a34679661978afc717cc5b08ece11cb0b9a94.
The protected product gate now uses this same pinned Rust source,
but real publisher signing and native acceptance remain separate.

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

The protected primary workflow now builds Rust Beam packages, requires
the same exact signed .tzpkg inside .tzsetup, validates the single
TurkuazSetup.exe publisher chain, and executes hosted Windows
install-self/verify/uninstall. Real Windows 10/11 GUI and user-consented
migration acceptance are still required. No secondary installer is built.

Run the synthetic offline tests:

    python -m unittest discover -s tools/tests -p test_rust_installer_candidate.py -v

See docs/INSTALLER-STRATEGY-TURKUAZ.md.

## Product payload safety gate (2026-11-17)

The protected `build-primary-and-gate` path now explicitly calls
`tools/check_product_release_payload.py` before accepting an externally
signed bundle. It checks the staged Rust v2 `.tzpkg` product identity,
exact rebuilt Beam executable bytes and strict production profile.

**This is intentionally BLOCKED on the current `main` baseline**:
the protected workflow still stages `levelupgt.beampatcher.qa` with
`installer/windows/config.qa.yml`. The new gate refuses that QA package
even if a publisher-signed bundle is later provided. Removing this check
is not a valid workaround for release. The isolated Rust QA pipeline
continues to test its QA-only artifact separately.

For a future product candidate, the staged `config.yml` must contain
an unambiguous UTF-8 **JSON object** (JSON syntax is valid YAML for Beam's
`serde_yaml` parser), not a free-form YAML document. Its package version,
non-QA identity, real HTTPS endpoints, checksums and supported
region/channel client guard must be verified; the signed package must
contain exactly the source-built Beam executable. No example URLs,
unverified client files, QA sentinel filenames or hard-coded machine
install locations are acceptable.

This preflight is *structural*, not an endpoint ownership check, runtime
client acceptance, actual CMS/Authenticode signature verification or GUI
smoke. A later reviewed implementation must bind a real approved product
config and package ID to the protected build and signing evidence before
the protected workflow can pass. Do not publish either a production tag
or an unsigned/test-signed setup based solely on this change.
