# Dosya Yolu: REPO_ROOT/tools/Test-BeamTrustNegative.ps1
# Amac: Rust tek-primary CMS ve Windows publisher trust negatif regresyonlari
# Modul - PowerShell / Hosted Windows security preflight
# Version: 3.0.0-candidate
# Aciklama: Test signer disinda secret gerektirmez; gercek urun imzasini PASS saymaz
# Bagimli Oldugu Katman: tools/Confirm-TurkuazTrust.ps1 | tools/verify_installer_primary.py
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Verifier = Join-Path $PSScriptRoot 'Confirm-TurkuazTrust.ps1'
$Root = Join-Path ([IO.Path]::GetTempPath()) ('beam-rust-trust-negative-' + [Guid]::NewGuid().ToString('N'))
$Primary = Join-Path $Root 'primary'
$Manifest = Join-Path $Primary 'release.yaml'
$Signature = Join-Path $Primary 'release.p7s'
$Trust = Join-Path $Primary 'manifest-trust.yaml'
$Setup = Join-Path $Primary 'TurkuazSetup.exe'
$Package = Join-Path $Primary 'Beam.tzpkg'
$Bundle = Join-Path $Primary 'Beam.tzsetup'
$Pin = 'a' * 64
$Publisher = 'CN=Beam Rust CI Structural Fixture'
$Utf8 = [Text.UTF8Encoding]::new($false)
function Assert-Reject([string]$Case, [string]$Expected, [scriptblock]$Action) {
    $message = ''
    try { & $Action | Out-Null } catch { $message = $_.Exception.Message }
    if (-not $message.Contains($Expected)) {
        throw "Rust trust negative [$Case] failed: $message"
    }
}
function Verify-Candidate {
    & $Verifier -PrimaryDirectory $Primary -PublisherSubject $Publisher -CertificateSha256 $Pin | Out-Null
}
try {
    New-Item -ItemType Directory -Force -Path $Primary | Out-Null
    [IO.File]::WriteAllText($Manifest, 'schema_version: 1' + [Environment]::NewLine, $Utf8)
    [IO.File]::WriteAllBytes($Signature, [byte[]](1,2,3,4))
    [IO.File]::WriteAllText($Trust, 'test-no-production-trust', $Utf8)
    [IO.File]::WriteAllBytes($Setup, [Text.Encoding]::ASCII.GetBytes('MZ' + ('test-only' * 200)))
    [IO.File]::WriteAllBytes($Bundle, [Text.Encoding]::ASCII.GetBytes('test-tzsetup' * 80))
    [IO.File]::WriteAllBytes($Package, [Text.Encoding]::ASCII.GetBytes('test-tzpkg' * 80))
    Assert-Reject 'untrusted unsigned EXE' 'Authenticode not trusted' { Verify-Candidate }
    Assert-Reject 'invalid independent publisher cert pin' 'SHA256 cert pin required' {
        & $Verifier -PrimaryDirectory $Primary -PublisherSubject $Publisher -CertificateSha256 'oops'
    }
    [IO.File]::WriteAllText($Manifest, ('m' * 1048577), $Utf8)
    Assert-Reject 'Rust manifest size cap' 'size limit exceeded' { Verify-Candidate }
    [IO.File]::WriteAllText($Manifest, 'schema_version: 1', $Utf8)
    [IO.File]::WriteAllText($Signature, ('s' * 262145), $Utf8)
    Assert-Reject 'Rust CMS size cap' 'size limit exceeded' { Verify-Candidate }
    [IO.File]::WriteAllBytes($Signature, [byte[]](1,2,3,4))
    [IO.File]::WriteAllText($Trust, ('t' * 65537), $Utf8)
    Assert-Reject 'external publisher policy size cap' 'size limit exceeded' { Verify-Candidate }
    [IO.File]::WriteAllText($Trust, 'test-no-production-trust', $Utf8)
    Remove-Item -LiteralPath $Package
    Assert-Reject 'missing Rust tzpkg' 'Missing Rust release input' { Verify-Candidate }
    [IO.File]::WriteAllBytes($Package, [Text.Encoding]::ASCII.GetBytes('test-tzpkg' * 80))

    # A detached signature must reject even a one-byte change in the
    # exact signed manifest, independently of OS publisher trust.
    Add-Type -AssemblyName System.Security.Cryptography.Pkcs
    $content = [Security.Cryptography.Pkcs.ContentInfo]::new(
        [Text.Encoding]::UTF8.GetBytes('signed-message')
    )
    $cert = New-SelfSignedCertificate -Subject $Publisher -CertStoreLocation 'Cert:\CurrentUser\My' -Type CodeSigningCert -KeyAlgorithm RSA -KeyLength 2048 -HashAlgorithm SHA256 -NotAfter (Get-Date).AddDays(1)
    try {
        $cms = [Security.Cryptography.Pkcs.SignedCms]::new($content, $true)
        $cms.ComputeSignature([Security.Cryptography.Pkcs.CmsSigner]::new($cert))
        $verified = [Security.Cryptography.Pkcs.SignedCms]::new($content, $true)
        $verified.Decode($cms.Encode())
        $verified.CheckSignature($true)
        $tampered = [Security.Cryptography.Pkcs.SignedCms]::new(
            [Security.Cryptography.Pkcs.ContentInfo]::new([Text.Encoding]::UTF8.GetBytes('tampered-message')),
            $true
        )
        $tampered.Decode($cms.Encode())
        Assert-Reject 'detached CMS byte tamper' 'signature' { $tampered.CheckSignature($true) }
    } finally {
        Remove-Item -LiteralPath ('Cert:\CurrentUser\My\' + $cert.Thumbprint) -Force -ErrorAction SilentlyContinue
    }
    Write-Output 'BEAM_RUST_TRUST_NEGATIVE_FIXTURES_PASS_NOT_PRODUCT_SIGNING'
} finally {
    Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue
}
