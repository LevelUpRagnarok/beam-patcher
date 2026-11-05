# Dosya Yolu: REPO_ROOT/tools/Test-BeamRustEphemeralLifecycle.ps1
# Amac: Beam QA Rust lifecycle ile Turkuaz GUI primary ve NSIS private pair'i test etmek
# Modul - PowerShell Integration QA
# Version: 1.1.0-candidate
# Aciklama: Gecici CI sertifikasi, gercek Beam EXE, signed bundle; production imzasi degil
# Bagimli Oldugu Katman: .github/workflows/rust-installer-beam-compat.yml | TurkuazInstaller/rust/CLI.md
[CmdletBinding()]
param([Parameter(Mandatory)][string]$InstallerPath,
      [Parameter(Mandatory)][string]$PayloadDirectory,
      [Parameter(Mandatory)][string]$GuiStubPath,
      [Parameter(Mandatory)][string]$MakensisPath)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:BEAM_RUNNER_KIND -ne 'github-hosted' -or
    [string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
    throw 'Signed candidate fixture requires disposable GitHub-hosted Windows CI'
}
$Cli = (Resolve-Path -LiteralPath $InstallerPath).ProviderPath
$Payload = (Resolve-Path -LiteralPath $PayloadDirectory).ProviderPath
$GuiStub = (Resolve-Path -LiteralPath $GuiStubPath).ProviderPath
$Makensis = (Resolve-Path -LiteralPath $MakensisPath).ProviderPath
if (-not (Test-Path -LiteralPath (Join-Path $Payload 'beam-patcher.exe') -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $Payload 'config.yml') -PathType Leaf) -or
    -not [IO.File]::ReadAllText((Join-Path $Payload 'config.yml')).Contains('qa_only: true')) {
    throw 'Expected real Beam executable with QA-only config'
}
$Root = Join-Path $env:RUNNER_TEMP ('beam-rust-test-signer-' + [Guid]::NewGuid().ToString('N'))
$Work = Join-Path $Root 'work'
$Target = Join-Path $Root 'installed'
$State = Join-Path $Root 'state'
$Trust = Join-Path $Work 'trust.yaml'
$PackageId = 'levelupgt.beampatcher.qa'
$Certificate = $null
$Utf8 = [Text.UTF8Encoding]::new($false)
function Run-Cli {
    param([string]$Label, [string[]]$ArgsList, [switch]$Reject)
    Write-Host "CI: $Label"
    $output = & $Cli @ArgsList 2>&1
    $code = $LASTEXITCODE
    if ($Reject) {
        if ($code -eq 0) { throw "Failed to reject: $Label" }
        return ''
    }
    if ($code -ne 0) { throw "Failed $Label (code $code): $($output -join ' ')" }
    return ($output -join [Environment]::NewLine)
}
function Make-Bundle {
    param([string]$Version, [string]$Source, [string]$Package)
    if (-not (Test-Path -LiteralPath $Package -PathType Leaf)) {
        Run-Cli "Build Rust tzpkg $Version" @(
            'build-package','--package-id',$PackageId,'--version',$Version,
            '--source',$Source,'--output',$Package,'--executable','beam-patcher.exe'
        ) | Out-Null
    }
    $Manifest = Join-Path $Work ("manifest-$Version.yaml")
    $Signature = Join-Path $Work ("manifest-$Version.p7s")
    $Bundle = Join-Path $Work ("beam-$Version.tzsetup")
    $uri = ([Uri]::new([IO.Path]::GetFullPath($Package))).AbsoluteUri
    Run-Cli "Draft $Version" @(
        'describe-package','--package-id',$PackageId,'--version',$Version,
        '--channel','beta','--package',$Package,'--uri',$uri,
        '--target',$Target,'--output',$Manifest
    ) | Out-Null
    $draft = [IO.File]::ReadAllText($Manifest)
    $changed = [regex]::Replace($draft, '(?m)^  supported: false$', '  supported: true')
    if ($changed -eq $draft) { throw 'Rollback manifest policy not found' }
    [IO.File]::WriteAllText($Manifest,$changed,$Utf8)
    $cms = [Security.Cryptography.Pkcs.SignedCms]::new(
        [Security.Cryptography.Pkcs.ContentInfo]::new([IO.File]::ReadAllBytes($Manifest)), $true)
    $signer = [Security.Cryptography.Pkcs.CmsSigner]::new($Certificate)
    $signer.IncludeOption = [Security.Cryptography.X509Certificates.X509IncludeOption]::EndCertOnly
    $signer.DigestAlgorithm = [Security.Cryptography.Oid]::new('2.16.840.1.101.3.4.2.1')
    $cms.ComputeSignature($signer)
    [IO.File]::WriteAllBytes($Signature,$cms.Encode())
    Run-Cli "Bundle $Version (test signer)" @(
        'build-setup-bundle','--package-id',$PackageId,
        '--manifest',$Manifest,'--signature',$Signature,
        '--trust-store',$Trust,'--package',$Package,'--output',$Bundle
    ) | Out-Null
    return [PSCustomObject]@{ Package=$Package; Manifest=$Manifest; Signature=$Signature; Bundle=$Bundle }
}
function Op {
    param([string]$Operation, [string]$Bundle)
    Run-Cli "Rust $Operation" @('install-bundle','--package-id',$PackageId,
        '--bundle',$Bundle,'--trust-store',$Trust,'--target',$Target,
        '--data-root',$State,'--operation',$Operation) | Out-Null
}
function Verify-Version {
    param([string]$Version)
    $report = Run-Cli "Verify $Version" @('verify','--package-id',$PackageId,
        '--target',$Target,'--data-root',$State)
    if ($report -notmatch ("version=" + [regex]::Escape($Version) + "\b")) {
        throw "Version mismatch: expected $Version"
    }
    return $report
}
function Find-TestSignTool {
    $kits = Join-Path ([Environment]::GetEnvironmentVariable('ProgramFiles(x86)')) 'Windows Kits/10/bin'
    if (-not (Test-Path -LiteralPath $kits -PathType Container)) {
        throw 'Windows SDK signing tools missing on hosted runner'
    }
    foreach ($version in (Get-ChildItem -LiteralPath $kits -Directory | Sort-Object Name -Descending)) {
        $exe = Join-Path $version.FullName 'x64/signtool.exe'
        if (Test-Path -LiteralPath $exe -PathType Leaf) { return $exe }
    }
    throw 'Windows SDK x64 signtool.exe not found'
}

function Sign-And-CheckTestExecutable {
    param([string]$Path, [string]$Label, [string]$SignToolPath)
    $before = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    & $SignToolPath sign /fd SHA256 /sha1 $Certificate.Thumbprint /s My $Path
    if ($LASTEXITCODE -ne 0) { throw "Ephemeral Authenticode signing failed for $Label" }
    $signed = Get-AuthenticodeSignature -LiteralPath $Path
    $status = [string]$signed.Status
    $rootOnly = [string]$signed.StatusMessage -match 'A certificate chain processed,\s*but terminated in a root certificate which is not trusted by the trust provider\.'
    if ($status -notin @('Valid','NotTrusted') -and
        -not ($status -eq 'UnknownError' -and $rootOnly)) {
        throw "Authenticode status unexpected for $Label - $status"
    }
    if (-not $signed.SignerCertificate) { throw "Missing signed certificate for $Label" }
    $actualPin = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($signed.SignerCertificate.RawData)).ToLowerInvariant()
    if ($actualPin -cne $pin) { throw "Ephemeral publisher pin mismatch for $Label" }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ceq $before) {
        throw "Authenticode signature did not alter test EXE: $Label"
    }
    Write-Host "TEST ONLY: Authenticode digest and signer pin verified for $Label"
}

function Assert-DistributionPair {
    param([string]$Bundle)
    $pairPath = Join-Path $Work 'rust-qa-pair'
    Run-Cli 'Build primary and private NSIS from single signed bundle' @(
        'build-distribution-pair','--package-id',$PackageId,'--stub',$GuiStub,
        '--bundle',$Bundle,'--trust-store',$Trust,'--output-dir',$pairPath,
        '--makensis',$Makensis
    ) | Out-Null
    if (-not (Test-Path -LiteralPath $pairPath -PathType Container)) {
        throw 'Rust distribution pair was not published atomically'
    }
    $primary = Join-Path $pairPath 'TurkuazSetup.exe'
    $privateBackup = Join-Path $pairPath 'TurkuazInstallerBackup.exe'
    foreach ($exe in @($primary,$privateBackup)) {
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf) -or
            (Get-Item -LiteralPath $exe).Length -lt 1024) {
            throw "Missing or empty test setup EXE: $exe"
        }
        $reader = [IO.File]::OpenRead($exe)
        try {
            if ($reader.ReadByte() -ne 77 -or $reader.ReadByte() -ne 90) {
                throw 'Rust pair member is not a Windows PE executable'
            }
        } finally { $reader.Dispose() }
    }
    if ((Get-FileHash -LiteralPath $primary -Algorithm SHA256).Hash -ceq
        (Get-FileHash -LiteralPath $privateBackup -Algorithm SHA256).Hash) {
        throw 'Primary and private NSIS executables unexpectedly identical'
    }
    $malformedTrust = Join-Path $Work 'wrong-trust.yaml'
    $badPin = 'f' * 64
    if ($badPin -ceq $pin) { $badPin = 'a' * 64 }
    [IO.File]::WriteAllText($malformedTrust,
        [IO.File]::ReadAllText($Trust).Replace($pin, $badPin), $Utf8)
    $rejectedPair = Join-Path $Work 'must-not-publish'
    Run-Cli -Label 'Reject wrong publisher pin before pair publication' -Reject -ArgsList @(
        'build-distribution-pair','--package-id',$PackageId,'--stub',$GuiStub,
        '--bundle',$Bundle,'--trust-store',$malformedTrust,
        '--output-dir',$rejectedPair,'--makensis',$Makensis
    ) | Out-Null
    if (Test-Path -LiteralPath $rejectedPair) {
        throw 'Invalid Rust pair left a public-looking output directory'
    }
    $signTool = Find-TestSignTool
    Sign-And-CheckTestExecutable -Path $primary -Label 'Turkuaz primary test setup' -SignToolPath $signTool
    Sign-And-CheckTestExecutable -Path $privateBackup -Label 'private NSIS fallback' -SignToolPath $signTool
    return [PSCustomObject]@{ Primary=$primary; Backup=$privateBackup }
}

try {
    New-Item -ItemType Directory -Force -Path $Work | Out-Null
    Add-Type -AssemblyName System.Security.Cryptography.Pkcs
    $Certificate = New-SelfSignedCertificate -Subject 'CN=TurkuazInstaller CI Smoke,O=TurkuazLabs,C=US' -CertStoreLocation 'Cert:\CurrentUser\My' -Type CodeSigningCert -KeyAlgorithm RSA -KeyLength 2048 -HashAlgorithm SHA256 -NotAfter (Get-Date).AddDays(2)
    $pin = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Certificate.RawData)).ToLowerInvariant()
    $dq = [char]34
    $subject = 'CN=TurkuazInstaller CI Smoke, O=TurkuazLabs, C=US'
    $trustContent = @('schema_version: 1','packages:',"  - id: $PackageId",
        "    publisher_subject: $dq$subject$dq","    certificate_sha256: $dq$pin$dq") -join [Environment]::NewLine
    [IO.File]::WriteAllText($Trust, $trustContent + [Environment]::NewLine, $Utf8)

    $first = Join-Path $env:RUNNER_TEMP 'beam-rust-candidate-output/beam-qa-candidate.tzpkg'
    $v1 = Make-Bundle '1.0.1' $Payload $first
    $tampered = Join-Path $Work 'altered.yaml'
    [IO.File]::WriteAllText($tampered,
        [IO.File]::ReadAllText($v1.Manifest) + [Environment]::NewLine + '# altered after CMS',
        $Utf8)
    Run-Cli -Label 'Reject CMS tamper' -Reject -ArgsList @(
        'build-setup-bundle','--package-id',$PackageId,'--manifest',$tampered,
        '--signature',$v1.Signature,'--trust-store',$Trust,'--package',$first,
        '--output',(Join-Path $Work 'never.tzsetup')) | Out-Null

    Op 'install' $v1.Bundle
    $null = Verify-Version '1.0.1'
    $sentinel = Join-Path $Target 'user-owned.txt'
    [IO.File]::WriteAllText($sentinel, 'preserve-me', $Utf8)
    $source2 = Join-Path $Work 'v1.0.2-payload'
    Copy-Item -LiteralPath $Payload -Destination $source2 -Recurse
    Add-Content -LiteralPath (Join-Path $source2 'README-QA.txt') -Value 'test-only upgrade 1.0.2'
    $v2 = Make-Bundle '1.0.2' $source2 (Join-Path $Work 'beam-1.0.2.tzpkg')
    Op 'update' $v2.Bundle
    $active = Verify-Version '1.0.2'
    $found = [regex]::Match($active, '(?m)\bdirectory=(.+)$')
    if (-not $found.Success) { throw 'Missing active version directory in verify output' }
    $readme = Join-Path $found.Groups[1].Value.Trim() 'README-QA.txt'
    if (-not (Test-Path -LiteralPath $readme -PathType Leaf)) { throw 'README missing from active Beam payload' }
    [IO.File]::WriteAllText($readme,'tampered', $Utf8)
    Run-Cli -Label 'Reject tampered managed file' -Reject -ArgsList @(
        'verify','--package-id',$PackageId,'--target',$Target,'--data-root',$State) | Out-Null
    Op 'repair' $v2.Bundle
    $null = Verify-Version '1.0.2'
    Op 'rollback' $v2.Bundle
    $null = Verify-Version '1.0.1'
    Run-Cli 'Uninstall test Beam package' @('uninstall','--package-id',$PackageId,
        '--target',$Target,'--data-root',$State,'--confirm-uninstall','YES') | Out-Null
    $listed = Run-Cli 'Check removed state' @('list','--data-root',$State)
    if ($listed -notmatch 'No installed packages\.') { throw 'Stale Beam installation state' }
    if (-not (Test-Path -LiteralPath $sentinel -PathType Leaf) -or
        [IO.File]::ReadAllText($sentinel) -cne 'preserve-me') { throw 'Unmanaged user file changed' }
    # NSIS fallback is compiled, PE-checked and test-signed, NEVER invoked.
    # Self-extractor tests only the primary CLI path in the QA target.
    $pair = Assert-DistributionPair -Bundle $v2.Bundle
    $primaryOutput = & $pair.Primary install-self --package-id $PackageId --trust-store $Trust --target $Target --data-root $State --operation install 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Primary Turkuaz setup test install failed: $($primaryOutput -join ' ')"
    }
    $null = Verify-Version '1.0.2'
    Run-Cli 'Uninstall primary test setup' @(
        'uninstall','--package-id',$PackageId,'--target',$Target,
        '--data-root',$State,'--confirm-uninstall','YES'
    ) | Out-Null
    if (-not (Test-Path -LiteralPath $sentinel -PathType Leaf) -or
        [IO.File]::ReadAllText($sentinel) -cne 'preserve-me') {
        throw 'Primary setup altered unmanaged user data'
    }
    Write-Host 'BEAM_RUST_EPHEMERAL_PRIMARY_NSIS_PAIR_PASS_NO_UPLOAD'
    Write-Host 'BEAM_RUST_TEST_SIGNED_LIFECYCLE_PASS_NOT_PRODUCTION'
} finally {
    if ($Certificate) {
        Remove-Item -LiteralPath ('Cert:\CurrentUser\My\' + $Certificate.Thumbprint) -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $Root) {
        Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue
    }
}
