# traj-claude

Two small tools for **Claude Code**, no dependencies, on Linux, macOS, and
Windows.

| | |
|---|---|
| **[`statusline/`](statusline/)** | A status bar at the bottom of Claude Code: model, context bar, percent of window used, input/output tokens, message count, session cost. |
| **[`dashboard/`](dashboard/)** | A local web page that reads the session log Claude Code already writes and shows you exactly which tokens are in the context window — reasoning, tool calls, injections, everything — as a timeline, a flow, or a table. |

Both are plain Python 3.8+. Nothing to `pip install`. Neither one sends your
data anywhere.

> **Work in progress.** The status line is finished and in daily use. The
> dashboard runs and is usable but is still changing — there is no packaging
> and no test suite yet. The parts below work today.

---

## 1. The status bar

```sh
git clone https://github.com/abdulwasea89/traj-claude.git
cd traj-claude/statusline
python3 install.py
```

On Windows use `python` instead of `python3`. Then restart Claude Code.

That is the whole setup. `install.py` copies the script into your Claude Code
directory (`~/.claude`, or `%USERPROFILE%\.claude` on Windows) and points
`statusLine` at it in `settings.json`. It backs the file up first and touches
only that one key — see [statusline/README.md](statusline/README.md#what-it-does-to-your-settings) for exactly what it writes.

The bar looks like this:

```
deepseek-v4-flash │ scripts │ █████████░░░ │ 77% │ ctx 153.8k/200.0k │ ↑ in 97.77M │ ↓ out 614.7k │ Σ 3.47b │ 1018 msg │ $199.22
```

Options, costs, and troubleshooting: **[statusline/README.md](statusline/README.md)**.

## 2. The dashboard

```sh
cd traj-claude/dashboard
python3 trajectory.py            # a report in the terminal
python3 trajectory.py serve      # http://127.0.0.1:8788
```

It reads `~/.claude/projects/*/*.jsonl` — the transcripts Claude Code writes
anyway — and binds to `127.0.0.1` only. Three views:

- **Timeline** — a waterfall of turns and lanes. Hover a bar for details, click
  it for the full record.
- **Flow** — the session as nested steps, with each tool call paired to its
  result.
- **Table** — every event, filterable, expandable.

Plus a **Settings** page (~140 knobs, all of which change real behaviour) and an
**Extract** page that writes the current view to JSON, Markdown, or CSV.

Its settings live in `dashboard/trajectory.config.json`, next to the script,
created on first save. It never writes to `~/.claude/settings.json`.

## Why the numbers are right

Claude Code's transcript writes each assistant message about 2.5× as streaming
snapshots, each with a byte-identical copy of the same `usage` object. Summing
every record inflates your totals by that factor. Both tools deduplicate by
`message.id`, so the counts are distinct messages, not transcript writes. The
details, including the byte-offset cache that makes re-counting cheap, are in
the docstring at the top of `statusline/statusline-command.py`.

## Layout

```
statusline/
  statusline-command.py   the bar itself — reads the Claude Code JSON on stdin
  install.py              cross-platform installer for settings.json
  README.md               what each field means, every env knob, troubleshooting
dashboard/
  trajectory.py           transcript parsing, the terminal report, `serve`
  trajectory_dashboard.py the page — waterfall, flow, table, settings, extract
```

## Licence

MIT. See [LICENSE](LICENSE).
