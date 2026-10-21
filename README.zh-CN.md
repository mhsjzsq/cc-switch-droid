# CC Switch Droid Hook

[English](README.md) | **简体中文**

为 [CC Switch](https://github.com/farion1231/cc-switch) 添加 Droid 页面、Factory 额度查询和本地用量同步的 Windows 扩展。

通过 `Open-Hook.cmd` 启动原版 CC Switch，并为这次运行加载 Hook。项目自带 Python 运行环境，无需安装系统 Python，也不依赖旧版 Addon 目录。

**当前版本：2.2.4** · [修改记录](CHANGELOG.md) · [配置模板](config.example.json) · [许可证](LICENSE)

## 功能

- **Droid 页面**：查看 Factory 套餐额度、本地今日用量和统计说明。
- **用量同步**：将 Droid 本地会话的新增 Token 用量写入 CC Switch 数据库。
- **速度与首字时间**：从 Droid 本地请求日志补全能够可靠匹配的记录。
- **原生统计筛选**：在用量统计页直接切换 Droid 与“全部”。
- **首次配置向导**：选择 CC Switch 目录、填写 Factory API Key，保存后继续启动。
- **设置备份**：启动前保存原版设备设置副本；发现 JSON 损坏时停止启动。

本项目以 CC Switch 4.0.12 为适配参考。适配依赖原版界面和数据库结构，其他版本可能需要调整。近期改动的验证范围见 [修改记录](CHANGELOG.md)。

## 快速开始

### 运行条件

- Windows，能够运行 Windows PowerShell 和 CC Switch。
- 已安装或解压原版 CC Switch。
- 保留项目的完整目录，尤其是 `python/`、`addon/` 和 `config.example.json`。
- Factory API Key，用于账户额度查询。
- 如需同步本地用量和速度，应已有 Droid 生成的会话及运行日志。

### 首次启动

1. 从托盘完整退出已运行的 CC Switch。只关闭窗口可能仍保留托盘进程。
2. 双击项目目录中的 `Open-Hook.cmd`。
3. 没有 `config.json` 时，在首次配置窗口中：
   - 选择包含 `cc-switch.exe` 的文件夹，或粘贴该 EXE 的完整路径。
   - 填写 Droid / Factory API Key。输入默认隐藏，可勾选“显示 API Key”。
4. 点击 **保存并启动**。程序生成配置后继续启动原版并加载 Hook，无需再次打开入口。
5. 在左侧打开 **Droid** 页面，或在 **用量统计** 页面使用 Droid 筛选。

首次配置窗口目前使用简体中文。API Key 可在 [Factory API Keys](https://app.factory.ai/settings/api-keys) 页面创建。配置窗口检查程序路径和 Key 输入格式；Key 的有效性由启动后的额度查询反馈。

取消或关闭配置窗口不会生成配置，也不会启动程序。已有配置时直接使用，不会重复弹出向导或覆盖原文件。

### 后续使用与更新

每次需要 Droid 功能时，通过 `Open-Hook.cmd` 启动。直接打开原版程序不会自动加载本项目。

更新项目文件后，从托盘完整退出 CC Switch，再通过入口启动。已运行的助手不会自动加载修改后的代码。

## 配置

个人配置保存在项目目录的 `config.json`，默认项见 [config.example.json](config.example.json)。

| 字段 | 说明 |
| --- | --- |
| `ccSwitchExecutable` | 原版 `cc-switch.exe` 路径。已有配置中留空时，尝试 PATH 和当前用户的常见安装目录。 |
| `ccSwitchArguments` | 原版启动参数，默认为空数组。不能覆盖入口管理的调试端口或用户资料目录参数。 |
| `factoryApiKey` | Factory API Key。首次向导要求填写；已有配置中留空时，依次读取环境变量 `FACTORY_API_KEY` 和 `~/.factory/.env`。 |
| `quotaRefreshSeconds` | 额度查询间隔，默认 60 秒，允许 15–86400 秒。失败后延长重试间隔并标记旧数据。 |
| `ccSwitchDbPath` | 原版数据库路径。默认 `~/.cc-switch/cc-switch.db`；目标不存在时不会创建空数据库。 |
| `droidSessionsDir` | Droid 会话目录，默认 `~/.factory/sessions`。 |
| `droidLogsDir` | Droid 请求日志目录。默认使用会话目录旁的 `logs`，通常为 `~/.factory/logs`。 |
| `startupTimeoutSeconds` | 初次连接等待上限，默认 45 秒，允许 10–120 秒。 |

`~` 表示当前用户目录，相对路径以项目目录为基准，路径也支持环境变量。向导会自动处理 JSON 转义；手动编辑配置时可以使用正斜杠，或将反斜杠写成 `\\`。

Factory Key、额度间隔和数据路径约每 10 秒重新读取一次。原版路径、启动参数和启动超时在下次启动时生效。缺少 Key 只影响额度查询，本地用量同步不依赖 Key。

Key 以明文保存在个人配置中。分享项目时保留配置模板，不包含 `config.json`、`.config-*.tmp` 或 `data/`；这些路径已列入 [.gitignore](.gitignore)。复制到另一台电脑时，如果一并携带个人配置，就会沿用其中的路径和 Key。

命令行指定 `launch-hook.ps1 -NoMessageBox` 时不显示首次配置窗口；缺少配置会返回错误。

## 扫描与刷新

Droid 用量同步和 Factory 额度查询是两个独立任务。

| 操作或设置 | 当前行为 |
| --- | --- |
| 启动并连接 Hook | 先执行一次 Droid 用量同步。 |
| 原版“每 N 秒扫描” | 读取数据库目录旁 `settings.json` 中的 `usageDashboardRefreshIntervalMs`。缺失或无效时使用 60 秒，最短 2 秒。 |
| 页头“立即同步” | 同时请求一次 Droid 同步。 |
| Droid 页“立即刷新” | 刷新 Factory 额度。 |
| `quotaRefreshSeconds` | 仅控制额度查询，不随原版扫描下拉框改变。 |

Droid 在上一轮同步完成后读取间隔，再安排下一轮；慢任务不会重叠执行。修改原版间隔不会立即重排已经等待中的任务。

目前还存在以下差异：

- 尚未跟随原版的自动扫描开关；切换页面或隐藏窗口也不会暂停 Droid 的定时扫描。
- 自定义数据库目录时，如果该目录旁没有原版设置文件，会回退到默认扫描间隔。
- Hook 写入数据库与原版刷新统计界面不是同一个动作，界面可能稍后才显示新增记录。

## 统计口径与限制

**当前导入的是会话累计用量的增量，不是逐请求账单，也不会将对话正文导入原版“会话”页面。** 一条记录可能涵盖多次回复，不能直接作为实际请求次数。

- **用量一致性**：按数据库内已经导入的累计值对账，在同一事务中保存增量和采样信息。累计值倒退、重复会话 ID 或文件读取不完整时会跳过或提示。
- **日期归属**：首次导入、跨日或缺少可信采样边界的补录标记为“日期未分配”。Droid 页的今日用量只包含前后采样均在当天的增量。
- **费用归属**：只有模型证据完整且数据库中存在精确匹配价格时才估算费用；其余保留未知状态。多模型会话不会将全部 Token 归到最后一个模型。
- **原生汇总**：原版统计页不了解全部 Droid 归属信息；未知费用的 `0` 是占位值，日期未分配记录使用导入时间。判断今日用量请结合 Droid 页的“统计说明”。
- **历史数据**：旧版导入记录保留原值，不会因更换启动方式而自动修正。
- **额度查询**：请求失败时显示错误和最近一次成功的旧数据，不将失败时间作为成功更新时间。

### tok/s 与首字时间

Hook 读取 `droid-log-single.log` 及其轮换文件中的请求总耗时、首 Token 耗时、成功消息 ID 和最终用量。只有会话、四类 Token、已知模型和采样时间能够唯一匹配时，才补全原生记录的耗时字段。

多请求合并、日志缺失、重试、供应商轮换或匹配存在歧义时，不填入新的速度数据。已有耗时也不会被自动覆盖。

在 CC Switch 4.0.12 中，Droid 属于会话日志来源，显示口径为：

```text
≈ tok/s = 输出 Token ÷ 请求总秒数
```

该口径包含首字等待，要求输出至少 200 Token、总耗时至少 1 秒；首字时间单独显示并带 `≈`。即使能够补全耗时，不满足显示门槛仍会显示 `—`。原版本地路由请求使用扣除首字的另一套公式，详见[原版格式化代码](https://github.com/farion1231/cc-switch/blob/v4.0.12/src/components/usage/format.ts)。

扫描间隔不会被当作生成耗时，但较长间隔更容易将多次请求合并，降低速度匹配率。Hook 不发送额外测速请求。

## 工作方式

```text
Open-Hook.cmd
  └─ launch-hook.ps1
      ├─ 首次配置（仅在缺少配置文件时）
      └─ pythonw.exe + addon/hook_client.py
          ├─ 启动原版 CC Switch
          ├─ 连接本次进程的 WebView2 页面并加载 Hook
          └─ 执行用量同步与额度查询
```

运行期间有一个随本次 CC Switch 会话存活的助手进程。完整退出原版后，助手取消后续任务并收尾退出；仅关闭到托盘时继续运行。

调试端口动态分配并绑定回环地址，通过原版子进程的环境变量启用。连接前核对监听进程归属，只接受 Tauri 应用页面。项目不修改原版 EXE，不注册开机启动项，也不改写系统 WebView2 策略。

## 数据与设置保护

启动前将原版 `~/.cc-switch/settings.json` 保存到项目的 `data/settings-backups/`。首次使用没有设置文件时正常继续；已有文件无法读取或 JSON 损坏时停止启动，保留原文件及可读取的副本。

这项保护不会自动修复或恢复设置，也不拦截原版运行中的保存行为。设置备份可能包含账户或同步配置，应作为个人数据保留。

用量同步会在原版数据库中保存 `droid_session` 记录，以及 `droid_addon_snapshots`、`droid_addon_records`、`droid_hook_timings` 辅助表。它们属于持久化统计数据，不在项目的 `data/` 日志目录中。

## 从旧版 Addon 迁移

先停止旧版 Droid Addon 助手并停用其开机启动项，再使用本项目。新旧版本有互斥检查，新入口不会强制结束已有进程。

如果旧版留下 WebView2 调试策略，请按旧版的备份或卸载说明撤销；新项目不会覆盖这些策略。

已有数据库中的 Droid 记录会保留，同步以数据库中的已导入用量为依据，不需要复制旧版的同步进度文件。迁移时使用新项目自己的配置向导即可。

## 停用与移除

1. 从托盘完整退出 CC Switch，等待助手完成收尾。
2. 后续直接运行原版 `cc-switch.exe`，即可不加载本项目。
3. 不再需要时，按需保存个人配置和备份，再删除项目目录及自行创建的快捷方式。

移除项目不会删除原版数据库中的既有 Droid 用量记录或辅助表。普通入口仍可能在统计中显示这些历史数据，但不会加载本项目的 Droid 页面。

## 故障排查

| 情况 | 处理方式 |
| --- | --- |
| 提示已有 CC Switch 或旧助手运行 | 从托盘完整退出原版，并停止旧版助手，再打开入口。 |
| 已有配置中的 EXE 路径失效 | 修改 `config.json` 的 `ccSwitchExecutable`。首次向导只在配置文件不存在时出现。 |
| 提示缺少启动文件 | 确认 `python/`、`addon/` 和入口文件完整，项目目录可写。 |
| 额度查询失败 | 检查 Factory Key、网络和页面错误提示；本地用量同步可独立运行。 |
| 提示原版设置损坏 | 检查或恢复有效设置。Hook 不会自动重置，副本位于 `data/settings-backups/`。 |
| Hook 连接持续中断 | 完整退出原版后重新通过入口启动，并查看 `data/hook.log`。 |

运行状态保存在 `data/status.json` 和 `data/launches/`，诊断日志为 `data/hook.log`，约 1 MB 后轮换为 `hook.previous.log`。

连接持续中断超过 15 秒时，助手会退出并提示，原版窗口保留。调试端口随原版进程退出而关闭。原版升级后若改变界面或数据库结构，需要更新适配代码。

## 项目结构

| 文件或目录 | 职责 |
| --- | --- |
| `Open-Hook.cmd` / `launch-hook.ps1` | 用户入口与启动协调。 |
| `addon/first_run.ps1` | 首次配置窗口与配置保存。 |
| `addon/hook_client.py` / `addon/windows.py` | 进程生命周期、互斥与连接归属检查。 |
| `addon/renderer.py` / `addon/cdp.py` | 页面连接与 Hook 注入。 |
| `addon/inject.js` / `addon/native_usage.js` | Droid 页面与原生筛选适配。 |
| `addon/service.py` | 同步、额度查询及任务调度。 |
| `addon/droid_sync.py` / `addon/droid_timing.py` | 用量导入、统计归属与耗时匹配。 |
| `addon/factory_quota.py` | Factory 额度读取。 |
| `addon/config.py` / `addon/run_state.py` / `addon/settings_guard.py` | 配置、运行状态与原版设置备份。 |
| `python/` | 随附 Python 运行环境。 |
| `data/` | 本地状态、日志与设置备份，不提交到仓库。 |

## 来源与许可

本项目基于 CC-Switch-Droid-Addon 的 Droid 页面、额度查询与用量同步功能，参考 Codex-Hook 的启动和 Hook 生命周期方式组织。

项目使用 [MIT License](LICENSE)。随附 Python 的许可证见 [python/LICENSE.txt](python/LICENSE.txt)。
