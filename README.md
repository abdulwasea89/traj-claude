# traj

**Read the session log Claude Code already writes — by source, in order, in a browser.**

`traj` is a small, dependency-free tool for looking at your own Claude Code
sessions. Claude Code appends everything the model sees to a JSONL transcript:
system prompt, reasoning, tool calls and their results, subagent activity, and
every context injection. `traj` reads those files and shows you the event
stream — who put each token in the context window, and when.

Two ways to look at it:

- a **terminal report** grouped by source, then in order
- a **local dashboard** (`serve`) with a waterfall timeline, a flow view, and a
  filterable table, plus a full settings page

> **Status: work in progress.** This is not finished and not yet packaged. There
> is no `pip install`, no PyPI release, and no installer. The parts described
> below work today; the parts under *Not done yet* do not. It is published early
> so the idea is visible and the shape can be argued with.

---

## Name

`traj` — the abbreviation of *trajectory*, four letters, one syllable, easy to
type on any keyboard. The project is a tool for reading a session's
trajectory, so the name is the thing itself rather than a metaphor for it.

## Requirements

- **Python 3.8 or newer.** That is the whole list.
- No third-party packages. Standard library only.
- Works on Linux, macOS, and Windows — no shell scripts, no `fork`, no POSIX
  assumptions. Paths come from `Path.home()`, so `~/.claude` resolves correctly
  on all three.

## Install

Nothing to install yet. Clone it and run it:

```sh
git clone https://github.com/abdulwasea89/traj.git
cd traj
python3 trajectory.py            # report on the session you are in
python3 trajectory.py serve      # open the dashboard in a browser
```

On Windows use `python` in place of `python3`.

Claude Code's own directory is found at `~/.claude` (`%USERPROFILE%\.claude` on
Windows). Sessions are read from `~/.claude/projects/*/`. Nothing is written
there except an optional settings file (see below).

## Use

### Terminal report

```sh
python3 trajectory.py                 # the session you are in
python3 trajectory.py de2b7ace        # a specific session, by id or id-prefix
python3 trajectory.py --all           # every session transcript on disk
python3 trajectory.py --limit 100     # more events (default 30)
python3 trajectory.py --source think  # only one source
```

### Dashboard

```sh
python3 trajectory.py serve           # http://127.0.0.1:8788
python3 trajectory.py serve --port 9000
```

The dashboard binds to `127.0.0.1` only. It reads your transcripts and renders
them locally; nothing is uploaded anywhere. The server is threaded, and the two
endpoints that change state (`/api/config`, `/api/shutdown`) require a custom
header that forces a CORS preflight this server never approves — so a page you
merely visit cannot rewrite your settings or stop the server.

Views:

- **Timeline** — a waterfall of turns and lanes, hoverable, click a bar for
  the full record.
- **Flow** — the session as nested steps, bash calls paired with their results.
- **Table** — every event, filterable, expandable.

There is also a **Settings** page (about 140 knobs in 16 groups) and an
**Extract** page that writes what is on screen to JSON, Markdown, or CSV.

## Settings

Settings live in `trajectory.config.json`, next to the script, created on first
save. Every knob in it changes real behaviour — there is deliberately no
catalogue of cosmetic toggles, because a switch that nothing reads teaches you
not to trust the panel. Each knob declares when a change takes effect:

- `live` — the page reacts immediately
- `open` — applied when a session page is loaded
- `restart` — read at launch, so it lands next time you serve

The definitions live in `CONFIG_SPEC` in `trajectory.py` and are shipped to the
browser in the state payload, so the Python side and the page cannot drift
apart.

**`traj` never writes to `~/.claude/settings.json`.** That file holds your API
token in plaintext; a web UI that can rewrite it can break your access to the
API from the browser. Settings for this tool stay in this tool's own file.

## Not done yet

Honest list, roughly in the order I would fix it:

- **No packaging.** No `pyproject.toml`, no console entry point, no
  `pipx install`. You run it from a clone.
- **No tests.** Not one. The parsing is verified by hand against real sessions.
- **No CI**, so nothing checks that it still runs on Windows or macOS beyond
  the absence of POSIX-only calls.
- **Not renamed.** Files are still `trajectory.py` / `trajectory_dashboard.py`
  while the project is `traj`; the rename is pending so it does not break an
  existing install.
- **Server-side knobs are thin.** `bind`, `log_requests`, `payload_cap`, and
  `event_cap` exist in the spec but are not all honoured yet.
- **Keyboard shortcuts are partial.** The bindings are configurable, but j/k
  navigation only walks the inspect sidebar, not the flow.
- **Some bookkeeping records are still classified as model-visible**
  (`system:turn_duration`, `system:compact_boundary`), which makes the
  per-source totals slightly generous.
- **The status line** in the author's `~/.claude/statusline-command.py` is a
  companion tool and is not part of this repository yet.

## Licence

MIT. See `LICENSE`.
