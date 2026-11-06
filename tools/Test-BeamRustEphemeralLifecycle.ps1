# Dosya Yolu: REPO_ROOT/tools/Test-BeamRustEphemeralLifecycle.ps1
# Amac: Beam QA Rust lifecycle ve tek Turkuaz Windows primary setup testi
# Modul - PowerShell Integration QA
# Version: 1.3.0-candidate
# Aciklama: Gecici CI sertifikasi, gercek Beam EXE, signed bundle; production imzasi degil
# Bagimli Oldugu Katman: .github/workflows/rust-installer-beam-compat.yml | TurkuazInstaller/rust/CLI.md
[CmdletBinding()]
param([Parameter(Mandatory)][string]$InstallerPath,
      [Parameter(Mandatory)][string]$PayloadDirectory,
      [Parameter(Mandatory)][string]$GuiStubPath)
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
    # Native stdout is diagnostic, not the primary EXE return value.
    # Do not leak signtool success text into Assert-TurkuazPrimary output.
    & $SignToolPath sign /fd SHA256 /sha1 $Certificate.Thumbprint /s My $Path | Out-Null
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

# TURKUAZ-ONLY-001: produce just the primary EXE from the same signed bundle.
function Assert-TurkuazPrimary {
    param([string]$Bundle, [string]$Manifest, [string]$Signature, [string]$Package)
    $primary = Join-Path $Work 'TurkuazSetup.exe'
    Run-Cli 'Build single Turkuaz primary self-extracting setup' @(
        'build-self-extracting-setup','--stub',$GuiStub,
        '--bundle',$Bundle,'--output',$primary
    ) | Out-Null
    if (-not (Test-Path -LiteralPath $primary -PathType Leaf) -or
        (Get-Item -LiteralPath $primary).Length -lt 1024) {
        throw 'Single Turkuaz primary is missing or empty'
    }
    $reader = [IO.File]::OpenRead($primary)
    try {
        if ($reader.ReadByte() -ne 77 -or $reader.ReadByte() -ne 90) {
            throw 'Turkuaz primary is not a Windows PE'
        }
    } finally { $reader.Dispose() }

    $wrongTrust = Join-Path $Work 'wrong-publisher-trust.yaml'
    $invalidPin = 'f' * 64
    if ($invalidPin -ceq $pin) { $invalidPin = 'a' * 64 }
    [IO.File]::WriteAllText($wrongTrust,
        [IO.File]::ReadAllText($Trust).Replace($pin,$invalidPin), $Utf8)
    $invalid = Join-Path $Work 'must-not-exist.tzsetup'
    Run-Cli -Label 'Reject mismatched Turkuaz publisher pin' -Reject -ArgsList @(
        'build-setup-bundle','--package-id',$PackageId,'--manifest',$Manifest,
        '--signature',$Signature,'--trust-store',$wrongTrust,
        '--package',$Package,'--output',$invalid
    ) | Out-Null
    if (Test-Path -LiteralPath $invalid) {
        throw 'Mismatched publisher still generated a candidate bundle'
    }
    $tool = Find-TestSignTool
    Sign-And-CheckTestExecutable -Path $primary -Label 'Turkuaz single primary test EXE' -SignToolPath $tool
    return $primary
}

# @dev-id BEAM-RUST-GUI-PROC-001
# @purpose Wait for the actual completion of the Windows GUI-subsystem setup.
# @reason A PowerShell direct invocation can return before a GUI EXE exits;
#         LASTEXITCODE may then be stale even though install-self is still running.
# @contract Uses argv-safe ProcessStartInfo, drains stdout/stderr asynchronously,
#           enforces a bounded timeout, inspects the REAL native process exit code,
#           then permits the managed-install state verification to run.
function Invoke-GuiPrimaryAndWait {
    param([Parameter(Mandatory)][string]$Path,
          [Parameter(Mandatory)][string[]]$Arguments,
          [int]$TimeoutMilliseconds = 120000)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'Turkuaz primary GUI executable is missing'
    }
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new($Path)
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    foreach ($argument in $Arguments) {
        $null = $startInfo.ArgumentList.Add([string]$argument)
    }
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) {
            throw 'Turkuaz GUI primary could not start'
        }
        # Drain pipes in parallel to avoid deadlocking a verbose child process.
        $standardOutput = $process.StandardOutput.ReadToEndAsync()
        $standardError = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutMilliseconds)) {
            $process.Kill($true)
            $process.WaitForExit()
            throw 'Turkuaz GUI install-self exceeded the bounded CI timeout'
        }
        $outText = $standardOutput.GetAwaiter().GetResult()
        $errText = $standardError.GetAwaiter().GetResult()
        $nativeCode = $process.ExitCode
        if ($nativeCode -ne 0) {
            $details = (($outText + ' ' + $errText).Trim())
            if ($details.Length -gt 2048) {
                $details = $details.Substring(0,2048) + ' [truncated]'
            }
            throw "Turkuaz GUI install-self exited $nativeCode : $details"
        }
        Write-Host 'BEAM_RUST_TURKUAZ_GUI_SUBSYSTEM_WAIT_EXIT_0'
    } finally {
        $process.Dispose()
    }
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
    # Exercise the primary self-extractor CLI, not a GUI wizard or client.
    $primary = Assert-TurkuazPrimary -Bundle $v2.Bundle -Manifest $v2.Manifest -Signature $v2.Signature -Package $v2.Package
    if ($primary -isnot [string] -or -not (Test-Path -LiteralPath $primary -PathType Leaf)) {
        throw 'Turkuaz primary builder returned unexpected stdout instead of one EXE path'
    }
    Invoke-GuiPrimaryAndWait -Path $primary -Arguments @(
        'install-self','--package-id',$PackageId,
        '--trust-store',$Trust,'--target',$Target,
        '--data-root',$State,'--operation','install'
    ) -TimeoutMilliseconds 120000
    $null = Verify-Version '1.0.2'
    Run-Cli 'Uninstall primary test setup' @(
        'uninstall','--package-id',$PackageId,'--target',$Target,
        '--data-root',$State,'--confirm-uninstall','YES'
    ) | Out-Null
    if (-not (Test-Path -LiteralPath $sentinel -PathType Leaf) -or
        [IO.File]::ReadAllText($sentinel) -cne 'preserve-me') {
        throw 'Single Turkuaz setup altered unmanaged user data'
    }
    Write-Host 'BEAM_RUST_EPHEMERAL_TURKUAZ_PRIMARY_PASS_NO_UPLOAD'
    Write-Host 'BEAM_RUST_TEST_SIGNED_LIFECYCLE_PASS_NOT_PRODUCTION'
} finally {
    if ($Certificate) {
        Remove-Item -LiteralPath ('Cert:\CurrentUser\My\' + $Certificate.Thumbprint) -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $Root) {
        Remove-Item -LiteralPath $Root -Recurse -Force -ErrorAction SilentlyContinue
    }
}
