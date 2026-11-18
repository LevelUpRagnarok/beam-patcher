# Dosya Yolu: REPO_ROOT/tools/Test-BeamNativeClassicUi.ps1
# Amac: Windows uzerinde gercek Beam Tauri penceresini QA modunda smoke test etmek
# Modul - PowerShell / native UI QA
# Version: 1.0.0-candidate
# Aciklama: Gercek WebView2 penceresi kontrolu; oyun, patch, setup ve ag testi degildir
# Bagimli Oldugu Katman: beam-patcher/src/main.rs | installer/windows/config.qa.yml

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ExecutablePath,
    [Parameter(Mandatory = $true)][string]$ConfigPath,
    [Parameter(Mandatory = $true)][string]$EvidenceDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $EvidenceDirectory -Force | Out-Null

$report = [ordered]@{
    schema = 'beam-native-classic-gui-smoke.v1'
    status = 'NOT_RUN'
    source = 'real Windows Tauri/WebView2 process'
    qa_only = $false
    screenshot = 'NOT_ATTEMPTED'
    screenshot_file = $null
    process_window_title = $null
    window_width = $null
    window_height = $null
    no_game_or_patch_commands_invoked = $true
    failure = $null
}
$child = $null

try {
    $exe = (Resolve-Path -LiteralPath $ExecutablePath).Path
    $config = (Resolve-Path -LiteralPath $ConfigPath).Path
    $raw = Get-Content -LiteralPath $config -Raw -Encoding UTF8
    if ($raw -notmatch '(?m)^\s*qa_only:\s*true\s*$' -or
        $raw -notmatch '(?m)^\s*client_exe:\s*"NO_CLIENT_CONFIGURED\.exe"\s*$' -or
        $raw -notmatch '(?m)^\s*theme:\s*"ragnar-classic"\s*$' -or
        $raw -notmatch 'http://127\.0\.0\.1:9/disabled') {
        throw 'NATIVE_UI_QA_REQUIRES_ISOLATED_QA_ONLY_CONFIG'
    }
    $report.qa_only = $true
    $report.executable_sha256 = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
    $report.status = 'STARTING_NATIVE_WINDOW'

    $child = Start-Process -FilePath $exe -ArgumentList ('--config "' + $config + '"') -WorkingDirectory (Split-Path -Parent $exe) -PassThru
    if (-not $child) { throw 'NATIVE_UI_PROCESS_DID_NOT_START' }
    $handle = [IntPtr]::Zero
    $title = ''
    for ($try = 0; $try -lt 40; $try++) {
        Start-Sleep -Seconds 1
        $child.Refresh()
        if ($child.HasExited) {
            throw ('NATIVE_UI_EXITED_BEFORE_WINDOW: ' + $child.ExitCode)
        }
        $running = Get-Process -Id $child.Id -ErrorAction Stop
        $handle = $running.MainWindowHandle
        $title = $running.MainWindowTitle
        if ($handle -ne [IntPtr]::Zero -and $title -match 'Turkuaz Ragnarok') {
            break
        }
    }
    if ($handle -eq [IntPtr]::Zero -or $title -notmatch 'Turkuaz Ragnarok') {
        throw 'NATIVE_UI_MAIN_WINDOW_NOT_FOUND'
    }
    if ($title -notmatch '(TEST MODU|QA)') {
        throw 'NATIVE_UI_WINDOW_NOT_LABELED_QA'
    }
    $report.process_window_title = $title

    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public struct BeamQaRect { public int Left; public int Top; public int Right; public int Bottom; }
public static class BeamQaUser32 {
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out BeamQaRect r);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
}
'@
    $rect = [BeamQaRect]::new()
    if (-not [BeamQaUser32]::GetWindowRect($handle, [ref]$rect)) {
        throw 'NATIVE_UI_GET_WINDOW_RECT_FAILED'
    }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    $report.window_width = $width
    $report.window_height = $height
    if ($width -lt 820 -or $width -gt 1030 -or
        $height -lt 560 -or $height -gt 735) {
        throw 'NATIVE_UI_UNEXPECTED_900X620_WINDOW_BOUNDS'
    }
    $report.status = 'NATIVE_WINDOW_OPENED'

    try {
        [void][BeamQaUser32]::SetForegroundWindow($handle)
        Start-Sleep -Seconds 3
        Add-Type -AssemblyName System.Drawing
        $image = [System.Drawing.Bitmap]::new($width, $height)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($image)
            try {
                $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0,
                    [System.Drawing.Size]::new($width, $height))
            }
            finally { $graphics.Dispose() }
            $out = Join-Path $EvidenceDirectory 'beam-native-classic-window.png'
            $image.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
            $report.screenshot_file = 'beam-native-classic-window.png'
            $report.screenshot = 'CAPTURED_NOT_VISUALLY_APPROVED'
        }
        finally { $image.Dispose() }
    }
    catch {
        # Some hosted Windows runners do not expose a captureable interactive
        # desktop; a real native HWND still proves the app was launched.
        $report.screenshot = 'BLOCKED_BY_RUNNER_DESKTOP'
        $report.screenshot_failure = $_.Exception.Message
    }
    Write-Host 'BEAM_NATIVE_CLASSIC_WINDOW_OPENED_QA_ONLY'
}
catch {
    $report.status = 'FAILED'
    $report.failure = $_.Exception.Message
    Write-Error ('BEAM_NATIVE_CLASSIC_SMOKE_FAILED: ' + $report.failure)
}
finally {
    if ($child) {
        try {
            $child.Refresh()
            if (-not $child.HasExited) {
                Stop-Process -Id $child.Id -Force -ErrorAction Stop
            }
        } catch { Write-Warning ('QA child cleanup: ' + $_.Exception.Message) }
    }
    $destination = Join-Path $EvidenceDirectory 'native-window-report.json'
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $destination -Encoding UTF8
}

if ($report.status -ne 'NATIVE_WINDOW_OPENED') { exit 1 }
exit 0
