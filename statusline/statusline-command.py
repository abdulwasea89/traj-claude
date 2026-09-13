#!/usr/bin/env python3
"""Claude Code status line.

Compact single row: model, context-usage bar, percent of window used,
input/output token totals, message count, and session cost.

Reads the Claude Code status line JSON payload on stdin. Never exits non-zero
and never prints a traceback -- on any failure it degrades to a minimal line.

Token accounting
----------------
The transcript writes each assistant message MANY times (streaming snapshots),
each carrying a byte-identical copy of the same `usage` object. Summing every
record therefore inflates totals by ~2.5x. Totals here are deduplicated by
`message.id` (and user records by `uuid`) so the numbers are exact counts of
distinct messages, not of transcript writes.

Cost
----
Claude Code cannot price this gateway's model, so `cost.total_cost_usd` comes
back as 0. A real cost is therefore computed from token counts times rates you
supply, and is only shown when you supply them.

Tunables (env vars):
    CLAUDE_CONTEXT_LIMIT      input context window in tokens (default 200000)
    CLAUDE_BAR_WIDTH          progress bar width in cells (default 12)
    CLAUDE_SHOW_PROJECT       set 0 to hide the project name (default 1)
    CLAUDE_EXACT              set 1 for 3,431,260 style instead of 3.43M
    CLAUDE_COST_IN            USD per 1M input tokens
    CLAUDE_COST_OUT           USD per 1M output tokens
    CLAUDE_COST_CACHE_READ    USD per 1M cache-read tokens
    CLAUDE_COST_CACHE_WRITE   USD per 1M cache-write tokens
"""

import json
import os
import sys
import time
import urllib.request

# ---------------------------------------------------------------- styling ---
RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
ORANGE = "\033[38;5;208m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
WHITE = "\033[97m"
SEP = f"{DIM}│{RESET}"

BAR_WIDTH = max(4, int(os.environ.get("CLAUDE_BAR_WIDTH", "12")))
CONTEXT_LIMIT = max(1000, int(os.environ.get("CLAUDE_CONTEXT_LIMIT", "200000")))
SHOW_PROJECT = os.environ.get("CLAUDE_SHOW_PROJECT", "1") != "0"
EXACT = os.environ.get("CLAUDE_EXACT", "0") == "1"
# Claude Code's directory. CLAUDE_CONFIG_DIR wins if it is set, so the bar
# reads the same files Claude Code does on a machine where it was moved.
CLAUDE_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
    os.path.expanduser("~"), ".claude")

CACHE_DIR = os.environ.get("CLAUDE_STATUSLINE_CACHE") or os.path.join(
    os.path.expanduser("~"), ".cache", "claude-statusline")
CACHE_VERSION = 2

# Dedupe windows. Streaming duplicates are consecutive, so a bounded recent-id
# list catches them without persisting every id a long session ever emitted.
WINDOW = 400


def _rate(name):
    try:
        return float(os.environ.get(name, "0") or 0)
    except Exception:
        return 0.0


COST_RATES = {
    "in": _rate("CLAUDE_COST_IN"),
    "out": _rate("CLAUDE_COST_OUT"),
    "cr": _rate("CLAUDE_COST_CACHE_READ"),
    "cw": _rate("CLAUDE_COST_CACHE_WRITE"),
}

# Gateway quota units per US dollar (new-api convention), and how long to trust
# a cached pricing fetch.
try:
    QUOTA_PER_USD = float(os.environ.get("CLAUDE_QUOTA_PER_USD", "500000") or 500000)
except Exception:
    QUOTA_PER_USD = 500000.0
PRICING_TTL = 86400


def fmt_cost(c):
    """Money: 2 decimals once it's meaningful, more while it's still tiny."""
    return f"${c:,.2f}" if c >= 0.01 else f"${c:.4f}"


def human(n):
    """Compact token format: 942 / 27.5k / 1.24M / 3.38b."""
    n = int(n)
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}k"
    if n < 1_000_000_000:
        return f"{n / 1_000_000:.2f}M"
    return f"{n / 1_000_000_000:.2f}b"


def num(n):
    """Compact by default; exact thousands-separated when CLAUDE_EXACT=1."""
    return f"{int(n):,}" if EXACT else human(n)


def color_for(pct):
    if pct >= 90:
        return RED
    if pct >= 75:
        return ORANGE
    if pct >= 50:
        return YELLOW
    return GREEN


def make_bar(pct):
    """Render the progress bar; 'filled' stays in 1..BAR_WIDTH-1 when partial."""
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct / 100.0 * BAR_WIDTH))
    if 0 < pct < 100:
        filled = max(1, min(BAR_WIDTH - 1, filled))
    c = color_for(pct)
    return f"{c}{'█' * filled}{DIM}{'░' * (BAR_WIDTH - filled)}{RESET}"


# ------------------------------------------------------------ transcript ---
def _load_cache(session_id):
    try:
        with open(os.path.join(CACHE_DIR, f"{session_id}.json")) as f:
            d = json.load(f)
        return d if isinstance(d, dict) and d.get("v") == CACHE_VERSION else None
    except Exception:
        return None


def _save_cache(session_id, data):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = os.path.join(CACHE_DIR, f"{session_id}.json.tmp")
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, os.path.join(CACHE_DIR, f"{session_id}.json"))
    except Exception:
        pass


def _is_real_prompt(rec):
    """A user record is a typed prompt unless it carries tool_result blocks."""
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                return False
        return True
    return False


BASE = {
    "prompts": 0,
    # Claude Code's own session cost, when the gateway reports one. The status
    # line sees it on stdin and the dashboard cannot, so it is persisted here
    # for the page to read back.
    "cost_reported": 0,
    "replies": 0,
    "tin": 0,  # uncached input
    "tcr": 0,  # cache read
    "tcw": 0,  # cache write
    "tout": 0,
    "ctx": 0,
    "last_out": 0,
}


def scan_transcript(path, session_id):
    """Deduplicated token/message totals for a session transcript.

    Reads only bytes appended since the last run (byte-offset cache) and skips
    any message id already counted, so each distinct message contributes once.
    """
    st = os.stat(path)
    acc = dict(BASE)

    offset = 0
    seen_msgs = []
    seen_users = []
    cached = _load_cache(session_id)
    if (
        cached
        and cached.get("path") == path
        and cached.get("inode") == st.st_ino
        and isinstance(cached.get("offset"), int)
        and 0 <= cached["offset"] <= st.st_size
    ):
        offset = cached["offset"]
        for k in acc:
            acc[k] = cached.get(k, 0)
        seen_msgs = list(cached.get("seen_msgs") or [])
        seen_users = list(cached.get("seen_users") or [])

    msg_set = set(seen_msgs)
    user_set = set(seen_users)

    with open(path, "rb") as f:
        f.seek(offset)
        pos = offset
        while True:
            raw = f.readline()
            if not raw or not raw.endswith(b"\n"):
                break  # trailing partial write -- leave it for the next run
            pos += len(raw)
            try:
                rec = json.loads(raw)
            except Exception:
                continue
            if not isinstance(rec, dict) or rec.get("isSidechain"):
                continue
            rtype = rec.get("type")

            if rtype == "user":
                uid = rec.get("uuid")
                if uid:
                    if uid in user_set:
                        continue
                    user_set.add(uid)
                    seen_users.append(uid)
                if _is_real_prompt(rec):
                    acc["prompts"] += 1

            elif rtype == "assistant":
                msg = rec.get("message") or {}
                mid = msg.get("id")
                # Each streaming snapshot repeats the same id and the same
                # usage; count the message once, on first sight.
                if mid:
                    if mid in msg_set:
                        continue
                    msg_set.add(mid)
                    seen_msgs.append(mid)

                acc["replies"] += 1
                u = msg.get("usage") or {}
                i = u.get("input_tokens") or 0
                o = u.get("output_tokens") or 0
                cc = u.get("cache_creation_input_tokens") or 0
                cr = u.get("cache_read_input_tokens") or 0
                acc["tin"] += i
                acc["tout"] += o
                acc["tcw"] += cc
                acc["tcr"] += cr
                acc["last_out"] = o
                # Context size as of this turn.
                acc["ctx"] = i + cc + cr

    _save_cache(
        session_id,
        {
            "v": CACHE_VERSION,
            "path": path,
            "inode": st.st_ino,
            "offset": pos,
            "size": st.st_size,
            "seen_msgs": seen_msgs[-WINDOW:],
            "seen_users": seen_users[-WINDOW:],
            **acc,
        },
    )
    return acc


# ------------------------------------------------------------------ main ---
def _remember_reported(session_id, usd):
    """Persist Claude Code's own cost figure so the dashboard can show it too."""
    if not session_id:
        return
    d = _load_cache(session_id)
    if not d:
        return
    d["cost_reported"] = usd
    _save_cache(session_id, d)


def compute_cost(payload, acc, model_name="", session_id=None):
    """Cost of this session, in USD.

    Order of preference:
      1. Claude Code's own figure, if non-zero (never true on this gateway).
      2. Explicit per-1M rates from the environment.
      3. Rates derived from the gateway's published model ratios.

    Returns None when nothing trustworthy is available -- better to show
    nothing than to invent a number.
    """
    reported = (payload.get("cost") or {}).get("total_cost_usd") or 0
    try:
        reported = float(reported)
    except Exception:
        reported = 0.0
    if reported > 0:
        _remember_reported(session_id, reported)
        return reported

    # (2) explicit rates win over anything derived
    if any(COST_RATES.values()):
        r = COST_RATES
        return (
            acc["tin"] / 1e6 * r["in"]
            + acc["tout"] / 1e6 * r["out"]
            + acc["tcr"] / 1e6 * r["cr"]
            + acc["tcw"] / 1e6 * r["cw"]
        )

    # (3) derive from the gateway's published ratios
    ratios = gateway_ratios(model_name)
    if not ratios:
        return None
    model_ratio, completion_ratio, group_ratio = ratios

    # new-api convention: quota = tokens * ratio, with QUOTA_PER_USD quota to
    # the dollar. Cache tokens bill at the input ratio -- the gateway publishes
    # no separate cache rate.
    prompt_tokens = acc["tin"] + acc["tcr"] + acc["tcw"]
    quota = (prompt_tokens * model_ratio) + (
        acc["tout"] * model_ratio * completion_ratio
    )
    return quota / QUOTA_PER_USD * group_ratio


def gateway_ratios(model_name):
    """(model_ratio, completion_ratio, group_ratio) for a model, or None."""
    pricing = _load_pricing()
    if not pricing or not model_name:
        return None
    for row in pricing.get("data") or []:
        if row.get("model_name") == model_name:
            mr = row.get("model_ratio")
            cr = row.get("completion_ratio")
            if not mr or not cr:
                return None
            gr = (pricing.get("group_ratio") or {}).get("default", 1) or 1
            return float(mr), float(cr), float(gr)
    return None


def _load_pricing():
    """Gateway pricing, cached on disk and refreshed at most once a day.

    A status line cannot afford a network round-trip on every render, so the
    common path is a local file read.
    """
    path = os.path.join(CACHE_DIR, "pricing.json")
    try:
        with open(path) as f:
            d = json.load(f)
        if time.time() - (d.get("_fetched") or 0) < PRICING_TTL:
            return d
    except Exception:
        pass

    base = (os.environ.get("ANTHROPIC_BASE_URL") or "").rstrip("/")
    if not base:
        try:
            with open(os.path.join(CLAUDE_DIR, "settings.json")) as f:
                base = (json.load(f).get("env") or {}).get(
                    "ANTHROPIC_BASE_URL", ""
                ).rstrip("/")
        except Exception:
            return None
    if not base:
        return None

    try:
        req = urllib.request.Request(
            base + "/api/pricing", headers={"User-Agent": "claude-statusline"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            d = json.loads(resp.read().decode("utf-8", "replace"))
        if isinstance(d, dict) and d.get("data"):
            d["_fetched"] = time.time()
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                tmp = path + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(d, f)
                os.replace(tmp, path)
            except Exception:
                pass
            return d
    except Exception:
        pass
    return None


def lifetime_total():
    """All-time token total across every session and model.

    Source is ~/.claude/stats-cache.json -- Claude Code's own accounting, which
    includes sidechain/subagent traffic that session transcripts undercount.
    It is rebuilt periodically rather than live, so the value can lag by a day
    or two. Returns (tokens, as_of_date_string).
    """
    try:
        with open(os.path.join(CLAUDE_DIR, "stats-cache.json")) as f:
            d = json.load(f)
        mu = d.get("modelUsage") or {}
        if not isinstance(mu, dict):
            return 0, None
        total = 0
        for v in mu.values():
            if not isinstance(v, dict):
                continue
            total += (
                (v.get("inputTokens") or 0)
                + (v.get("outputTokens") or 0)
                + (v.get("cacheReadInputTokens") or 0)
                + (v.get("cacheCreationInputTokens") or 0)
            )
        return total, d.get("lastComputedDate")
    except Exception:
        return 0, None


def render(payload):
    model = payload.get("model") or {}
    model_name = model.get("display_name") or model.get("id") or "claude"

    workspace = payload.get("workspace") or {}
    cwd = workspace.get("current_dir") or payload.get("cwd") or ""
    project = os.path.basename(cwd.rstrip("/")) if cwd else ""

    stats = None
    tpath = payload.get("transcript_path")
    sid = payload.get("session_id") or "default"
    if tpath and os.path.exists(tpath):
        try:
            stats = scan_transcript(tpath, sid)
        except Exception:
            stats = None

    parts = [f"{BOLD}{WHITE}{model_name}{RESET}"]
    if SHOW_PROJECT and project:
        parts.append(f"{DIM}{project}{RESET}")

    if stats and (stats["replies"] or stats["ctx"]):
        ctx = stats["ctx"]
        pct = ctx / CONTEXT_LIMIT * 100.0
        cum_in = stats["tin"] + stats["tcr"] + stats["tcw"]
        c = color_for(pct)

        parts.append(make_bar(pct))
        parts.append(f"{c}{BOLD}{pct:>3.0f}%{RESET}")
        parts.append(f"{CYAN}ctx {num(ctx)}{DIM}/{num(CONTEXT_LIMIT)}{RESET}")
        parts.append(f"{BLUE}↑ in {num(cum_in)}{RESET}")
        parts.append(f"{MAGENTA}↓ out {num(stats['tout'])}{RESET}")

        life, as_of = lifetime_total()
        if life:
            parts.append(f"{GREEN}Σ {human(life)}{RESET}")

        parts.append(f"{DIM}{stats['prompts'] + stats['replies']} msg{RESET}")

        cost = compute_cost(payload, stats, model.get("id") or model_name, sid)
        if cost is not None:
            parts.append(f"{MAGENTA}{fmt_cost(cost)}{RESET}")
    else:
        parts.append(make_bar(0))
        parts.append(f"{DIM}  0%{RESET}")
        parts.append(f"{DIM}no transcript yet{RESET}")

    return f" {SEP} ".join(parts)


def main():
    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}
    try:
        print(render(payload))
    except Exception:
        # Absolute fallback: never leave the status line blank or broken.
        print("\033[2mclaude\033[0m")


if __name__ == "__main__":
    main()
