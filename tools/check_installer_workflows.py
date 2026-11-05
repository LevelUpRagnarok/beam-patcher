#!/usr/bin/env python3
# Dosya Yolu: REPO_ROOT/tools/check_installer_workflows.py
# Amac: BURAK-INS-001 bypass eden Inno/NSIS tekli setup uploadlarini reddetmek
# Modul - Python / CI static policy checker
# Version: 1.1.0-candidate
# Aciklama: Tum github workflows ve installer source yapisi uzerinde fail-closed disiplini
# Bagimli Oldugu Katman: tools/verify_installer_pair.py | .github/workflows

"""Protect the default distribution contract against standalone setup uploads."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = "dual-installer-policy.yml"
REQUIRED = (
    "installer/windows/BeamPatcher-NSIS-Backup.nsi",
    "tools/verify_installer_pair.py",
    "tools/check_installer_workflows.py",
    "tools/Confirm-TurkuazTrust.ps1",
    "tools/Assert-BeamManifestSetupBinding.ps1",
    "tools/Test-BeamTrustNegative.ps1",
    "docs/INSTALLER-STRATEGY-TURKUAZ.md",
    "docs/WINDOWS-SETUP-PATCH-QA.md",
)


def policy_errors(root: Path) -> list[str]:
    errors = []
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append(f"missing installer policy component: {relative}")

    # Retired standalone setup instructions are a policy bypass even if
    # the workflow no longer uploads the obsolete unsigned artifact.
    guide = root / "docs/WINDOWS-SETUP-PATCH-QA.md"
    if guide.is_file():
        guidance = guide.read_text(encoding="utf-8")
        if re.search(r"(?is)download\s+the\s+short-lived\s+`levelup-beam-windows-setup-qa", guidance):
            errors.append("Windows QA guide advertises retired standalone setup download")

    workflows = root / ".github/workflows"
    candidates = list(workflows.glob("*.yml")) + list(workflows.glob("*.yaml"))
    if not any(p.name == RELEASE_WORKFLOW for p in candidates):
        errors.append("mandatory dual-installer orchestrator not present")
    for path in candidates:
        raw = path.read_text(encoding="utf-8-sig")
        if path.name == RELEASE_WORKFLOW:
            for token in ("TurkuazInstaller", "NSIS", "verify_installer_pair.py",
                          "windows-latest", "actions/upload-artifact",
                          "Confirm-TurkuazTrust.ps1"):
                if token not in raw:
                    errors.append(f"{path.name}: missing {token}")
            continue

        # A nonsigned QA-only NSIS is allowed to compile and smoke-test.
        # An upload of any setup from another workflow is not allowed.
        if re.search(r"(?im)^\s*-\s+uses:\s*actions/upload-artifact@", raw):
            if re.search(r"(?i)(inno|nsis|setup\.exe|windows.setup.qa|setup-qa-report|beam-installer)", raw):
                errors.append(f"{path.name}: standalone setup upload must not bypass dual gate")
        if "softprops/action-gh-release" in raw and "NSIS" in raw:
            errors.append(f"{path.name}: NSIS fallback may never be GitHub Release primary")
    return errors


def main():
    issues = policy_errors(ROOT)
    for issue in issues:
        print("BURAK-INS-001 FAIL: " + issue, file=sys.stderr)
    if issues:
        return 1
    print("BURAK-INS-001 PASS: no standalone setup distribution workflow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
