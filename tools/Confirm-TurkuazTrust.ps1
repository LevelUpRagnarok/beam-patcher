# Dosya Yolu: REPO_ROOT/tools/Confirm-TurkuazTrust.ps1
# Amac: Rust TurkuazSetup Authenticode, detached CMS ve harici pin dogrulamasi
# Modul - PowerShell / Protected Windows signing gate
# Version: 3.0.0-candidate
# Aciklama: Gercek Windows trust zinciri ve bagimsiz publisher pin; Rust release bytes bazinda
# Bagimli Oldugu Katman: tools/verify_installer_primary.py | TurkuazInstaller/rust/CLI.md

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$PrimaryDirectory,
    [Parameter(Mandatory)][string]$PublisherSubject,
    [Parameter(Mandatory)][string]$CertificateSha256,
    [string]$PackageId = 'levelupgt.beampatcher.qa'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Primary = (Resolve-Path -LiteralPath $PrimaryDirectory -ErrorAction Stop).ProviderPath
$CertPin = $CertificateSha256.Trim().ToLowerInvariant()
if ($CertPin -notmatch '^[a-f0-9]{64}$' -or [string]::IsNullOrWhiteSpace($PublisherSubject)) {
    throw 'TURKUAZ-RUST-ONLY: independent publisher subject and SHA256 cert pin required'
}
# SEC-BEAM-RUST-TRUST-001: size, regular-file and reparse preflight
# before decoding certificates, CMS or untrusted manifest bytes.
$Manifest = Join-Path $Primary 'release.yaml'
$Signature = Join-Path $Primary 'release.p7s'
$Trust = Join-Path $Primary 'manifest-trust.yaml'
$Setup = Join-Path $Primary 'TurkuazSetup.exe'
$Bundle = Join-Path $Primary 'Beam.tzsetup'
$Package = Join-Path $Primary 'Beam.tzpkg'
$Inputs = @(
    @{ Path = $Manifest; Limit = 1048576; Label = 'release manifest' },
    @{ Path = $Signature; Limit = 262144; Label = 'detached CMS signature' },
    @{ Path = $Trust; Limit = 65536; Label = 'external trust policy' },
    @{ Path = $Setup; Limit = 8589934592; Label = 'Rust primary EXE' },
    @{ Path = $Bundle; Limit = 8589934592; Label = 'Rust signed bundle' },
    @{ Path = $Package; Limit = 8589934592; Label = 'Rust application tzpkg' }
)
foreach ($Entry in $Inputs) {
    if (-not (Test-Path -LiteralPath $Entry.Path -PathType Leaf)) {
        throw "Missing Rust release input: $($Entry.Label)"
    }
    $Meta = Get-Item -LiteralPath $Entry.Path
    if (($Meta.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Linked Rust release input refused: $($Entry.Label)"
    }
    if ($Meta.Length -eq 0 -or $Meta.Length -gt $Entry.Limit) {
        throw "Rust release input size limit exceeded or empty: $($Entry.Label)"
    }
}
# SEC-BEAM-RUST-TRUST-002: never accept a test signature as a
# production Windows publisher. Validate actual trust chain and pinned
# signer of THE ONE user-facing TurkuazSetup.exe.
$Auth = Get-AuthenticodeSignature -LiteralPath $Setup
if ($Auth.Status -ne 'Valid' -or $null -eq $Auth.SignerCertificate) {
    throw "Rust TurkuazSetup Authenticode not trusted: $($Auth.Status)"
}
$PublisherCert = $Auth.SignerCertificate
$PublisherHash = [Convert]::ToHexString(
    [Security.Cryptography.SHA256]::HashData($PublisherCert.RawData)
).ToLowerInvariant()
if ($PublisherCert.Subject -cne $PublisherSubject -or $PublisherHash -cne $CertPin) {
    throw 'Turkuaz Rust publisher/certificate pin mismatch'
}
$Now = [DateTime]::UtcNow
if ($Now -lt $PublisherCert.NotBefore.ToUniversalTime() -or
    $Now -gt $PublisherCert.NotAfter.ToUniversalTime()) {
    throw 'Turkuaz Rust Authenticode signer is outside its validity period'
}
# SEC-BEAM-RUST-TRUST-003: validate one detached CMS signature on the
# exact signed Rust release.yaml bytes, including the Windows trust chain.
Add-Type -AssemblyName 'System.Security.Cryptography.Pkcs'
$Content = [Security.Cryptography.Pkcs.ContentInfo]::new([IO.File]::ReadAllBytes($Manifest))
$Cms = [Security.Cryptography.Pkcs.SignedCms]::new($Content, $true)
$Cms.Decode([IO.File]::ReadAllBytes($Signature))
$Cms.CheckSignature($false)
if ($Cms.SignerInfos.Count -ne 1 -or $null -eq $Cms.SignerInfos[0].Certificate) {
    throw 'Expected exactly one detached CMS Rust manifest signer'
}
$CmsSigner = $Cms.SignerInfos[0].Certificate
$CmsSha = [Convert]::ToHexString(
    [Security.Cryptography.SHA256]::HashData($CmsSigner.RawData)
).ToLowerInvariant()
if ($CmsSigner.Subject -cne $PublisherSubject -or $CmsSha -cne $CertPin) {
    throw 'Rust CMS signer does not match independent certificate pin'
}
if ($Now -lt $CmsSigner.NotBefore.ToUniversalTime() -or
    $Now -gt $CmsSigner.NotAfter.ToUniversalTime()) {
    throw 'Detached Rust CMS signer certificate is outside its validity period'
}
# This externally supplied policy is NOT allowed to select a different
# publisher from the protected GitHub environment's pinned certificate.
$TrustText = [Text.UTF8Encoding]::new($false, $true).GetString(
    [IO.File]::ReadAllBytes($Trust)
)
$ExpectedFields = @{
    'id' = $PackageId
    'certificate_sha256' = $CertPin
    'publisher_subject' = $PublisherSubject
}
foreach ($Entry in $ExpectedFields.GetEnumerator()) {
    $field = [regex]::Escape($Entry.Key)
    $value = [regex]::Escape($Entry.Value)
    $pattern = '(?m)^\s*' + $field + ':\s*["' + [char]39 + ']?' +
               $value + '["' + [char]39 + ']?\s*$'
    if (-not [regex]::IsMatch($TrustText, $pattern)) {
        throw "External Rust trust policy missing pinned field: $($Entry.Key)"
    }
}
Write-Output 'TURKUAZ_RUST_REAL_CMS_AUTHENTICODE_AND_EXTERNAL_PIN_OK'
