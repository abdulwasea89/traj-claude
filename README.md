# traj-claude

Two small tools for **Claude Code**, no dependencies, on Linux, macOS and Windows.

| | |
|---|---|
| **[`statusline/`](statusline/)** | A status bar at the bottom of Claude Code: model, context bar, percent of window used, input/output tokens, message count, session cost. |
| **[`dashboard/`](dashboard/)** | A local web page that reads the session log Claude Code already writes and shows you exactly which tokens are in the context window — reasoning, tool calls, injections, everything — as a timeline, a flow, or a table. |

Both are plain Python 3.8+. Nothing to `pip install`. Neither one sends your
data anywhere.

📖 **[Full documentation](https://abdulwasea89.github.io/traj-claude/)** — this
README is the short version.

> **Work in progress.** The status line is finished and in daily use. The
> dashboard runs and is usable but is still changing — there is no packaging and
> no test suite yet. Everything below works today.

---

## 1. The status bar

Claude Code reserves one row at the bottom of the terminal. This fills it:

```
deepseek-v4-flash │ scripts │ █████████░░░ │ 77% │ ctx 153.8k/200.0k │ ↑ in 97.77M │ ↓ out 614.7k │ Σ 3.47b │ 1018 msg │ $199.22
```

| field | meaning |
|---|---|
| `deepseek-v4-flash` | the model serving this session |
| `scripts` | the project directory you are in |
| `█████████░░░` | context window used, colour-shifting green → yellow → orange → red |
| `77%` | the same thing as a number |
| `ctx 153.8k/200.0k` | tokens currently in the window, over your configured limit |
| `↑ in 97.77M` | **cumulative** input: fresh input + cache reads + cache writes, all session |
| `↓ out 614.7k` | cumulative output tokens this session |
| `Σ 3.47b` | all-time tokens across every session, from Claude Code's own `stats-cache.json` |
| `1018 msg` | your prompts plus the model's replies, this session |
| `$199.22` | derived session cost — only shown when you supply rates |

Fields drop out rather than showing a placeholder when they are not available:
with no transcript yet you get the bar, `0%`, and `no transcript yet`.

### Install it

```sh
git clone https://github.com/abdulwasea89/traj-claude.git
cd traj-claude/statusline
python3 install.py
```

On Windows use `python` instead of `python3`. Then restart Claude Code. That is
the whole setup.

`install.py` copies the script into your Claude Code directory (`~/.claude`, or
`%USERPROFILE%\.claude` on Windows) and points `statusLine` at it in
`settings.json`. It backs the file up first and touches only that one key —
[exactly what it writes](statusline/README.md#what-it-does-to-your-settings).

```
python3 install.py --dry-run          # show what would change, write nothing
python3 install.py --uninstall        # remove the statusLine entry
python3 install.py --python /usr/bin/python3.12
```

### Make it yours

Set these as environment variables. Under Claude Code the reliable place is the
`env` block of `settings.json`:

| variable | default | effect |
|---|---|---|
| `CLAUDE_CONTEXT_LIMIT` | `200000` | input context window in tokens — **set this to your model's real window** or the percentage is wrong |
| `CLAUDE_BAR_WIDTH` | `12` | width of the progress bar in cells |
| `CLAUDE_SHOW_PROJECT` | `1` | `0` hides the project name |
| `CLAUDE_EXACT` | `0` | `1` prints `3,431,260` instead of `3.43M` |
| `CLAUDE_COST_IN` / `_OUT` / `_CACHE_READ` / `_CACHE_WRITE` | — | USD per 1M tokens, per kind. Cost appears only once you supply at least one rate — guessing a price and printing it in dollars would be worse than printing nothing |
| `CLAUDE_QUOTA_PER_USD` | `500000` | quota units per dollar, for gateways that report cost that way |
| `CLAUDE_STATUSLINE_CACHE` | `~/.cache/claude-statusline` | where the scan cache lives |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Claude Code's directory, if you have moved it |

Costs, troubleshooting and every field in more detail:
**[statusline/README.md](statusline/README.md)**.

## 2. The trajectory dashboard

The transcript Claude Code writes contains everything the model saw. This reads
it and shows you the shape of it.

![The dashboard's Timeline view: one row per turn, each split into four lanes — Input, Model, Output and Tools — with bars placed by wall-clock time](docs/img/trajectory.png)

```sh
cd traj-claude/dashboard
python3 trajectory.py            # a report in the terminal
python3 trajectory.py serve      # http://127.0.0.1:8788
```

It reads `~/.claude/projects/*/*.jsonl` and binds to `127.0.0.1` only — the
transcript holds your prompts, your code and your file paths, so it does not go
on a network.

The bar chart above is the point of the whole thing. Each turn is one row, split
into four lanes:

| lane | what it measures |
|---|---|
| **Input** | waiting on the model |
| **Model** | it reasoning |
| **Output** | it writing the answer |
| **Tools** | tools running |

A turn that took four minutes and a turn that took four minutes and nineteen
tool calls look identical in a transcript and completely different here. Hover
any bar for the span it covers; click one for the full record.

### Three views and two pages

- **Timeline** — the event stream above, plus the per-source breakdown and one
  tile per source: tokens, events and share of the window. Click a tile to
  filter every view to it.
- **Flow** — the session as nested steps, with each tool call paired to the
  result it produced.
- **Table** — every event, in order, filterable and expandable.

Plus a **Settings** page (~140 knobs, all of which change real behaviour) at
`/settings`, and an **Extract** page at `/extract` that writes the current view
to JSON, Markdown or CSV. Both are pages in their own right — their own address
and their own title, the session's view tabs and source filter come off the nav
while one is open, and Back returns you to the session rather than out of the
dashboard. The brand in the corner links back.

### Six palettes

Under Settings → Appearance → Palette. Five are `DESIGN.md`'s own stocks, and
**midnight** — the doc's green-cast near-black — is the default:

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

A source colour is a saved setting, and its default was picked against paper's
light ground: a bar that reads at one lightness there sinks into a near-black
one. So the page never draws a source colour raw — it draws that colour at the
lightness the current stock asks for, same hue and same chroma, lifted 1.38×,
which is the ratio `DESIGN.md` itself uses between a stock's accent and its
dark-stock version. A bar, a dot, a table rail and a label that speaks in that
colour are all one value, so a colour you pick in Settings moves all of them.
The three light stocks draw the settings' exact values.

Scrollbars come from the palette too: thin, the stock's accent at 45%, on a
transparent track that lets the panel show through. It is the standard
`scrollbar-width`/`scrollbar-color` pair doing the work rather than
`::-webkit-scrollbar`, because that is what actually renders — a 14px
`::-webkit-scrollbar` rule leaves the bar at the platform's 15px here, while
`scrollbar-width:thin` takes it to 10. The pseudo-elements stay for older Blink,
which knows only those. This also fixed the page's own scrollbar, which was
coloured from `--bg-3` on `html`: the themes declare that token on `body`, so on
`html` it fell back to paper's light value and drew a white bar down the side of
every dark stock.

Its settings live in `dashboard/trajectory.config.json`, next to the script. It is
written on the first change you make, or on the first page load that has a
migration to record. **It never writes to `~/.claude/settings.json`.**

## Installation

Nothing to install beyond the clone. Both tools are standard-library Python 3.8+
and are run from the checkout.

| | |
|---|---|
| **Python** | 3.8 or newer. `python3 --version` |
| **Dependencies** | none, and that is a constraint rather than luck |
| **Platform** | Linux, macOS, Windows |
| **Status bar** | `python3 install.py` in `statusline/`, then restart Claude Code |
| **Dashboard** | nothing — `python3 trajectory.py` in `dashboard/` |
| **What it writes** | the status line's cache in `~/.cache/claude-statusline`; the dashboard's `dashboard/trajectory.config.json`; and only `install.py` ever touches `~/.claude/settings.json`, one key |

## Advanced

**The terminal report.** `trajectory.py --text` renders the same numbers as the
page, as text — useful over SSH, or in a script.

```sh
python3 trajectory.py --text
python3 trajectory.py --text --limit 100 --source reasoning
python3 trajectory.py --all            # every session on disk
python3 trajectory.py de2b7ace         # one session, by id or id-prefix
```

**A static snapshot.** `--html` writes a single self-contained file — no server,
no live updates. That is what you want when attaching it to a bug report rather
than watching it.

```sh
python3 trajectory.py --html --out session.html
```

**A different Claude Code directory.** Both tools read `CLAUDE_CONFIG_DIR`, so
you can point them at a copied directory and analyse a transcript from another
machine without touching your own:

```sh
CLAUDE_CONFIG_DIR=/mnt/backup/claude python3 trajectory.py --all
```

**The config file.** Every knob in Settings is in
`dashboard/trajectory.config.json`, keyed by the name the page shows. Delete the
file and the dashboard comes back up on its defaults. A knob that does not change
real behaviour is a bug, not a placeholder.

**Everything else** — the full command line, the server knobs, the payload caps,
where each tool stores things, and troubleshooting:
**[abdulwasea89.github.io/traj-claude](https://abdulwasea89.github.io/traj-claude/)**.

## Why the numbers are right

Claude Code's transcript writes each assistant message about 2.5× as streaming
snapshots, each with a byte-identical copy of the same `usage` object. Summing
every record inflates your totals by that factor — which is where a lot of "I
used 3 million tokens?" comes from. Both tools deduplicate by `message.id` (and
user records by `uuid`), so the counts are distinct messages, not transcript
writes. The details, including the byte-offset cache that makes re-counting
cheap, are in the docstring at the top of `statusline/statusline-command.py`.

Page-level sizes are a different thing: those are characters, not tokens, and
are estimated so that sources are comparable with each other. The session's real
billed usage is reported separately and is never an estimate.

## Collaborating

Issues and pull requests are both welcome — the project is small enough that
there is no process to learn. A few things make a change easy to take:

- **Open an issue first for anything structural.** The dashboard is still
  changing shape, and it is cheaper to agree on the shape before either of us
  writes it.
- **Standard library only.** No `pip install` for anyone, and no dependency to
  audit.
- **Keep the tokens in one place.** A colour or a size is a token in the
  stylesheet or a knob in `trajectory.py`'s `CONFIG_SPEC`, never a literal in a
  component. Every knob names the custom property it writes (`cssvar`) or the
  `data-` attribute it sets (`attr`), so the control and the thing it moves are
  one line apart rather than two lists that drift apart.
- **Say what you measured.** If a change is about contrast, speed or size, put
  the before-and-after numbers in the pull request. "Looks better" is hard to
  review; "2.76:1 → 4.61:1 on the 9.5px label" is not.
- **Test on a light stock and a dark one.** Almost every layout bug in this
  project so far has appeared on one and not the other.

The docs site under `docs/` is one self-contained HTML file and a folder of
screenshots — no build step. Edit it and push; the [Pages
workflow](.github/workflows/pages.yml) checks that every image it references
exists and then publishes it.

## Layout

```
statusline/
  statusline-command.py   the bar itself — reads the Claude Code JSON on stdin
  install.py              cross-platform installer for settings.json
  README.md               what each field means, every env knob, troubleshooting
dashboard/
  trajectory.py           transcript parsing, the terminal report, `serve`,
                          CONFIG_SPEC (every setting), and the HTTP server
  trajectory_dashboard.py the page — waterfall, flow, table, settings, extract
docs/
  index.html              the documentation site
  img/                    its screenshots
```

Both dashboard files are large single files on purpose: the page is one embedded
string, so there is no build step and nothing between `git clone` and a running
dashboard.

## Licence

MIT. See [LICENSE](LICENSE).
