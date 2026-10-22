# CC Switch Droid Hook

**English** | [简体中文](README.zh-CN.md)

A Windows extension that adds a Droid page, Factory quota information, and local usage synchronization to [CC Switch](https://github.com/farion1231/cc-switch).

Launch the unmodified CC Switch through `Open-Hook.cmd` to load the Hook for that session. The project includes a Python runtime and does not require a system Python installation or the old Addon directory.

**Current version: 2.2.8** · [Changelog (Chinese)](CHANGELOG.md) · [Configuration template](config.example.json) · [License](LICENSE)

## Features

- **Droid page**: View Factory plan quotas, local usage for today, and notes explaining the statistics.
- **Usage synchronization**: Import changes in Droid's cumulative session token counts into the CC Switch database.
- **Speed and time to first token**: Fill in timing data for records that can be reliably matched to local Droid request logs.
- **Native usage filters**: Switch directly between Droid and All on the usage dashboard.
- **First-run setup**: Select the CC Switch directory, enter a Factory API key, and continue launching after saving.
- **Settings backup**: Save a copy of CC Switch's device settings before launch and stop if the JSON is damaged.

The current integration uses CC Switch 4.0.12 as its compatibility reference, with the app-filter adapter updated and checked offline against the 4.0.17 source. It depends on the application's interface and database structure, so other versions may require changes. See the [changelog](CHANGELOG.md) for the validation scope of recent changes.

## Quick start

### Requirements

- Windows with Windows PowerShell and the ability to run CC Switch.
- An installed or extracted copy of CC Switch.
- The complete project directory, including `python/`, `addon/`, and `config.example.json`.
- A Factory API key for account quota queries.
- Existing Droid session files and runtime logs if you want to import local usage and timing data.

### First launch

1. Fully exit any running CC Switch instance from the system tray. Closing its window may leave the process running.
2. Double-click `Open-Hook.cmd` in the project directory.
3. If `config.json` does not exist, complete the setup dialog:
   - Select the folder containing `cc-switch.exe`, or paste the full path to that executable.
   - Enter your Droid / Factory API key. It is masked by default; select **显示 API Key** to reveal it.
4. Click **保存并启动** (Save and launch). The launcher creates the configuration and continues launching CC Switch with the Hook.
5. Open **Droid** in the sidebar, or use the Droid filter on the usage dashboard.

The setup dialog currently uses Simplified Chinese. You can create a key on the [Factory API Keys](https://app.factory.ai/settings/api-keys) page. Setup checks the executable path and key input format; the quota query after launch determines whether the key is valid.

Canceling or closing setup does not create a configuration or launch the application. If a configuration already exists, the launcher uses it without reopening setup or overwriting it.

### Daily use and updates

Use `Open-Hook.cmd` whenever you want the Droid features. Opening CC Switch directly does not load this extension.

After updating project files, fully exit CC Switch from the system tray and launch it again through the entry point. A running helper does not automatically reload changed code.

## Configuration

Personal settings are stored in `config.json` in the project directory. See [config.example.json](config.example.json) for defaults.

| Field | Description |
| --- | --- |
| `ccSwitchExecutable` | Path to the original `cc-switch.exe`. If left empty in an existing configuration, the launcher searches PATH and common installation directories for the current user. |
| `ccSwitchArguments` | Additional application arguments; an empty array by default. Arguments cannot override the debugging port or user data directory managed by the launcher. |
| `factoryApiKey` | Factory API key, required by the setup dialog. If left empty in an existing configuration, the helper checks `FACTORY_API_KEY` in the environment, then `~/.factory/.env`. |
| `quotaRefreshSeconds` | Quota refresh interval: 60 seconds by default, with a range of 15–86400 seconds. Failures increase the retry interval and mark previous data as stale. |
| `ccSwitchDbPath` | CC Switch database path. Defaults to `~/.cc-switch/cc-switch.db`; a missing database is not replaced with an empty one. |
| `droidSessionsDir` | Droid session directory. Defaults to `~/.factory/sessions`. |
| `droidLogsDir` | Droid request log directory. Defaults to the `logs` directory next to the session directory, usually `~/.factory/logs`. |
| `startupTimeoutSeconds` | Initial connection timeout: 45 seconds by default, with a range of 10–120 seconds. |

`~` refers to the current user's home directory. Relative paths are resolved from the project directory, and environment variables are supported. Setup handles JSON escaping automatically. When editing the file manually, use forward slashes or escape each backslash as `\\`.

The Factory key, quota interval, and data paths are reloaded approximately every 10 seconds. Changes to the executable path, launch arguments, and startup timeout take effect on the next launch. A missing key only affects quota queries; local usage synchronization does not require it.

The key is stored as plain text in the personal configuration. When sharing the project, include the template but exclude `config.json`, `.config-*.tmp`, and `data/`. These paths are listed in [.gitignore](.gitignore). Copying a personal configuration to another computer also carries over its paths and key.

Running `launch-hook.ps1 -NoMessageBox` does not show setup. A missing configuration is reported as an error instead.

## Scanning and refresh

Droid usage synchronization and Factory quota queries run as separate tasks.

| Action or setting | Current behavior |
| --- | --- |
| Launch and connect the Hook | Run an initial Droid usage sync when native automatic scanning is enabled. |
| Native automatic scanning toggle | Follow `sessionAutoSyncEnabled`; disabling it stops scheduling automatic scans while keeping manual sync available. |
| CC Switch's “Scan every N seconds” setting | Read `usageDashboardRefreshIntervalMs` from `~/.cc-switch/settings.json`, independently of the database directory. Missing, invalid, or longer-than-one-day intervals fall back to 60 seconds; the minimum is 2 seconds. |
| “Sync now” in the header, empty state, or data sources dialog | Also request a Droid sync. |
| “Refresh now” on the Droid page | Refresh Factory quota information. |
| `quotaRefreshSeconds` | Control quota queries only, independently of the native scanning dropdown. |

Droid schedules the next scan after the previous one finishes; slow jobs do not overlap. Scan preferences are reread approximately every 2 seconds. Re-enabling automatic scanning or changing its interval requests a scan once idle. Disabling the toggle does not interrupt an in-flight scan. Unreadable native settings pause automatic scanning with a warning; manual sync remains available.

Current differences from native scanning:

- While automatic scanning is enabled, switching pages or hiding the window does not pause Droid scans.
- After importing usage or filling timing fields, the Hook emits the native `usage-log-recorded` event to refresh statistics. Failed notifications are retried and reported on the Droid page.

The usage dashboard's Droid icon uses the same app-filter state as native app buttons (`appType=droid`). Switching apps clears provider and model filters while preserving the date range and status code. Selecting Droid again preserves its current filters. Empty ranges remain selectable and use the native empty-list or zero-value display. Changing dates keeps Droid selected; All and other app buttons switch normally. Selection no longer depends on a Droid provider-menu option.

## Statistics and limitations

**Imported records represent changes in cumulative session usage, rather than individual request bills. Conversation text is not imported into CC Switch's native Sessions page.** One record may cover several responses and should not be counted as one actual request.

- **Usage consistency**: Compare cumulative counts against previously imported totals and save usage changes and sampling information in one transaction. Decreasing counters, duplicate session IDs, or incomplete reads are skipped or reported.
- **Date attribution**: Initial imports, changes spanning multiple days, and imports without reliable sampling boundaries are marked as having an unallocated date. The Droid page's daily totals only include changes whose two samples fall within the current day.
- **Model identification**: Prefer actual transcript model IDs over later configuration changes. Missing assistant messages can be supplemented by a uniquely matched completed request within a trusted sample, explicitly labeled as inferred. Without per-request token evidence, costs and timings are not backfilled. Aggregates involving multiple models remain mixed rather than assigning all tokens to the main model.
- **Cost attribution**: Estimate costs only when model evidence is complete and the database contains an exact pricing match. Other costs remain unknown. Sessions using multiple models are not assigned entirely to the last model.
- **Native totals**: The native dashboard does not understand all Droid attribution metadata. A cost of `0` can be a placeholder for an unknown cost, and records with unallocated dates use the import time. Consult the statistics notes on the Droid page when interpreting daily usage.
- **Historical data**: Existing records from older versions keep their values. Changing the launch method does not automatically correct them.
- **Quota queries**: Failed requests display an error alongside the most recent successful data. A failed attempt does not replace the last successful refresh time.

### tok/s and time to first token

The Hook reads total request duration, time to first token, successful message IDs, and final token usage from `droid-log-single.log` and its rotated files. It fills timing fields only when the session, all four token counts, known model, and sampling time uniquely match a request.

No new timing data is added for combined requests, missing logs, retries, provider rotation, unknown or mixed models, missing sampling boundaries, or ambiguous matches. Initial and legacy imports are not matched merely because their import timestamp is close to a request. Existing timing values are not automatically overwritten.

In CC Switch 4.0.12, Droid is treated as a session log source and uses this display formula:

```text
≈ tok/s = output tokens ÷ total request duration in seconds
```

This includes the wait for the first token and requires at least 200 output tokens and a total duration of at least 1 second. Time to first token is displayed separately, also with `≈`. Records below these thresholds display `—` even when timing data is available. Native requests recorded through the local proxy use a different formula that subtracts time to first token; see the [native formatting code](https://github.com/farion1231/cc-switch/blob/v4.0.12/src/components/usage/format.ts).

The scanning interval is never used as generation time. However, longer intervals are more likely to combine multiple requests into one record, reducing timing match coverage. The Hook does not send additional requests to measure speed.

## How it works

```text
Open-Hook.cmd
  └─ launch-hook.ps1
      ├─ First-run setup, if configuration is missing
      └─ pythonw.exe + addon/hook_client.py
          ├─ Launch CC Switch
          ├─ Connect to that process's WebView2 page and load the Hook
          └─ Synchronize usage and query quotas
```

A helper process runs for the lifetime of the launched CC Switch session. When the application fully exits, the helper cancels pending work, finishes cleanup, and exits. Closing CC Switch to the system tray keeps the session running.

The debugging port is dynamically assigned and bound to a loopback address, using the child process's environment to enable it. The helper checks process ownership before connecting and only accepts Tauri application pages. The project does not modify the original executable, register startup entries, or change system WebView2 policies.

## Data and settings protection

Before launch, the helper copies CC Switch's `~/.cc-switch/settings.json` into the project's `data/settings-backups/` directory. A missing settings file on first use is allowed. An existing file that cannot be read or contains damaged JSON stops the launch, preserving the original and any readable backup.

This protection does not automatically repair or restore settings, or intercept settings writes while CC Switch is running. Backups can contain account or synchronization settings and should be kept private.

Usage synchronization stores `droid_session` records and the `droid_addon_snapshots`, `droid_addon_records`, `droid_hook_timings`, and `droid_hook_models` tables in the CC Switch database. These are persistent statistics, separate from the project's `data/` log directory.

## Migrating from the old Addon

Stop the old Droid Addon helper and disable its startup entry before using this project. A shared lock prevents conflicting instances; the new launcher does not forcibly stop existing processes.

If the old Addon left WebView2 debugging policies behind, remove them according to its backup or uninstall instructions. This project does not overwrite those policies.

Existing Droid records in the database are preserved. Synchronization uses the totals already imported into that database, so the old sync progress file is not needed. Use this project's setup dialog to create its own configuration.

## Disabling and removing

1. Fully exit CC Switch from the system tray and wait for the helper to finish cleanup.
2. Open the original `cc-switch.exe` directly to use it without this extension.
3. When the extension is no longer needed, save any personal configuration or backups you want to keep, then delete the project directory and any shortcuts you created.

Removing the project does not delete existing Droid usage records or helper tables from the CC Switch database. The normal application may still display those historical records, but it will not load this project's Droid page.

## Troubleshooting

| Situation | What to do |
| --- | --- |
| CC Switch or an old helper is already running | Fully exit CC Switch from the system tray and stop the old helper before opening the launcher. |
| The configured EXE path is no longer valid | Update `ccSwitchExecutable` in `config.json`. Setup appears only when the configuration file is absent. |
| Startup files are missing | Keep `python/`, `addon/`, and the launch files together, and ensure the project directory is writable. |
| Quota queries fail | Check the Factory key, network connection, and error shown on the page. Local usage sync can continue independently. |
| Native settings are reported as damaged | Inspect or restore a valid settings file. The Hook does not reset it automatically; backups are in `data/settings-backups/`. |
| The Hook connection remains interrupted | Fully exit CC Switch, restart through the launcher, and inspect `data/hook.log`. |

Runtime status is stored in `data/status.json` and `data/launches/`. Diagnostic output is written to `data/hook.log`, which rotates to `hook.previous.log` at approximately 1 MB.

If a connection interruption lasts more than 15 seconds, the helper exits and reports the problem while leaving the original application window open. The debugging port closes when the original application process exits. Changes to the application's interface or database in future releases may require integration updates.

## Project structure

| File or directory | Purpose |
| --- | --- |
| `Open-Hook.cmd` / `launch-hook.ps1` | User entry point and launch coordination. |
| `addon/first_run.ps1` | Setup dialog and configuration saving. |
| `addon/hook_client.py` / `addon/windows.py` | Process lifecycle, instance locking, and connection ownership checks. |
| `addon/renderer.py` / `addon/cdp.py` | Page connections and Hook injection. |
| `addon/inject.js` / `addon/native_usage.js` | Droid interface and native filter integration. |
| `addon/service.py` | Usage sync, quota queries, and scheduling. |
| `addon/droid_sync.py` / `addon/droid_timing.py` | Usage import, statistics attribution, and timing matches. |
| `addon/factory_quota.py` | Factory quota queries. |
| `addon/config.py` / `addon/run_state.py` / `addon/settings_guard.py` | Configuration, runtime status, and native settings backups. |
| `python/` | Bundled Python runtime. |
| `data/` | Local status, logs, and settings backups; excluded from the repository. |

## Credits and license

This project builds on the Droid interface, quota queries, and usage synchronization from CC-Switch-Droid-Addon, with its launcher and Hook lifecycle organized after Codex-Hook.

The project is distributed under the [MIT License](LICENSE). The bundled Python license is available in [python/LICENSE.txt](python/LICENSE.txt).
