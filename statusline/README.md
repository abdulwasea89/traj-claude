# The status bar

A single row at the bottom of Claude Code, in the space the status line uses:

![The bar in place at the bottom of a real session — under the model's last line of output and above the permission prompt. It reads deepseek-v4-flash, scripts, a 31% context bar, ctx 61.1k/200.0k, up in 170.54M, down out 1.06M, a 3.47b all-time total, 1766 msg and $123.90.](../docs/img/statusline-in-place.png)

| field | meaning |
|---|---|
| `deepseek-v4-flash` | the model serving this session |
| `scripts` | the project directory you are in |
| `███████░░░` | context window used, colour-shifting green → yellow → orange → red |
| `31%` | the same thing as a number |
| `ctx 61.1k/200.0k` | tokens currently in the window, over your configured limit |
| `↑ in 170.54M` | **cumulative** input: fresh input + cache reads + cache writes, all session |
| `↓ out 1.06M` | cumulative output tokens this session |
| `Σ 3.47b` | all-time tokens across every session, from Claude Code's own `stats-cache.json` |
| `1766 msg` | your prompts plus the model's replies, this session |
| `$123.90` | derived session cost — only shown when you supply rates |

Fields drop out rather than showing a placeholder when they are not available:
with no transcript yet you get the bar, `0%`, and `no transcript yet`.

## Install

```sh
cd statusline
python3 install.py
```

Windows: `python install.py`. Then restart Claude Code.

```
python3 install.py --dry-run          # show what would change, write nothing
python3 install.py --uninstall        # remove the statusLine entry
python3 install.py --python /usr/bin/python3.12
```

The installer **copies** `statusline-command.py` into your Claude Code directory
and sets `statusLine` in `settings.json`. If you keep Claude Code's config
somewhere else, it honours `CLAUDE_CONFIG_DIR`.

Because that is a copy rather than a link, a later `git pull` does **not** reach
the running bar — re-run `install.py` after pulling to pick up changes. And
`--uninstall` removes the `statusLine` entry but leaves the copy behind; delete
`~/.claude/statusline-command.py` yourself if you want the directory clean.

### What it does to your settings

Editing a file Claude Code owns deserves specifics, so:

- It backs the file up first, as `settings.json.bak-<timestamp>`, next to the
  original.
- It sets **exactly one key**. Your `env`, `permissions`, `hooks`, `model`,
  `theme`, and everything else are read, kept, and written back.
- It **never prints your `env` block**. For a lot of people that is where a
  plaintext API token lives, and a tool that echoes it into a terminal has
  leaked it into your scrollback.
- If `settings.json` is not valid JSON, it **refuses to write** and tells you
  why. A settings file broken by a helpful installer is a much worse problem
  than a missing status line.

The status line itself only ever *reads* from your Claude Code directory. The
one thing it writes is its own cache under `~/.cache/claude-statusline`.

## Options

Set these as environment variables. Under Claude Code the reliable place is the
`env` block of `settings.json`:

```json
{
  "env": {
    "CLAUDE_BAR_WIDTH": "16",
    "CLAUDE_CONTEXT_LIMIT": "1000000",
    "CLAUDE_COST_IN": "0.55",
    "CLAUDE_COST_OUT": "2.19"
  }
}
```

| variable | default | effect |
|---|---|---|
| `CLAUDE_CONTEXT_LIMIT` | `200000` | input context window in tokens — set this to your model's real window or the percentage is wrong |
| `CLAUDE_BAR_WIDTH` | `12` | width of the progress bar in cells |
| `CLAUDE_SHOW_PROJECT` | `1` | `0` hides the project name |
| `CLAUDE_EXACT` | `0` | `1` prints `3,431,260` instead of `3.43M` |
| `CLAUDE_COST_IN` | — | USD per 1M input tokens |
| `CLAUDE_COST_OUT` | — | USD per 1M output tokens |
| `CLAUDE_COST_CACHE_READ` | — | USD per 1M cache-read tokens |
| `CLAUDE_COST_CACHE_WRITE` | — | USD per 1M cache-write tokens |
| `CLAUDE_QUOTA_PER_USD` | `500000` | quota units per dollar, for gateways that report cost that way |
| `CLAUDE_STATUSLINE_CACHE` | `~/.cache/claude-statusline` | where the scan cache lives |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Claude Code's directory, if you moved it |

Cost is only shown when you supply at least one rate. Guessing a price and
printing it in dollars would be worse than printing nothing.

## Why the token numbers are not what you would get by summing the file

The transcript writes each assistant message roughly **2.5×**, as streaming
snapshots, each carrying a byte-identical copy of the same `usage` object.
Summing every record therefore inflates your totals by that factor.

This deduplicates by `message.id` (and user records by `uuid`), so the numbers
are exact counts of *distinct messages*, not of transcript writes. Re-counting
a long transcript on every render would be slow, so the scan keeps a byte-offset
cache per session and only reads what was appended since last time. Streaming
duplicates are consecutive, so a bounded window of recent ids catches them
without persisting every id a session ever emitted.

## Troubleshooting

**The bar does not appear.** Run the script by hand — a status line that crashes
prints nothing, which looks identical to a status line that was never
configured:

```sh
echo '{"model":{"display_name":"test"},"cwd":"/tmp"}' | python3 ~/.claude/statusline-command.py
```

It should print a bar. The rendering path never prints a traceback and never
exits non-zero — on a failure it degrades to a minimal line, because a broken
status line should not take the session with it. Note the two exceptions:
`CLAUDE_BAR_WIDTH` and `CLAUDE_CONTEXT_LIMIT` are parsed at import time, before
that guard, so a value that is not a number raises `ValueError` and exits 1.
That is a deliberately loud failure — a bar drawn at the wrong width, or a
percentage computed against the wrong window, is worse than no bar.

**The percentage is wrong.** `CLAUDE_CONTEXT_LIMIT` is 200000 by default. If
your model's window is a different size, the bar and the percent are both
scaled wrong.

**It is slow.** The first render on a long session scans the whole transcript;
after that it reads only the appended bytes. Delete
`~/.cache/claude-statusline` to force a full rescan.

**Cost shows `$0.00` or nothing.** No rates are set, or the gateway reports its
own cost as zero (many do). Supply `CLAUDE_COST_*` and the figure is derived
from token counts instead.
