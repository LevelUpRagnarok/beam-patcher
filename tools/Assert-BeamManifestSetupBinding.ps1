# Dosya Yolu: REPO_ROOT/tools/Assert-BeamManifestSetupBinding.ps1
# Amac: Stable v1 imzali manifestin ilk kurulum Setup.exe SHA-256 ve boyut bagini sinar
# Modul - PowerShell / Offline manifest structure
# Version: 1.0.0-candidate
# Aciklama: Salt okunur; CMS imzasi ve sertifika guveni burada DOGRULANMAZ
# Bagimli Oldugu Katman: tools/Confirm-TurkuazTrust.ps1 | Installer Stable v1 manifest

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ManifestPath,
    [Parameter(Mandatory)][string]$SetupPath,
    [Parameter(Mandatory)][string]$PackageId,
    [Parameter(Mandatory)][string]$Version
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw 'Signed manifest file missing'
}
$ManifestMeta = Get-Item -LiteralPath $ManifestPath
if ($ManifestMeta.Length -eq 0 -or $ManifestMeta.Length -gt 1048576 -or
    ($ManifestMeta.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'Manifest size/reparse preflight failed'
}

# Decode exact signed bytes with a strict UTF-8 decoder.
$ManifestText = [Text.UTF8Encoding]::new($false, $true).GetString([IO.File]::ReadAllBytes($ManifestPath))
$Sections = @{ 'package' = 0; 'artifact' = 0 }
$Fields = @{}
$Section = ''
foreach ($Line in [regex]::Split($ManifestText, '\r?\n')) {
    if ($Line -cmatch '^([a-zA-Z_][a-zA-Z0-9_]*):[ \t]*$') {
        $Section = $Matches[1]
        if ($Sections.ContainsKey($Section)) {
            $Sections[$Section]++
            if ($Sections[$Section] -ne 1) {
                throw "Duplicate signed manifest section: $Section"
            }
        }
        continue
    }
    if ($Line -cmatch '^[a-zA-Z_][a-zA-Z0-9_]*:') {
        $Section = ''
        continue
    }
    if ($Section -eq 'package' -and $Line -cmatch '^  (id|version):[ \t]*([^#\r\n]+?)[ \t]*$') {
        $Key = "package.$($Matches[1])"
        $Raw = $Matches[2].Trim()
    } elseif ($Section -eq 'artifact' -and $Line -cmatch '^  (sha256|size_bytes):[ \t]*([^#\r\n]+?)[ \t]*$') {
        $Key = "artifact.$($Matches[1])"
        $Raw = $Matches[2].Trim()
    } else {
        continue
    }
    if ($Fields.ContainsKey($Key)) { throw "Duplicate signed manifest field: $Key" }
    if (($Raw.StartsWith('"') -and $Raw.EndsWith('"')) -or
        ($Raw.StartsWith("'") -and $Raw.EndsWith("'"))) {
        $Raw = $Raw.Substring(1, $Raw.Length - 2)
    } elseif ($Raw.Contains('"') -or $Raw.Contains("'")) {
        throw "Invalid signed manifest quote: $Key"
    }
    $Fields[$Key] = $Raw
}
if ($Sections['package'] -ne 1 -or $Sections['artifact'] -ne 1 -or
    $Fields['package.id'] -cne $PackageId -or
    $Fields['package.version'] -cne $Version) {
    throw 'Signed manifest package identity or schema mismatch'
}

# The Stable v1 initial-install artifact must identify *Setup.exe*.
# A matching digest anywhere else (including full nupkg or comments)
# cannot authorize an initial installer.
$Setup = $SetupPath
if (-not (Test-Path -LiteralPath $Setup -PathType Leaf)) {
    throw 'Initial Velopack Setup file missing'
}
if (((Get-Item -LiteralPath $Setup).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'Linked initial Velopack Setup refused'
}
$ActualSetupHash = (Get-FileHash -LiteralPath $Setup -Algorithm SHA256).Hash.ToLowerInvariant()
$ActualSetupSize = (Get-Item -LiteralPath $Setup).Length
$ExpectedHash = [string]$Fields['artifact.sha256']
$ExpectedSizeText = [string]$Fields['artifact.size_bytes']
[long]$ExpectedSize = 0
if ($ExpectedHash -cnotmatch '^[a-f0-9A-F]{64}$' -or
    -not [long]::TryParse($ExpectedSizeText, [ref]$ExpectedSize) -or
    $ExpectedSize -le 0 -or $ExpectedSize -ne $ActualSetupSize -or
    $ExpectedHash.ToLowerInvariant() -cne $ActualSetupHash) {
    throw 'Signed initial Velopack Setup artifact SHA-256/size mismatch'
}
# Structural binding only. A caller MUST verify CMS and Windows signer first.
Write-Output 'BURAK-INS-001_SETUP_STRUCTURE_BOUND_ONLY'
