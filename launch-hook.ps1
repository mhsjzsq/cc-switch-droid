param([switch]$NoMessageBox)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$mutex = $null
$acquired = $false
$helper = $null
$failure = $null

function Read-LaunchState([string]$Path, [string]$LaunchId, [int]$HelperId) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try {
        $status = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($status.launchId -eq $LaunchId -and $status.helperPid -eq $HelperId) {
            return $status
        }
    } catch {
        # Atomic status replacement can briefly overlap a reader on Windows.
    }
    return $null
}

try {
    $mutex = New-Object System.Threading.Mutex($false, 'Local\CCSwitchDroidHookLaunch')
    try { $acquired = $mutex.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $acquired = $true }
    if (-not $acquired) { throw '另一个启动入口正在处理，请稍候查看 CC Switch 窗口。' }

    $python = Join-Path $root 'python\pythonw.exe'
    $entry = Join-Path $root 'addon\hook_client.py'
    foreach ($file in @($python, $entry)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "缺少启动文件：$file。请保留完整的项目目录。"
        }
    }
    $configPath = Join-Path $root 'config.json'
    if (Test-Path -LiteralPath $configPath) {
        if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
            throw 'config.json 路径不是文件，请检查项目目录。'
        }
    } else {
        if ($NoMessageBox) {
            throw '缺少 config.json，请双击 Open-Hook.cmd 完成首次配置。'
        }
        . (Join-Path $root 'addon\first_run.ps1')
        if (-not (Show-FirstRunSetup -Root $root)) { exit 0 }
    }

    $launchId = [Guid]::NewGuid().ToString('N')
    $statusPath = Join-Path $root "data\launches\$launchId.json"
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $python
    $startInfo.Arguments = '-B "' + $entry + '" --launch-id ' + $launchId
    $startInfo.WorkingDirectory = $root
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $helper = [System.Diagnostics.Process]::Start($startInfo)

    # The helper enforces the configured timeout (at most 120 seconds).
    # This outer limit also covers early interpreter/import/status failures.
    $deadline = [DateTime]::UtcNow.AddSeconds(140)
    $attached = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        $status = Read-LaunchState $statusPath $launchId $helper.Id
        if ($null -ne $status) {
            if ($status.state -eq 'attached') { $attached = $true; break }
            if ($status.state -eq 'error') { throw ([string]$status.reason) }
            if ($status.state -in @('stopping', 'stopped')) {
                throw 'CC Switch 已退出，启动入口没有保持连接。'
            }
        }
        if ($helper.HasExited) {
            # Read once more so a final atomic error write is not missed.
            $status = Read-LaunchState $statusPath $launchId $helper.Id
            if ($null -ne $status -and $status.state -eq 'error') { throw ([string]$status.reason) }
            throw "Hook 启动助手已退出（退出码 $($helper.ExitCode)）。请查看 data\hook.log；若没有日志，请确认 python 目录完整且项目目录可写。"
        }
        Start-Sleep -Milliseconds 200
    }
    if (-not $attached) {
        throw '未收到 Hook 加载成功状态。请查看 data\hook.log；已有的原版窗口会保留，请完整退出后重试。'
    }
} catch {
    $failure = $_.Exception.Message
} finally {
    if ($null -ne $helper) { $helper.Dispose() }
    if ($acquired) { $mutex.ReleaseMutex() }
    if ($null -ne $mutex) { $mutex.Dispose() }
}

if ($failure) {
    if ($NoMessageBox) {
        [Console]::Error.WriteLine($failure)
    } else {
        try {
            Add-Type -AssemblyName System.Windows.Forms
            [void][System.Windows.Forms.MessageBox]::Show(
                $failure, 'CC Switch Droid Hook',
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Error
            )
        } catch {
            [Console]::Error.WriteLine($failure)
        }
    }
    exit 1
}
exit 0
