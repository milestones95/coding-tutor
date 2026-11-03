# Capture — LeetCode extension + ingest server

Records your LeetCode practice into `data/capture.db` at the repository root: code snapshots
while you type, and every Run and Submit result. That file is the input to the Python
analyzer (`src/tutor/`), which only ever opens it read-only. Capture makes no LLM calls and
runs no analysis (D-015).

Requires Node 20.19.5 (`.nvmrc`). All commands run from the repository root.

## Install

```
npm --prefix ux-extension install
```

## Start the ingest server

```
npm --prefix ux-extension start
```

It listens on `http://localhost:7777` and writes `data/capture.db`. Leave it running while
you practise. Settings (environment variables):

| Variable | Default | |
|---|---|---|
| `PORT` | `7777` | must match `host_permissions` in `extension/manifest.json` |
| `LCA_DB` | `<repo>/data/capture.db` | the capture database |
| `LCA_IDLE_MINUTES` | `30` | a session with no activity for this long is ended |

## Load the extension in Chrome

1. Open `chrome://extensions` and turn on **Developer mode**.
2. Remove any older copy of "LeetCode Practice Analyzer" (for example one loaded from
   `leetcode-analyzer/extension`).
3. **Load unpacked** → choose this repo's `ux-extension/extension` folder.
4. Open a LeetCode problem and click **Run**: a `judge_events` row with `kind = 'run'`
   appears in `data/capture.db`.

After editing extension files, click the reload icon on the extension card and reload the
LeetCode tab.

## Other commands

```
npm --prefix ux-extension test           # builder unit tests (tests/unit/capture)
npm --prefix ux-extension run typecheck
npm --prefix ux-extension run seed:problems   # optional: fill the problems table from LeetCode's public list
```
