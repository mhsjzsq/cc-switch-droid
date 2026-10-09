# CC Switch Droid Addon

Show your [Droid](https://factory.ai/) session usage inside [CC Switch](https://github.com/farion1231/cc-switch).

This Windows add-on imports token usage from Droid's local session logs into CC Switch's **Usage Statistics** and adds a **Droid** page for Factory quota and today's usage. It also adds a Droid filter to the statistics page, so you can find imported sessions quickly.

## Features

- **Droid usage in CC Switch:** Import input, output, cache read, and cache creation tokens from local Droid sessions. New usage is added incrementally as sessions change.
- **Droid filter:** Show only Droid records in CC Switch's Usage Statistics.
- **Factory quota at a glance:** View available five-hour, weekly, and monthly usage windows and reset countdowns when the Factory API provides them. A Factory API key is required for this panel.
- **Today's activity:** See today's imported records, tokens, and estimated cost on the Droid page.
- **Automatic updates:** Usage sync follows CC Switch's Usage Statistics auto-refresh interval; when auto-refresh is off, it syncs every 60 seconds. CC Switch's **Sync Now** button also triggers a Droid sync.
- **No CC Switch executable patching:** The interface additions are injected into CC Switch's WebView2 window.

## Requirements

- Windows 10 or 11
- CC Switch 3.x
- Droid, launched at least once so its local session directory exists

## Install

1. Download or clone this repository into a permanent folder. If you are moving it from another computer, do not copy `data/sync_state.json`.
2. Run `install.cmd`. You can enter a [Factory API key](https://app.factory.ai/settings/api-keys) for quota display, or press Enter and configure it later. Session usage import does not require an API key.
3. When Windows asks for administrator access, allowing it lets the installer set the WebView2 debugging argument for `cc-switch.exe`. If you decline, the helper can restart a newly launched CC Switch once with that argument instead.
4. Open CC Switch. A **Droid** entry should appear in the sidebar within a few seconds.

The installer adds a Windows startup shortcut and runs the included portable Python helper in the background. Keep the add-on folder in place after installation; if you move it, run `install.cmd` again.

## Configuration

Edit `config.json` to change these settings. Most changes take effect within about 10 seconds.

| Setting | Description |
| --- | --- |
| `factoryApiKey` | Optional key for Factory quota display. If empty, the helper also checks `FACTORY_API_KEY` and `~/.factory/.env`. |
| `debugPort` | Local WebView2 debugging port; defaults to `9333`. Re-run the installer and restart CC Switch after changing it. |
| `quotaRefreshSeconds` | Factory quota refresh interval; minimum 15 seconds. |
| `autoRestartWithoutPolicy` | Whether the helper may restart a recently launched CC Switch if the debugging port is unavailable. |
| `ccSwitchDbPath` | Optional CC Switch database path; defaults to `~/.cc-switch/cc-switch.db`. |
| `droidSessionsDir` | Optional Droid sessions path; defaults to `~/.factory/sessions`. |

Keep your API key private. Do not publish a populated `config.json` or files in `data/`.

## Notes

- The cost shown for imported sessions is estimated from CC Switch's model price table. It may differ from Factory's actual billing or quota consumption.
- The Droid page and filter are interface additions; they do not manage providers or switch configurations.
- The WebView2 debugging port listens on `127.0.0.1`. Other programs on the same computer can access it and control the CC Switch window.
- Interface changes in future CC Switch releases may require an update to `addon/inject.js`.

## Uninstall

Run `uninstall.cmd`. It can optionally remove imported Droid usage records from the CC Switch database. After uninstalling, restart CC Switch and delete the add-on folder.
