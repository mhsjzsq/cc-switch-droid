# First-run configuration UI. Loaded only when config.json does not exist.

function Resolve-SetupExecutable([string]$Value, [string]$Root) {
    $path = $Value.Trim().Trim('"')
    if ([string]::IsNullOrWhiteSpace($path)) {
        throw '请选择 CC Switch 程序目录。'
    }
    $path = [Environment]::ExpandEnvironmentVariables($path)
    if ($path -eq '~' -or $path.StartsWith('~\') -or $path.StartsWith('~/')) {
        $userDirectory = [Environment]::GetFolderPath('UserProfile')
        $path = if ($path.Length -eq 1) { $userDirectory } else { Join-Path $userDirectory $path.Substring(2) }
    }
    if (-not [IO.Path]::IsPathRooted($path)) { $path = Join-Path $Root $path }
    if (Test-Path -LiteralPath $path -PathType Container) { $path = Join-Path $path 'cc-switch.exe' }
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
        [IO.Path]::GetFileName($path) -ine 'cc-switch.exe') {
        throw '没有找到 cc-switch.exe。请选择包含它的文件夹，或填写该文件的完整路径。'
    }
    return (Get-Item -LiteralPath $path -ErrorAction Stop).FullName
}

function Save-FirstRunConfig([string]$Root, [string]$Executable, [string]$ApiKey) {
    $destination = Join-Path $Root 'config.json'
    if (Test-Path -LiteralPath $destination) {
        throw 'config.json 已存在，未覆盖。请关闭此窗口并重新运行 Open-Hook.cmd。'
    }
    try {
        $template = Get-Content -LiteralPath (Join-Path $Root 'config.example.json') -Raw -Encoding UTF8 |
            ConvertFrom-Json -ErrorAction Stop
        if ($template -isnot [pscustomobject] -or
            $null -eq $template.PSObject.Properties['ccSwitchExecutable'] -or
            $null -eq $template.PSObject.Properties['factoryApiKey']) {
            throw 'Invalid configuration template'
        }
        $template.ccSwitchExecutable = $Executable
        $template.factoryApiKey = $ApiKey
        $json = ConvertTo-Json -InputObject $template -Depth 10
    } catch {
        throw '无法读取配置模板，请确认项目中的 config.example.json 完整且格式正确。'
    }

    # Move a fully written file in the same directory; never overwrite a config
    # created by another process while the dialog was open.
    $temporary = Join-Path $Root ('.config-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $bytes = [Text.UTF8Encoding]::new($false).GetBytes($json + [Environment]::NewLine)
        $stream = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try {
            $stream.Write($bytes, 0, $bytes.Length)
            $stream.Flush($true)
        } finally {
            $stream.Dispose()
        }
        [IO.File]::Move($temporary, $destination)
    } catch {
        if (Test-Path -LiteralPath $destination) {
            throw 'config.json 已存在，未覆盖。请关闭此窗口并重新运行 Open-Hook.cmd。'
        }
        throw '无法保存 config.json，请确认项目目录可写后重试。'
    } finally {
        if ([IO.File]::Exists($temporary)) {
            try { [IO.File]::Delete($temporary) } catch { }
        }
    }
}

function New-SetupLabel([string]$Text) {
    $label = [System.Windows.Forms.Label]::new()
    $label.Text = $Text
    $label.AutoSize = $true
    $label.MaximumSize = [System.Drawing.Size]::new(570, 0)
    $label.Margin = [System.Windows.Forms.Padding]::new(0, 0, 0, 8)
    return $label
}

function Show-FirstRunSetup([string]$Root) {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    [System.Windows.Forms.Application]::EnableVisualStyles()

    $form = [System.Windows.Forms.Form]::new()
    $form.Text = 'CC Switch Droid Hook · 首次配置'
    $form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
    $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::Font
    $form.AutoSize = $true
    $form.AutoSizeMode = [System.Windows.Forms.AutoSizeMode]::GrowAndShrink
    $form.ClientSize = [System.Drawing.Size]::new(640, 400)
    $form.MinimumSize = [System.Drawing.Size]::new(640, 0)
    $form.BackColor = [System.Drawing.SystemColors]::Window

    try {
        $layout = [System.Windows.Forms.TableLayoutPanel]::new()
        $layout.Dock = [System.Windows.Forms.DockStyle]::Fill
        $layout.AutoSize = $true
        $layout.ColumnCount = 1
        $layout.Padding = [System.Windows.Forms.Padding]::new(24)
        [void]$layout.ColumnStyles.Add([System.Windows.Forms.ColumnStyle]::new([System.Windows.Forms.SizeType]::Percent, 100))
        $form.Controls.Add($layout)

        $layout.Controls.Add((New-SetupLabel '首次使用，请填写以下两项。保存后将自动启动 CC Switch。'))
        $layout.Controls.Add((New-SetupLabel 'CC Switch 程序目录'))

        $pathRow = [System.Windows.Forms.TableLayoutPanel]::new()
        $pathRow.Dock = [System.Windows.Forms.DockStyle]::Fill
        $pathRow.AutoSize = $true
        $pathRow.ColumnCount = 2
        $pathRow.Margin = [System.Windows.Forms.Padding]::new(0, 0, 0, 8)
        [void]$pathRow.ColumnStyles.Add([System.Windows.Forms.ColumnStyle]::new([System.Windows.Forms.SizeType]::Percent, 100))
        [void]$pathRow.ColumnStyles.Add([System.Windows.Forms.ColumnStyle]::new([System.Windows.Forms.SizeType]::AutoSize))
        $pathBox = [System.Windows.Forms.TextBox]::new()
        $pathBox.Dock = [System.Windows.Forms.DockStyle]::Fill
        $pathBox.Margin = [System.Windows.Forms.Padding]::new(0, 4, 10, 0)
        $pathRow.Controls.Add($pathBox, 0, 0)
        $browseButton = [System.Windows.Forms.Button]::new()
        $browseButton.Text = '选择文件夹…'
        $browseButton.AutoSize = $true
        $browseButton.Margin = [System.Windows.Forms.Padding]::new(0)
        $pathRow.Controls.Add($browseButton, 1, 0)
        $layout.Controls.Add($pathRow)
        $layout.Controls.Add((New-SetupLabel '选择包含 cc-switch.exe 的文件夹，也可以粘贴完整的 EXE 路径。'))

        $layout.Controls.Add((New-SetupLabel 'Droid / Factory API Key'))
        $keyBox = [System.Windows.Forms.TextBox]::new()
        $keyBox.Dock = [System.Windows.Forms.DockStyle]::Fill
        $keyBox.UseSystemPasswordChar = $true
        $keyBox.Margin = [System.Windows.Forms.Padding]::new(0, 0, 0, 8)
        $layout.Controls.Add($keyBox)
        $showKey = [System.Windows.Forms.CheckBox]::new()
        $showKey.Text = '显示 API Key'
        $showKey.AutoSize = $true
        $showKey.Margin = [System.Windows.Forms.Padding]::new(0, 0, 0, 8)
        $layout.Controls.Add($showKey)
        $layout.Controls.Add((New-SetupLabel '请填写 Factory 账户的 API Key，用于读取套餐额度。'))

        $errorLabel = New-SetupLabel ''
        $errorLabel.ForeColor = [System.Drawing.Color]::Firebrick
        $errorLabel.MinimumSize = [System.Drawing.Size]::new(0, 24)
        $layout.Controls.Add($errorLabel)
        $buttons = [System.Windows.Forms.FlowLayoutPanel]::new()
        $buttons.Dock = [System.Windows.Forms.DockStyle]::Fill
        $buttons.AutoSize = $true
        $buttons.FlowDirection = [System.Windows.Forms.FlowDirection]::RightToLeft
        $buttons.Margin = [System.Windows.Forms.Padding]::new(0, 8, 0, 0)
        $saveButton = [System.Windows.Forms.Button]::new()
        $saveButton.Text = '保存并启动'
        $saveButton.AutoSize = $true
        $cancelButton = [System.Windows.Forms.Button]::new()
        $cancelButton.Text = '取消'
        $cancelButton.AutoSize = $true
        $cancelButton.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
        $buttons.Controls.Add($saveButton)
        $buttons.Controls.Add($cancelButton)
        $layout.Controls.Add($buttons)
        $form.AcceptButton = $saveButton
        $form.CancelButton = $cancelButton

        $browseButton.Add_Click({
            $picker = [System.Windows.Forms.FolderBrowserDialog]::new()
            try {
                $picker.Description = '请选择包含 cc-switch.exe 的文件夹'
                $picker.ShowNewFolderButton = $false
                if ($picker.ShowDialog($form) -eq [System.Windows.Forms.DialogResult]::OK) {
                    $pathBox.Text = $picker.SelectedPath
                    $errorLabel.Text = ''
                }
            } catch {
                $errorLabel.Text = '无法打开文件夹选择窗口，请直接粘贴 CC Switch 目录。'
            } finally {
                $picker.Dispose()
            }
        })
        $showKey.Add_CheckedChanged({ $keyBox.UseSystemPasswordChar = -not $showKey.Checked })
        $saveButton.Add_Click({
            $saveButton.Enabled = $false
            $errorLabel.Text = ''
            try {
                $executable = Resolve-SetupExecutable -Value $pathBox.Text -Root $Root
                $apiKey = $keyBox.Text.Trim()
                if ([string]::IsNullOrWhiteSpace($apiKey)) {
                    $keyBox.Focus() | Out-Null
                    throw '请输入 Droid / Factory API Key。'
                }
                if ($apiKey -match '[\s\p{Cc}]') {
                    throw 'API Key 中不能包含空格、换行或控制字符，请重新粘贴。'
                }
                Save-FirstRunConfig -Root $Root -Executable $executable -ApiKey $apiKey
                $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
                $form.Close()
            } catch {
                $errorLabel.Text = $_.Exception.Message
            } finally {
                $apiKey = $null
                $saveButton.Enabled = $true
            }
        })
        $form.Add_Shown({ $form.Activate(); $pathBox.Focus() | Out-Null })
        return $form.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK
    } finally {
        $form.Dispose()
    }
}
