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

Plus a **Settings** page (~140 knobs, all of which change real behaviour) at
`/settings`, and an **Extract** page at `/extract` that writes the current view
to JSON, Markdown, or CSV. Both are pages in their own right — their own address
and their own title, the session's view tabs and source filter come off the nav
while one is open, and Back returns you to the session rather than out of the
dashboard. The brand in the corner links back.

Six palettes, under Settings → Appearance → Palette. Five are `DESIGN.md`'s own
stocks, and **midnight** — the doc's green-cast near-black — is the default:

| | |
|---|---|
| **midnight** | the doc's green-cast near-black, declared in OKLCH — the default |
| **light** | warm off-white, the other end of that same ramp |
| **dark** | warm charcoal |
| **solarized** | the classic Solarized sand, with its signature blue |
| **oled** | true `#000000`, neon cyan accent |
| **paper** | this dashboard's own warm off-white |

A palette brings the accent `DESIGN.md` pairs with it — a lighter green on the
dark stocks, because a 0.52 green sinks into a 0.16 background. Pick an accent by
hand and it survives every switch: a palette claims the accent only while it is
still the one the last palette put there. A palette name from an older build
(`ink`, `green`) reads as the stock it became rather than resetting to paper.

Text clears AA (4.5:1) on **light, dark, midnight and oled**. The small voices —
the 9.5px labels, the timestamps, the `--faint` ramp — are what that is measured
against, and two stocks needed work to get there: midnight's and dark's `--faint`
were under 4.5:1, and oled's ramp was one step too light. `paper` is left exactly
as it was, so its `--faint` still measures 2.8:1. `solarized` is the one palette
that cannot get there without ceasing to be Solarized: base2 is only 1.13:1 from
base3, so nothing clears AA on a base2 card, and the two secondary voices are
read off Solarized's own blue-grey hue at the lightest steps that do. Its
signature blue is left alone, so it reads about 3.2:1 as 10px text.

Hairlines are not a grey at all: they are the stock's foreground at 10% and 5%,
the derivation `DESIGN.md` calls for, so they read as a line rather than as white
on black. **Hairline strength** in Settings scales them, 100 being the doc's 10%,
0 removing every line.

Its settings live in `dashboard/trajectory.config.json`, next to the script. It is
written on the first change you make, or on the first page load that has a
migration to record. It never writes to `~/.claude/settings.json`.

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
