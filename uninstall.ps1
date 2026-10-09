$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$mainPy = Join-Path $root 'addon\main.py'
$image = 'cc-switch.exe'
$policyKey = 'Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments'
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'CC Switch Droid Addon.lnk'

Write-Host '== 停止助手'
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains($mainPy) } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host "已停止 PID $($_.ProcessId)" }

Write-Host '== 删除开机启动项'
if (Test-Path $shortcutPath) { Remove-Item $shortcutPath; Write-Host '已删除。' } else { Write-Host '不存在。' }

Write-Host '== WebView2 调试端口策略'
$hasPolicy = $false
foreach ($hive in 'HKLM:', 'HKCU:') {
    if ((Get-ItemProperty -Path "$hive\$policyKey" -Name $image -ErrorAction SilentlyContinue).$image) { $hasPolicy = $true }
}
if ($hasPolicy) {
    $ans = Read-Host '删除 cc-switch.exe 的调试端口策略吗？需要一次管理员授权 (Y/n)'
    if ($ans -notmatch '^[nN]') {
        $cmd = "foreach (`$h in 'HKLM:','HKCU:') { Remove-ItemProperty -Path `"`$h\$policyKey`" -Name '$image' -ErrorAction SilentlyContinue }"
        try { Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $cmd; Write-Host '已删除。' }
        catch { Write-Host '未授权，策略保留。' -ForegroundColor Yellow }
    }
} else { Write-Host '不存在。' }

Write-Host '== 已导入 CC Switch 的 Droid 用量记录'
$ans = Read-Host '要从 CC Switch 数据库里删除这些记录吗？(y/N)'
if ($ans -match '^[yY]') {
    & (Join-Path $root 'python\python.exe') (Join-Path $root 'addon\remove_rows.py')
    Remove-Item (Join-Path $root 'data\sync_state.json') -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host '卸载完成。重启 CC Switch 后 Droid 入口会消失；现在可以删除整个文件夹。' -ForegroundColor Green
Read-Host '按回车退出'
