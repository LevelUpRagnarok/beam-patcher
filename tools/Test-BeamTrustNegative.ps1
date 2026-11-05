# Dosya Yolu: REPO_ROOT/tools/Test-BeamTrustNegative.ps1
# Amac: Gercek signer gerektirmeyen CMS preflight ve Setup identity negatif testleri
# Modul - PowerShell / Windows offline security QA
# Version: 1.0.0-candidate
# Aciklama: Sentetik fixture ile manifest/size/hash/identity red; Authenticode PASS iddiasi yok
# Bagimli Oldugu Katman: tools/Confirm-TurkuazTrust.ps1 | tools/Assert-BeamManifestSetupBinding.ps1

[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Verifier = Join-Path $PSScriptRoot 'Confirm-TurkuazTrust.ps1'
$Binding = Join-Path $PSScriptRoot 'Assert-BeamManifestSetupBinding.ps1'
$Root = Join-Path ([IO.Path]::GetTempPath()) ('beam-trust-qa-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Root -Force | Out-Null
$Primary = Join-Path $Root 'primary'
New-Item -ItemType Directory -Path $Primary -Force | Out-Null
$Manifest = Join-Path $Primary 'installer-manifest.yml'
$Signature = Join-Path $Primary 'installer-manifest.yml.p7s'
$Trust = Join-Path $Primary 'manifest-trust.yml'
$Setup = Join-Path $Primary 'Beam-Velopack-Setup.exe'
$PackageId = 'levelupgt.beampatcher.qa'
$Version = '1.0.1'
$Pin = 'a' * 64

function Write-Manifest([string]$Value) {
    [IO.File]::WriteAllText($Manifest, $Value, [Text.UTF8Encoding]::new($false))
}
function Assert-Rejection([string]$Case, [string]$Expected, [scriptblock]$Action) {
    $Message = ''
    try { & $Action | Out-Null } catch { $Message = $_.Exception.Message }
    if ($Message -notmatch [regex]::Escape($Expected)) {
        throw "Negative case [$Case] was not rejected as expected: $Message"
    }
}
function Test-Identity {
    & $Binding -ManifestPath $Manifest -SetupPath $Setup -PackageId $PackageId -Version $Version | Out-Null
}
function Test-SignerPreflight {
    & $Verifier -PrimaryDirectory $Primary -PublisherSubject 'CN=QA Structural Fixture' -CertificateSha256 $Pin | Out-Null
}

try {
    [IO.File]::WriteAllBytes($Setup, [Text.Encoding]::ASCII.GetBytes(('BEAM-QA-SETUP-SYNTHETIC' * 40)))
    $Sha = (Get-FileHash -LiteralPath $Setup -Algorithm SHA256).Hash.ToLowerInvariant()
    $Length = (Get-Item -LiteralPath $Setup).Length
    $Template = @"
schema_version: 1
package:
  id: "$PackageId"
  version: "$Version"
  channel: beta
artifact:
  uri: "file:///TEST-ONLY-setup.exe"
  sha256: "$Sha"
  size_bytes: $Length
install:
  mode: full
"@
    Write-Manifest $Template
    Test-Identity

    Write-Manifest ($Template.Replace($Sha, ('f' * 64)))
    Assert-Rejection 'wrong SHA' 'SHA-256/size mismatch' { Test-Identity }

    Write-Manifest ($Template.Replace("size_bytes: $Length", "size_bytes: $($Length + 1)"))
    Assert-Rejection 'wrong byte count' 'SHA-256/size mismatch' { Test-Identity }

    Write-Manifest ($Template.Replace("id: ""$PackageId""", 'id: "other-application"'))
    Assert-Rejection 'wrong package' 'identity or schema mismatch' { Test-Identity }

    Write-Manifest ($Template + [Environment]::NewLine + 'package:' + [Environment]::NewLine + '  id: evil')
    Assert-Rejection 'duplicate package block' 'Duplicate signed manifest section' { Test-Identity }

    # A real hash in an unrelated comment must not rescue a fake
    # artifact.sha256 from the signed structure.
    Write-Manifest ('# ' + $Sha + [Environment]::NewLine + $Template.Replace($Sha, ('f' * 64)))
    Assert-Rejection 'unrelated hash comment' 'SHA-256/size mismatch' { Test-Identity }

    Write-Manifest $Template
    $Original = [IO.File]::ReadAllBytes($Setup)
    [IO.File]::WriteAllBytes($Setup, [Text.Encoding]::ASCII.GetBytes('tampered-synthetic-setup'))
    Assert-Rejection 'tampered actual setup bytes' 'SHA-256/size mismatch' { Test-Identity }
    [IO.File]::WriteAllBytes($Setup, $Original)
    Test-Identity

    # Refuse oversized metadata before signer and Authenticode checks.
    [IO.File]::WriteAllText($Signature, 'fake-cms')
    [IO.File]::WriteAllText($Trust, 'fake-external-trust')
    Write-Manifest ('x' * 1048577)
    Assert-Rejection 'manifest cap' 'size limit exceeded' { Test-SignerPreflight }

    Write-Manifest $Template
    [IO.File]::WriteAllText($Signature, ('x' * 262145))
    Assert-Rejection 'CMS cap' 'size limit exceeded' { Test-SignerPreflight }

    [IO.File]::WriteAllText($Signature, 'fake-cms')
    [IO.File]::WriteAllText($Trust, ('x' * 65537))
    Assert-Rejection 'external trust cap' 'size limit exceeded' { Test-SignerPreflight }

    Write-Output 'BEAM_OFFLINE_TRUST_NEGATIVE_FIXTURES_PASS (NOT SIGNED E2E)'
} finally {
    Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue
}
