#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/check_installer_workflows.py
# Amac: BeamPatcher installer icin yalniz Rust Turkuaz primary ve korumali yayin kapisi
# Modul - Python / CI policy checker
# Version: 3.0.0-candidate
# Aciklama: Eski .NET, Velopack, NSIS ve Inno yayini; guvensiz Rust setup uploader'i reddedilir
# Bagimli Oldugu Katman: tools/verify_installer_primary.py | .github/workflows

"""Fail closed if a non-Rust Windows installer or unprotected release path returns."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = "turkuaz-primary-policy.yml"
REQUIRED = (
    "AGENTS.md",
    "tools/verify_installer_primary.py",
    "tools/check_installer_workflows.py",
    "tools/Confirm-TurkuazTrust.ps1",
    "tools/Test-BeamRustProtectedPrimary.ps1",
    "tools/Test-BeamTrustNegative.ps1",
    "tools/check_rust_installer_candidate.py",
    "docs/INSTALLER-STRATEGY-TURKUAZ.md",
    "docs/RUST-INSTALLER-BEAM-COMPAT.md",
    "docs/WINDOWS-SETUP-PATCH-QA.md",
    ".github/workflows/rust-installer-beam-compat.yml",
)
RETIRED = (
    "installer/windows/BeamPatcher-NSIS-Backup.nsi",
    "installer/windows/BeamPatcher-QA.iss",
    "tools/verify_installer_pair.py",
    "tools/Assert-BeamManifestSetupBinding.ps1",
    ".github/workflows/dual-installer-policy.yml",
)
# Only active workflow files are searched; historical code references
# inside regression tests/docs do not reinstate a retired installer.
FORBIDDEN_BUILD_TOKENS = re.compile(
    r"(?i)(?:\bnsis\b|\bmakensis\b|\.nsi\b|build-distribution-pair|"
    r"\bdotnet\b|setup-dotnet|\.csproj\b|\bvelopack\b|\.nupkg\b|"
    r"\bvpk(?:\.exe)?\b|1048931bf7498ab4d4440414c4463e6ee5e7421e)"
)
STANDALONE_ARTIFACT = re.compile(
    r"(?i)(?:inno|nsis|setup\.exe|windows.setup.qa|setup-qa-report|beam-installer)"
)
REQUIRED_RUST_GATE_TOKENS = (
    "TurkuazInstaller",
    "ref: 456a34679661978afc717cc5b08ece11cb0b9a94",
    "tools/verify_installer_primary.py",
    "build-package",
    "--features setup-gui",
    "windows-latest",
    "actions/upload-artifact@v4",
    "environment: windows-installer-signing",
    "build-primary-and-gate:",
    "if: github.event_name == 'workflow_dispatch'",
    "needs: [policy-contract, trust-negative-fixtures]",
    "Confirm-TurkuazTrust.ps1",
    "Test-BeamRustProtectedPrimary.ps1",
    "Test-BeamTrustNegative.ps1",
    "BEAM_VERIFIED_RUST_TURKUAZ_BUNDLE",
    "BEAM_TURKUAZ_CERT_SHA256",
)


def policy_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append(f"missing Rust-only installer policy component: {relative}")
    for relative in RETIRED:
        if (root / relative).exists():
            errors.append(f"retired installer component still present: {relative}")
    installer = root / "installer"
    if any(installer.rglob("*.nsi")):
        errors.append("NSIS source must not exist inside Beam installer tree")
    if any(installer.rglob("*.iss")):
        errors.append("Inno Setup source must not exist inside Beam installer tree")

    workflows = root / ".github/workflows"
    paths = sorted(set(workflows.glob("*.yml")) | set(workflows.glob("*.yaml")))
    protected = workflows / RELEASE_WORKFLOW
    if not protected.is_file():
        errors.append("mandatory signed Rust Turkuaz workflow missing")
    for path in paths:
        raw = path.read_text(encoding="utf-8-sig")
        if FORBIDDEN_BUILD_TOKENS.search(raw):
            errors.append(f"{path.name}: legacy installer build or .NET/NSIS/Velopack reference")
        if path.name == RELEASE_WORKFLOW:
            for token in REQUIRED_RUST_GATE_TOKENS:
                if token not in raw:
                    errors.append(f"{path.name}: mandatory Rust signing gate token missing: {token}")
            if re.search(r"(?im)^\s*-\s*uses:\s*softprops/action-gh-release", raw):
                errors.append("protected Rust CI must not create a production GitHub release")
        else:
            if re.search(r"(?im)^\s*-\s*uses:\s*actions/upload-artifact@", raw):
                if STANDALONE_ARTIFACT.search(raw):
                    errors.append(f"{path.name}: installer upload bypasses Rust-only gate")
            if "softprops/action-gh-release" in raw and STANDALONE_ARTIFACT.search(raw):
                errors.append(f"{path.name}: installer GitHub Release bypass")
    return errors


def main() -> int:
    issues = policy_errors(ROOT)
    for issue in issues:
        print("TURKUAZ-RUST-ONLY FAIL: " + issue, file=sys.stderr)
    if issues:
        return 1
    print("TURKUAZ-RUST-ONLY PASS: retired installers absent; protected Rust primary only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
