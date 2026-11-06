# Dosya Yolu: REPO_ROOT/tools/Test-BeamRustProtectedPrimary.ps1
# Amac: Gercek imzali Rust TurkuazSetup'u sadece hosted Windows ephemeral alanda kurup dogrulamak
# Modul - PowerShell / Protected installer native smoke
# Version: 1.0.0-candidate
# Aciklama: Native GUI-process bekleme, install/verify/uninstall ve kullanici dosyasi korunumu
# Bagimli Oldugu Katman: tools/Confirm-TurkuazTrust.ps1 | TurkuazInstaller/rust/CLI.md
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SetupPath,
    [Parameter(Mandatory)][string]$CliPath,
    [Parameter(Mandatory)][string]$TrustPath,
    [Parameter(Mandatory)][string]$BeamExePath,
    [string]$PackageId = 'levelupgt.beampatcher.qa',
    [string]$Version = '1.0.1'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or
    $env:BEAM_RUNNER_KIND -ne 'github-hosted' -or
    [string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
    throw 'Rust protected install smoke runs on disposable GitHub-hosted Windows only'
}
$Setup = (Resolve-Path -LiteralPath $SetupPath -ErrorAction Stop).ProviderPath
$Cli = (Resolve-Path -LiteralPath $CliPath -ErrorAction Stop).ProviderPath
$Trust = (Resolve-Path -LiteralPath $TrustPath -ErrorAction Stop).ProviderPath
$Beam = (Resolve-Path -LiteralPath $BeamExePath -ErrorAction Stop).ProviderPath
$Work = Join-Path $env:RUNNER_TEMP ('beam-rust-protected-' + [Guid]::NewGuid().ToString('N'))
$Target = Join-Path $Work 'installed'
$Data = Join-Path $Work 'state'
$TimeoutMilliseconds = 120000
function Run-And-Wait {
    param([string]$Executable, [string[]]$Arguments, [string]$Label)
    $start = [Diagnostics.ProcessStartInfo]::new($Executable)
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($argument in $Arguments) {
        [void]$start.ArgumentList.Add([string]$argument)
    }
    $proc = [Diagnostics.Process]::new()
    $proc.StartInfo = $start
    try {
        if (-not $proc.Start()) { throw "Cannot start: $Label" }
        $stdout = $proc.StandardOutput.ReadToEndAsync()
        $stderr = $proc.StandardError.ReadToEndAsync()
        if (-not $proc.WaitForExit($TimeoutMilliseconds)) {
            $proc.Kill($true)
            $proc.WaitForExit()
            throw "Native process deadline exceeded: $Label"
        }
        $nativeCode = $proc.ExitCode
        $output = $stdout.GetAwaiter().GetResult() + $stderr.GetAwaiter().GetResult()
        if ($nativeCode -ne 0) {
            $preview = if ($output.Length -gt 1500) { $output.Substring(0,1500) } else { $output }
            throw "Native Rust $Label failed with exit $nativeCode : $preview"
        }
        return $output
    } finally {
        $proc.Dispose()
    }
}
try {
    New-Item -ItemType Directory -Path $Work -Force | Out-Null
    # The test intentionally creates ONE user-owned file; the installer
    # must remove managed packages without erasing this unrelated data.
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
    $sentinel = Join-Path $Target 'user-owned-preserve.txt'
    [IO.File]::WriteAllText($sentinel,'preserve-user-owned', [Text.UTF8Encoding]::new($false))
    $null = Run-And-Wait $Setup @(
        'install-self','--package-id',$PackageId,'--trust-store',$Trust,
        '--target',$Target,'--data-root',$Data,'--operation','install'
    ) 'signed TurkuazSetup install-self'
    $result = Run-And-Wait $Cli @(
        'verify','--package-id',$PackageId,'--target',$Target,'--data-root',$Data
    ) 'Rust installed-state verify'
    if ($result -notmatch ('version=' + [regex]::Escape($Version) + '\b')) {
        throw 'Protected Rust primary installed unexpected package version'
    }
    $m = [regex]::Match($result, '(?m)\bdirectory=(.+)$')
    if (-not $m.Success) { throw 'Protected Rust primary verify did not report active directory' }
    $installedExe = Join-Path $m.Groups[1].Value.Trim() 'beam-patcher.exe'
    if (-not (Test-Path -LiteralPath $installedExe -PathType Leaf)) {
        throw 'Protected Rust active Beam executable missing'
    }
    $expected = (Get-FileHash -LiteralPath $Beam -Algorithm SHA256).Hash
    $actual = (Get-FileHash -LiteralPath $installedExe -Algorithm SHA256).Hash
    if ($expected -cne $actual) { throw 'Protected Rust primary installed mismatching Beam EXE bytes' }
    $null = Run-And-Wait $Cli @(
        'uninstall','--package-id',$PackageId,'--target',$Target,
        '--data-root',$Data,'--confirm-uninstall','YES'
    ) 'Rust uninstall'
    $listed = Run-And-Wait $Cli @('list','--data-root',$Data) 'Rust list after uninstall'
    if ($listed -notmatch 'No installed packages\.') {
        throw 'Protected Rust primary retained installed state after uninstall'
    }
    if (-not (Test-Path -LiteralPath $sentinel -PathType Leaf) -or
        [IO.File]::ReadAllText($sentinel) -cne 'preserve-user-owned') {
        throw 'Protected Rust primary altered unmanaged user data'
    }
    Write-Host 'BEAM_RUST_PROTECTED_NATIVE_INSTALL_UNINSTALL_PASS_NOT_GUI_ACCEPTANCE'
} finally {
    if (Test-Path -LiteralPath $Work) {
        Remove-Item -LiteralPath $Work -Recurse -Force -ErrorAction SilentlyContinue
    }
}
