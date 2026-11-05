#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/check_installer_workflows.py
# Amac: TURKUAZ-ONLY-001; NSIS derleme/yayinini ve bagimsiz setup dagitimini engeller
# Modul - Python / CI policy checker
# Version: 2.0.0-candidate
# Aciklama: GitHub Actions ve kurulum kaynaklarinda tek TurkuazInstaller primary kuralini zorlar
# Bagimli Oldugu Katman: tools/verify_installer_primary.py | .github/workflows

"""Fail closed unless Beam's only installer publication path is TurkuazInstaller."""

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
    "tools/Assert-BeamManifestSetupBinding.ps1",
    "tools/Test-BeamTrustNegative.ps1",
    "docs/INSTALLER-STRATEGY-TURKUAZ.md",
    "docs/WINDOWS-SETUP-PATCH-QA.md",
    ".github/workflows/rust-installer-beam-compat.yml",
)
RETIRED = (
    "installer/windows/BeamPatcher-NSIS-Backup.nsi",
    "tools/verify_installer_pair.py",
    ".github/workflows/dual-installer-policy.yml",
)
FORBIDDEN_BUILD_TOKENS = re.compile(
    r"(?i)(?:\bnsis\b|\bmakensis\b|\.nsi\b|build-distribution-pair)"
)
STANDALONE_ARTIFACT = re.compile(
    r"(?i)(?:inno|nsis|setup\.exe|windows.setup.qa|setup-qa-report|beam-installer)"
)


def policy_errors(root: Path) -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append(f"missing Turkuaz-only policy component: {relative}")
    for relative in RETIRED:
        if (root / relative).exists():
            errors.append(f"retired installer component still present: {relative}")
    if any((root / "installer").rglob("*.nsi")):
        errors.append("NSIS source must not exist inside Beam installer tree")

    guide = root / "docs/WINDOWS-SETUP-PATCH-QA.md"
    if guide.is_file() and re.search(
        r"(?is)download\s+the\s+short-lived\s+" +
        r"\x60levelup-beam-windows-setup-qa",
        guide.read_text(encoding="utf-8"),
    ):
        errors.append("Windows QA guide advertises retired standalone setup download")

    workflows = root / ".github/workflows"
    candidates = list(workflows.glob("*.yml")) + list(workflows.glob("*.yaml"))
    primary = workflows / RELEASE_WORKFLOW
    if not primary.is_file():
        errors.append("mandatory Turkuaz-only primary workflow absent")

    for path in candidates:
        raw = path.read_text(encoding="utf-8-sig")
        if FORBIDDEN_BUILD_TOKENS.search(raw):
            errors.append(f"{path.name}: deprecated NSIS/pair build reference")
        if path.name == RELEASE_WORKFLOW:
            for token in (
                "TurkuazInstaller",
                "tools/verify_installer_primary.py",
                "windows-latest",
                "actions/upload-artifact@v4",
                "environment: windows-installer-signing",
                "build-primary-and-gate:",
                "if: github.event_name == 'workflow_dispatch'",
                "Confirm-TurkuazTrust.ps1",
                "Test-BeamTrustNegative.ps1",
            ):
                if token not in raw:
                    errors.append(f"{path.name}: required primary gate missing {token}")
        else:
            if re.search(r"(?im)^\s*-\s*uses:\s*actions/upload-artifact@", raw):
                if STANDALONE_ARTIFACT.search(raw):
                    errors.append(
                        f"{path.name}: installer artifact bypasses primary-only gate"
                    )
            if "softprops/action-gh-release" in raw and STANDALONE_ARTIFACT.search(raw):
                errors.append(f"{path.name}: installer GitHub Release bypass")

    return errors


def main() -> int:
    issues = policy_errors(ROOT)
    for issue in issues:
        print("TURKUAZ-ONLY-001 FAIL: " + issue, file=sys.stderr)
    if issues:
        return 1
    print("TURKUAZ-ONLY-001 PASS: no NSIS build and only protected Turkuaz primary upload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
