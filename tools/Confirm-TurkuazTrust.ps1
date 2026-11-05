# Dosya Yolu: REPO_ROOT/tools/Confirm-TurkuazTrust.ps1
# Amac: Turkuaz primary installer manifest CMS, external pin ve Authenticode gercek dogrulama
# Modul - PowerShell / Protected Windows signing gate
# Version: 1.1.0-candidate
# Aciklama: Bounded CMS verification and signed initial Velopack Setup identity
# Bagimli Oldugu Katman: tools/verify_installer_pair.py | TurkuazInstaller/docs/MANIFEST_TRUST.md

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$PrimaryDirectory,
    [Parameter(Mandatory)][string]$PublisherSubject,
    [Parameter(Mandatory)][string]$CertificateSha256,
    [string]$PackageId = 'levelupgt.beampatcher.qa'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Primary = (Resolve-Path -LiteralPath $PrimaryDirectory).Path
$CertPin = $CertificateSha256.Trim().ToLowerInvariant()
if ($CertPin -notmatch '^[a-f0-9]{64}$' -or [string]::IsNullOrWhiteSpace($PublisherSubject)) {
    throw 'BURAK-INS-001: independent signer subject and 64-hex SHA256 pin required'
}
# SEC-BEAM-TRUST-001: refuse oversized metadata before any CMS parsing.
$Manifest = Join-Path $Primary 'installer-manifest.yml'
$Signature = Join-Path $Primary 'installer-manifest.yml.p7s'
$Trust = Join-Path $Primary 'manifest-trust.yml'
$Inputs = @(
    @{ Path = $Manifest; Limit = 1048576; Label = 'manifest' },
    @{ Path = $Signature; Limit = 262144; Label = 'detached CMS signature' },
    @{ Path = $Trust; Limit = 65536; Label = 'external trust policy' }
)
foreach ($Entry in $Inputs) {
    if (-not (Test-Path -LiteralPath $Entry.Path -PathType Leaf)) {
        throw "Missing signed metadata: $($Entry.Label)"
    }
    $Meta = Get-Item -LiteralPath $Entry.Path
    if (($Meta.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Linked signed metadata refused: $($Entry.Label)"
    }
    if ($Meta.Length -eq 0 -or $Meta.Length -gt $Entry.Limit) {
        throw "Signed metadata size limit exceeded or empty: $($Entry.Label)"
    }
}

$BinPaths = @(
    'TurkuazInstaller.Bootstrapper.exe',
    'app/TurkuazInstaller.WinUI.exe',
    'cli/TurkuazInstaller.Cli.exe'
)
foreach ($Rel in $BinPaths) {
    $Binary = Join-Path $Primary $Rel
    if (-not (Test-Path -LiteralPath $Binary -PathType Leaf)) { throw "Missing signed Turkuaz executable: $Rel" }
    $Sig = Get-AuthenticodeSignature -LiteralPath $Binary
    if ($Sig.Status -ne 'Valid' -or $null -eq $Sig.SignerCertificate) {
        throw "Turkuaz binary Authenticode not trusted: $Rel, $($Sig.Status)"
    }
    $Sign = $Sig.SignerCertificate
    $Hash = [Convert]::ToHexString(
        [Security.Cryptography.SHA256]::HashData($Sign.RawData)
    ).ToLowerInvariant()
    if ($Sign.Subject -cne $PublisherSubject -or $Hash -cne $CertPin) {
        throw "Turkuaz publisher/certificate pin mismatch: $Rel"
    }
}
# Check the detached CMS signature against the exact bytes saved on disk.
Add-Type -AssemblyName 'System.Security.Cryptography.Pkcs'
$Content = [Security.Cryptography.Pkcs.ContentInfo]::new([IO.File]::ReadAllBytes($Manifest))
$Cms = [Security.Cryptography.Pkcs.SignedCms]::new($Content, $true)
$Cms.Decode([IO.File]::ReadAllBytes($Signature))
$Cms.CheckSignature($false)
if ($Cms.SignerInfos.Count -ne 1 -or $null -eq $Cms.SignerInfos[0].Certificate) {
    throw 'Expected one detached CMS manifest signer'
}
$Signer = $Cms.SignerInfos[0].Certificate
$SignerSha = [Convert]::ToHexString(
    [Security.Cryptography.SHA256]::HashData($Signer.RawData)
).ToLowerInvariant()
if ($Signer.Subject -cne $PublisherSubject -or $SignerSha -cne $CertPin) {
    throw 'Detached CMS manifest signer does not match independent certificate pin'
}
$Now = [DateTime]::UtcNow
if ($Now -lt $Signer.NotBefore.ToUniversalTime() -or
    $Now -gt $Signer.NotAfter.ToUniversalTime()) {
    throw 'Detached CMS signer certificate is outside its validity period'
}
$TrustText = Get-Content -LiteralPath $Trust -Raw -Encoding utf8
if (-not $TrustText.Contains("id: $PackageId") -or
    -not $TrustText.Contains("certificate_sha256: $CertPin") -or
    -not $TrustText.Contains("publisher_subject: $PublisherSubject")) {
    throw 'External trust store does not contain the exact package and publisher pin'
}
# SEC-BEAM-TRUST-002: bind the already CMS-verified manifest to the
# exact first-install Velopack Setup; reject free-text/nupkg-only matches.
$Setup = Join-Path $Primary 'Beam-Velopack-Setup.exe'
$FullNupkg = Join-Path $Primary 'Beam-full.nupkg'
if (-not (Test-Path -LiteralPath $FullNupkg -PathType Leaf)) {
    throw 'Missing pinned Velopack full nupkg'
}
$BindingScript = Join-Path $PSScriptRoot 'Assert-BeamManifestSetupBinding.ps1'
if (-not (Test-Path -LiteralPath $BindingScript -PathType Leaf)) {
    throw 'Missing initial Setup identity verifier'
}
& $BindingScript -ManifestPath $Manifest -SetupPath $Setup -PackageId $PackageId -Version '1.0.1' | Out-Null
Write-Output 'BURAK-INS-001_REAL_SIGNATURE_AND_EXTERNAL_PIN_OK'
