$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pythonw = Join-Path $root 'python\pythonw.exe'
$mainPy = Join-Path $root 'addon\main.py'
$configPath = Join-Path $root 'config.json'
$image = 'cc-switch.exe'
$policyKey = 'Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments'
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'CC Switch Droid Addon.lnk'

function Step($msg) { Write-Host ''; Write-Host "== $msg" -ForegroundColor Cyan }

if (-not (Test-Path $pythonw) -or -not (Test-Path $mainPy)) {
    Write-Host '文件不完整：缺少 python\pythonw.exe 或 addon\main.py' -ForegroundColor Red
    Read-Host '按回车退出'; exit 1
}

Step '停止正在运行的助手'
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($mainPy) } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host "已停止 PID $($_.ProcessId)" }
if (Get-ScheduledTask -TaskName 'CC-Switch Droid Sync' -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName 'CC-Switch Droid Sync' -Confirm:$false
    Write-Host '已删除旧的计划任务 CC-Switch Droid Sync（功能已并入助手）'
}

Step 'Factory API key'
$config = $null
if (Test-Path $configPath) {
    try { $config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $config = $null }
}
if (-not $config) {
    $config = [pscustomobject]@{ factoryApiKey = ''; debugPort = 9333; quotaRefreshSeconds = 60
        autoRestartWithoutPolicy = $true; ccSwitchDbPath = ''; droidSessionsDir = '' }
}
foreach ($name in 'factoryApiKey', 'debugPort') {
    if (-not ($config.PSObject.Properties.Name -contains $name)) {
        $default = if ($name -eq 'debugPort') { 9333 } else { '' }
        $config | Add-Member -NotePropertyName $name -NotePropertyValue $default
    }
}
if ([string]::IsNullOrWhiteSpace($config.factoryApiKey)) {
    Write-Host '用于显示 Droid 额度。可在 https://app.factory.ai/settings/api-keys 创建。'
    $secure = Read-Host '粘贴 Factory API key（直接回车跳过，之后可在 config.json 填写）' -AsSecureString
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    if (-not [string]::IsNullOrWhiteSpace($plain)) { $config.factoryApiKey = $plain.Trim(); Write-Host '已保存。' }
    else { Write-Host '已跳过。' }
} else {
    Write-Host 'config.json 里已有 API key，保留不变。'
}
$json = $config | ConvertTo-Json
[IO.File]::WriteAllText($configPath, $json, (New-Object Text.UTF8Encoding $false))
$port = [int]$config.debugPort
$portArg = "--remote-debugging-port=$port"

Step 'WebView2 调试端口策略'
function Get-PolicyValue {
    foreach ($hive in 'HKLM:', 'HKCU:') {
        $v = (Get-ItemProperty -Path "$hive\$policyKey" -Name $image -ErrorAction SilentlyContinue).$image
        if ($v) { return [string]$v }
    }
    return ''
}
$policy = Get-PolicyValue
if ($policy -like "*$portArg*") {
    Write-Host '策略已存在，CC Switch 每次启动都会开启调试端口。'
} else {
    Write-Host '接下来会弹出一次管理员授权（UAC），只为 cc-switch.exe 写入一条 WebView2 启动参数。'
    Write-Host '点「否」也能用：助手会在 CC Switch 刚启动时自动带参数重启它一次。'
    $newValue = ("$policy $portArg").Trim()
    $cmd = "New-Item -Path 'HKLM:\$policyKey' -Force | Out-Null; Set-ItemProperty -Path 'HKLM:\$policyKey' -Name '$image' -Value '$newValue'"
    try {
        Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $cmd
    } catch {
        Write-Host '未授权，改用自动重启方式。' -ForegroundColor Yellow
    }
    if ((Get-PolicyValue) -like "*$portArg*") { Write-Host '策略写入成功。' -ForegroundColor Green }
}

Step '开机自启'
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($shortcutPath)
$lnk.TargetPath = $pythonw
$lnk.Arguments = "`"$mainPy`""
$lnk.WorkingDirectory = $root
$lnk.Description = 'CC Switch Droid 用量与额度助手'
$lnk.Save()
Write-Host "已创建启动项：$shortcutPath"

Step '启动助手'
Start-Process -FilePath $pythonw -ArgumentList "`"$mainPy`"" -WorkingDirectory $root
Write-Host '助手已在后台运行（没有窗口）。日志：data\addon.log'

$procs = Get-CimInstance Win32_Process -Filter "Name='$image'"
if ($procs) {
    $ok = $false
    try { $ok = [bool](Invoke-RestMethod "http://127.0.0.1:$port/json" -TimeoutSec 2 | Where-Object { $_.url -like '*tauri.localhost*' }) } catch {}
    if (-not $ok) {
        Step 'CC Switch 需要重启一次'
        $ans = Read-Host 'CC Switch 正在运行，但没有开启调试端口。现在重启它吗？(Y/n)'
        if ($ans -notmatch '^[nN]') {
            $proc = $procs | Select-Object -First 1
            $exe = $proc.ExecutablePath
            Stop-Process -Id $proc.ProcessId -Force
            Start-Sleep -Seconds 3
            $env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = $portArg
            Start-Process -FilePath $exe -WorkingDirectory (Split-Path $exe)
            Write-Host '已重启 CC Switch。几秒后左侧会出现 Droid。'
        } else {
            Write-Host '下次启动 CC Switch 时生效。'
        }
    } else {
        Write-Host '几秒后 CC Switch 左侧会出现 Droid。'
    }
}

Write-Host ''
Write-Host '安装完成。' -ForegroundColor Green
Read-Host '按回车退出'
