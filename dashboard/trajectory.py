#!/usr/bin/env python3
"""Inspect the append-only session log, by source.

Everything the model sees lands in a session transcript: system prompt,
reasoning, tool calls and their results, subagent activity, and every context
injection. This reports that event stream grouped by source, then in order.

Usage:
    trajectory.py                 # the session you are in
    trajectory.py de2b7ace        # a specific session, by id or id-prefix
    trajectory.py --all           # every session transcript on disk
    trajectory.py --limit 100     # more events (default 30)
    trajectory.py --source think  # only one source

Accounting note: the transcript writes each assistant message ~2.5x as
streaming snapshots under one message.id. Those are collapsed here, because
the model sees one copy. Attachment, user, and system records do not
duplicate (verified: every uuid is distinct).

Sizes are estimated from character counts so sources are comparable. The
session's real billed usage is reported separately in the header and is not
estimated.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

HOME = Path.home()
# Claude Code lets you move its directory with CLAUDE_CONFIG_DIR, so honour it
# rather than assuming ~/.claude -- the alternative is a tool that silently
# reads nothing on a machine where that variable is set.
CLAUDE = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (HOME / ".claude"))
PROJECTS = CLAUDE / "projects"

ANSI_RE = re.compile(r"\033\[[0-9;]*m")
RESET, DIM, BOLD = "\033[0m", "\033[2m", "\033[1m"
GREEN, YELLOW, CYAN, MAGENTA, BLUE = (
    "\033[32m", "\033[33m", "\033[36m", "\033[35m", "\033[34m",
)

TOTAL_W = 92

# ---------------------------------------------------------------- settings ---
# Every knob here changes behaviour somewhere real. There is no catalogue of
# cosmetic toggles: a setting that nothing reads is a lie. The list is long
# because each group earns its place in code, not because the number is a
# target. `scope` says when a change lands:
#
#   live     the page picks it up on the next poll (some without even that)
#   open     read once when a session page is built, so it shapes a new load
#   restart  read once at launch, so it takes effect the next time you serve
#
# A few entries also declare how they reach the page without any bespoke code:
#
#   cssvar + unit   written to :root as a custom property, unit appended
#   attr            written to document.body.dataset under that name
#
# Everything else is handled explicitly in the page's applyCfg().
# Settings live next to this script, not at a fixed path under ~/.claude. A
# clone can sit anywhere -- ~/code/traj-claude, C:\tools\traj-claude -- and
# still keep its own config, and it never writes into the directory Claude Code
# owns beyond reading transcripts out of it.
CONFIG_PATH = Path(__file__).resolve().parent / "trajectory.config.json"
# serve() is threaded, so settings writes must be serialized.
CONFIG_LOCK = __import__("threading").Lock()

CONFIG_SPEC = [
    # ---------------------------------------------------------- appearance
    {"k": "theme", "g": "Appearance", "l": "Palette", "t": "enum",
     "d": "paper", "opts": ["paper", "ink"], "attr": "theme", "scope": "live",
     "h": "Paper is the light stock; ink is the dark one"},
    {"k": "density", "g": "Appearance", "l": "Density", "t": "enum",
     "d": "comfortable", "opts": ["comfortable", "compact"], "attr": "density",
     "scope": "live", "h": "Row padding across every list on the page"},
    {"k": "font_scale", "g": "Appearance", "l": "Interface scale (%)",
     "t": "int", "d": 100, "min": 85, "max": 140, "step": 1,
     "cssvar": "--fs", "scope": "live",
     "h": "Type and spacing together, as a percentage"},
    {"k": "radius", "g": "Appearance", "l": "Corner radius", "t": "int",
     "d": 4, "min": 0, "max": 16, "cssvar": "--radius", "unit": "px",
     "scope": "live", "h": "Panels, tiles, buttons and bars"},
    {"k": "brand", "g": "Appearance", "l": "Accent colour", "t": "color",
     "d": "#2F6F4E", "cssvar": "--brand", "scope": "live",
     "h": "The accent: pressed buttons, the live dot, the logo"},
    {"k": "brand_tint", "g": "Appearance", "l": "Accent wash (%)", "t": "int",
     "d": 13, "min": 0, "max": 45, "cssvar": "--tint", "unit": "%",
     "scope": "live",
     "h": "How strong the accent tint behind a pressed control is"},
    {"k": "hair", "g": "Appearance", "l": "Hairline strength (%)", "t": "int",
     "d": 100, "min": 0, "max": 200, "cssvar": "--hair-a",
     "scope": "live", "h": "Border and rule contrast; 0 removes every line"},
    {"k": "grain", "g": "Appearance", "l": "Paper grain", "t": "bool",
     "d": True, "attr": "grain", "scope": "live",
     "h": "The faint noise overlay, per the design system"},
    {"k": "serif_head", "g": "Appearance", "l": "Serif headings", "t": "bool",
     "d": True, "attr": "serif", "scope": "live",
     "h": "Instrument Serif for headings; off is all-sans"},
    {"k": "wide", "g": "Appearance", "l": "Full-bleed layout", "t": "bool",
     "d": True, "attr": "wide", "scope": "live",
     "h": "Off caps the page to a centred column"},
    {"k": "sticky_nav", "g": "Appearance", "l": "Sticky nav", "t": "bool",
     "d": True, "attr": "stickynav", "scope": "live",
     "h": "Keep the nav pinned while the stream scrolls"},
    {"k": "motion", "g": "Appearance", "l": "Arrival flash", "t": "bool",
     "d": True, "attr": "motion", "scope": "live",
     "h": "Tint rows that arrived after the page loaded"},
    {"k": "shadow", "g": "Appearance", "l": "Panel shadows", "t": "bool",
     "d": False, "attr": "shadow", "scope": "live",
     "h": "A soft lift under panels and dropdowns"},
    {"k": "uppercase_labels", "g": "Appearance", "l": "Uppercase labels",
     "t": "bool", "d": True, "attr": "uplat", "scope": "live",
     "h": "Small mono labels set in caps, or as written"},
    {"k": "row_pad", "g": "Appearance", "l": "Row padding", "t": "int",
     "d": 7, "min": 2, "max": 18, "cssvar": "--pad", "unit": "px",
     "scope": "live", "h": "Vertical padding on a record row"},
    {"k": "gap", "g": "Appearance", "l": "Gap between blocks", "t": "int",
     "d": 14, "min": 2, "max": 40, "cssvar": "--gap", "unit": "px",
     "scope": "live", "h": "Space between the panels on the page"},

    # ------------------------------------------------------ source colours
    {"k": "color_prompt", "g": "Source colours", "l": "User prompt",
     "t": "color", "d": "#B4642A", "cssvar": "--src-prompt", "scope": "live",
     "h": "Hue for user prompts"},
    {"k": "color_text", "g": "Source colours", "l": "Text", "t": "color",
     "d": "#8A4FBF", "cssvar": "--src-text", "scope": "live",
     "h": "Hue for model text output"},
    {"k": "color_reasoning", "g": "Source colours", "l": "Reasoning",
     "t": "color", "d": "#7A4FA8", "cssvar": "--src-reasoning",
     "scope": "live", "h": "Hue for reasoning records"},
    {"k": "color_toolcall", "g": "Source colours", "l": "Tool call",
     "t": "color", "d": "#2E6FB8", "cssvar": "--src-toolcall", "scope": "live",
     "h": "Hue for tool calls"},
    {"k": "color_toolresult", "g": "Source colours", "l": "Tool result",
     "t": "color", "d": "#2F7F5F", "cssvar": "--src-toolresult",
     "scope": "live", "h": "Hue for tool results"},
    {"k": "color_inject", "g": "Source colours", "l": "Injections",
     "t": "color", "d": "#8A6A16", "cssvar": "--src-inject", "scope": "live",
     "h": "Hue for context injections"},
    {"k": "color_system", "g": "Source colours", "l": "System", "t": "color",
     "d": "#4A7A8C", "cssvar": "--src-system", "scope": "live",
     "h": "Hue for system records"},
    {"k": "color_other", "g": "Source colours", "l": "Anything else",
     "t": "color", "d": "#6B6660", "cssvar": "--src-other", "scope": "live",
     "h": "Fallback hue for a source none of the above names"},
    {"k": "dot_size", "g": "Source colours", "l": "Legend dot size",
     "t": "int", "d": 7, "min": 4, "max": 16, "cssvar": "--dot", "unit": "px",
     "scope": "live", "h": "Dots in the legend, tiles and dropdown"},
    {"k": "source_order", "g": "Source colours", "l": "Order sources by",
     "t": "enum", "d": "tokens", "opts": ["tokens", "events", "name"],
     "scope": "live", "h": "Sort for the legend, tiles and share bar"},
    {"k": "show_share", "g": "Source colours", "l": "Show share bar",
     "t": "bool", "d": True, "scope": "live",
     "h": "The stacked token-share bar"},
    {"k": "show_legend", "g": "Source colours", "l": "Show legend",
     "t": "bool", "d": True, "scope": "live",
     "h": "The key under the share bar"},
    {"k": "show_tiles", "g": "Source colours", "l": "Show tiles",
     "t": "bool", "d": True, "scope": "live",
     "h": "Per-source cards with totals and a bar"},
    {"k": "show_spark", "g": "Source colours", "l": "Show volume chart",
     "t": "bool", "d": True, "scope": "live",
     "h": "Tokens per minute for the whole session"},
    {"k": "spark_buckets", "g": "Source colours", "l": "Chart buckets",
     "t": "int", "d": 48, "min": 8, "max": 240, "step": 4, "scope": "live",
     "h": "Columns in the tokens-per-minute chart"},
    {"k": "spark_height", "g": "Source colours", "l": "Chart height",
     "t": "int", "d": 46, "min": 18, "max": 160, "cssvar": "--spark",
     "unit": "px", "scope": "live", "h": "Height of that chart"},
    {"k": "tile_cols", "g": "Source colours", "l": "Tiles per row",
     "t": "int", "d": 5, "min": 1, "max": 8, "scope": "live",
     "h": "How many source tiles sit across one row"},
    {"k": "share_min_pct", "g": "Source colours", "l": "Merge below (%)",
     "t": "float", "d": 0.5, "min": 0, "max": 10, "step": 0.5,
     "scope": "live",
     "h": "Fold sources under this token share into one 'other' band"},
    {"k": "hide_sources", "g": "Source colours", "l": "Hidden sources",
     "t": "list", "d": [], "scope": "live",
     "h": "Sources removed from the share bar, tiles and stream entirely"},

    # -------------------------------------------------------------- timeline
    {"k": "waterfall_turns", "g": "Timeline", "l": "Turns drawn", "t": "int",
     "d": 12, "min": 1, "max": 400, "scope": "live",
     "h": "How many turns the duration waterfall draws"},
    {"k": "waterfall_segments", "g": "Timeline", "l": "Bars per turn",
     "t": "int", "d": 900, "min": 50, "max": 5000, "step": 50, "scope": "live",
     "h": "Bars drawn in a turn before it is truncated"},
    {"k": "wf_lane_height", "g": "Timeline", "l": "Lane height", "t": "int",
     "d": 11, "min": 4, "max": 28, "cssvar": "--wf-h", "unit": "px",
     "scope": "live", "h": "Thickness of each Input / Model / Tools lane"},
    {"k": "wf_min_pct", "g": "Timeline", "l": "Min bar width (%)",
     "t": "float", "d": 0.12, "min": 0.02, "max": 2, "step": 0.02,
     "scope": "live",
     "h": "Floor on a span's width, so a 20ms call is still visible"},
    {"k": "wf_label_w", "g": "Timeline", "l": "Lane label width",
     "t": "int", "d": 58, "min": 34, "max": 120, "cssvar": "--wf-lw",
     "unit": "px", "scope": "live", "h": "Gutter for the lane labels"},
    {"k": "wf_color_input", "g": "Timeline", "l": "Round-trip colour",
     "t": "color", "d": "#2E6FB8", "cssvar": "--wf-input", "scope": "live",
     "h": "Bars for time spent waiting on the model"},
    {"k": "wf_color_model", "g": "Timeline", "l": "Model colour",
     "t": "color", "d": "#8A4FBF", "cssvar": "--wf-model", "scope": "live",
     "h": "Bars for the model writing"},
    {"k": "wf_color_tool", "g": "Timeline", "l": "Tool colour", "t": "color",
     "d": "#2F7F5F", "cssvar": "--wf-tool", "scope": "live",
     "h": "Bars for a tool running"},
    {"k": "wf_ticks", "g": "Timeline", "l": "Axis ticks", "t": "int",
     "d": 5, "min": 2, "max": 11, "scope": "live",
     "h": "Labels along each turn's time axis"},
    {"k": "wf_labels", "g": "Timeline", "l": "Lane labels", "t": "bool",
     "d": True, "scope": "live", "h": "The Input / Model / Tools gutter"},
    {"k": "wf_header", "g": "Timeline", "l": "Turn header", "t": "bool",
     "d": True, "scope": "live",
     "h": "The per-turn badge with records, tokens and duration"},
    {"k": "wf_tooltip", "g": "Timeline", "l": "Hover tooltip", "t": "bool",
     "d": True, "scope": "live", "h": "Describe a bar on hover"},
    {"k": "wf_gap", "g": "Timeline", "l": "Gap between turns", "t": "int",
     "d": 10, "min": 0, "max": 40, "cssvar": "--wf-gap", "unit": "px",
     "scope": "live", "h": "Vertical space between two turns"},
    {"k": "stream_excerpt", "g": "Timeline", "l": "Row preview length",
     "t": "int", "d": 160, "min": 20, "max": 600, "step": 10, "scope": "live",
     "h": "Characters of a record shown in the event stream row"},

    # ------------------------------------------------------------------ flow
    {"k": "flow_steps", "g": "Flow", "l": "Steps for the newest turn",
     "t": "int", "d": 60, "min": 5, "max": 1000, "step": 5, "scope": "live",
     "h": "How much of the current turn the flow view expands"},
    {"k": "flow_step_cap", "g": "Flow", "l": "Steps per older turn",
     "t": "int", "d": 60, "min": 5, "max": 500, "step": 5, "scope": "live",
     "h": "Cap on steps rendered for turns above the newest"},
    {"k": "flow_budget", "g": "Flow", "l": "Step budget", "t": "int",
     "d": 160, "min": 20, "max": 2000, "step": 20, "scope": "live",
     "h": "Total steps on screen before the oldest turns are dropped"},
    {"k": "flow_nested", "g": "Flow", "l": "Nest results under calls",
     "t": "bool", "d": True, "scope": "live",
     "h": "Draw a tool result inside the call it answers"},
    {"k": "flow_clamp", "g": "Flow", "l": "Collapsed lines", "t": "int",
     "d": 2, "min": 1, "max": 20, "cssvar": "--clamp", "scope": "live",
     "h": "Lines shown before a collapsed step body is clipped"},
    {"k": "flow_json", "g": "Flow", "l": "Colour tool JSON", "t": "bool",
     "d": True, "scope": "live",
     "h": "Syntax-highlight a tool call's input"},
    {"k": "flow_meta", "g": "Flow", "l": "Show step meta", "t": "bool",
     "d": True, "scope": "live", "h": "Tokens and clock time on each step"},
    {"k": "flow_expand_last", "g": "Flow", "l": "Open the newest step",
     "t": "bool", "d": False, "scope": "live",
     "h": "Start with the last step of each turn expanded"},
    {"k": "flow_indent", "g": "Flow", "l": "Nesting indent", "t": "int",
     "d": 18, "min": 0, "max": 48, "cssvar": "--indent", "unit": "px",
     "scope": "live", "h": "Left step for a nested step"},

    # ----------------------------------------------------------------- table
    {"k": "table_rows", "g": "Table", "l": "Rows drawn", "t": "int",
     "d": 400, "min": 20, "max": 5000, "step": 20, "scope": "live",
     "h": "Rows in the table view before it stops"},
    {"k": "col_time", "g": "Table", "l": "Time column", "t": "bool",
     "d": True, "scope": "live", "h": "Clock time for each record"},
    {"k": "col_source", "g": "Table", "l": "Source column", "t": "bool",
     "d": True, "scope": "live", "h": "Which source the record came from"},
    {"k": "col_tokens", "g": "Table", "l": "Tokens column", "t": "bool",
     "d": True, "scope": "live", "h": "Estimated token count"},
    {"k": "col_text", "g": "Table", "l": "Text column", "t": "bool",
     "d": True, "scope": "live", "h": "The record's own content"},
    {"k": "table_full", "g": "Table", "l": "Full text in rows", "t": "bool",
     "d": False, "scope": "live",
     "h": "Off truncates the column so rows stay one line"},
    {"k": "table_zebra", "g": "Table", "l": "Striped rows", "t": "bool",
     "d": False, "attr": "zebra", "scope": "live",
     "h": "Alternate row shading"},
    {"k": "col_name", "g": "Table", "l": "Name column", "t": "bool",
     "d": True, "scope": "live", "h": "Tool or record name column"},
    {"k": "table_row_h", "g": "Table", "l": "Row height", "t": "int",
     "d": 26, "min": 16, "max": 52, "cssvar": "--trh", "unit": "px",
     "scope": "live", "h": "Height of a table row"},

    # --------------------------------------------------------------- filters
    {"k": "start_filter", "g": "Filters", "l": "Source on open", "t": "text",
     "d": "", "scope": "open",
     "h": "A source prefix to pre-select, e.g. tool call (blank = all)"},
    {"k": "hidden_sources", "g": "Filters", "l": "Open without",
     "t": "list", "d": [], "scope": "open",
     "h": "Source prefixes filtered out at page load"},
    {"k": "min_tokens", "g": "Filters", "l": "Min tokens", "t": "int",
     "d": 0, "min": 0, "max": 100000, "step": 50, "scope": "open",
     "h": "Open hiding events smaller than this"},
    {"k": "only_errors", "g": "Filters", "l": "Only failures", "t": "bool",
     "d": False, "scope": "open",
     "h": "Open showing only errors and failed tool results"},
    {"k": "only_inflight", "g": "Filters", "l": "Only the turn in flight",
     "t": "bool", "d": False, "scope": "open",
     "h": "Open showing just the newest turn"},
    {"k": "match_case", "g": "Filters", "l": "Case-sensitive search",
     "t": "bool", "d": False, "scope": "live",
     "h": "The search box in Tracking options"},
    {"k": "match_regex", "g": "Filters", "l": "Search is a regex",
     "t": "bool", "d": False, "scope": "live",
     "h": "Treat the search box as a regular expression"},
    {"k": "remember_filters", "g": "Filters", "l": "Remember filters",
     "t": "bool", "d": True, "scope": "live",
     "h": "Keep the current filters when you switch session"},

    # ------------------------------------------------------------------ live
    {"k": "live", "g": "Live", "l": "Follow the session", "t": "bool",
     "d": True, "scope": "live",
     "h": "Poll for records appended since the page loaded"},
    {"k": "poll_ms", "g": "Live", "l": "Poll every (ms)", "t": "int",
     "d": 2000, "min": 500, "max": 60000, "step": 250, "scope": "live",
     "h": "How often the page asks for new events while live"},
    {"k": "max_events", "g": "Live", "l": "Keep at most", "t": "int",
     "d": 20000, "min": 500, "max": 200000, "step": 500, "scope": "live",
     "h": "Oldest events dropped from the browser once past this"},
    {"k": "auto_follow", "g": "Live", "l": "Follow the tail", "t": "bool",
     "d": False, "scope": "live",
     "h": "Scroll to the newest event as it arrives"},

    # ------------------------------------------------------------ accounting
    {"k": "context_limit", "g": "Accounting", "l": "Context window (tok)",
     "t": "int", "d": 200000, "min": 1000, "max": 2000000, "step": 1000,
     "scope": "live",
     "h": "The window the context percentage is measured against"},
    {"k": "bar_cells", "g": "Accounting", "l": "Bar width (cells)",
     "t": "int", "d": 12, "min": 4, "max": 40, "scope": "live",
     "h": "Cells in the status strip's progress bar"},
    {"k": "cost_source", "g": "Accounting", "l": "Cost shown", "t": "enum",
     "d": "both", "opts": ["both", "reported", "derived"], "scope": "live",
     "h": "Claude Code's own figure, the gateway's ratios, or both"},
    {"k": "quota_per_usd", "g": "Accounting", "l": "Quota per USD",
     "t": "float", "d": 500000, "min": 1, "max": 1e9, "scope": "live",
     "h": "Gateway quota units to the dollar, for the derived figure"},
    {"k": "cost_decimals", "g": "Accounting", "l": "Cost decimals",
     "t": "int", "d": 2, "min": 0, "max": 6, "scope": "live",
     "h": "Precision on the dollar figures"},
    {"k": "show_billed", "g": "Accounting", "l": "Billed-by-API panel",
     "t": "bool", "d": True, "scope": "live",
     "h": "Exact token counts as the API reports them"},
    {"k": "show_lifetime", "g": "Accounting", "l": "Lifetime total",
     "t": "bool", "d": True, "scope": "live",
     "h": "All-time tokens across every session and model"},
    {"k": "bar_colors", "g": "Accounting", "l": "Colour the context bar",
     "t": "bool", "d": True, "scope": "live",
     "h": "Off draws it in a single neutral tone"},
    {"k": "ctx_warn_pct", "g": "Accounting", "l": "Warn above (%)",
     "t": "int", "d": 70, "min": 10, "max": 99, "scope": "live",
     "h": "Context share where the bar turns amber"},
    {"k": "ctx_danger_pct", "g": "Accounting", "l": "Danger above (%)",
     "t": "int", "d": 90, "min": 11, "max": 100, "scope": "live",
     "h": "Context share where the bar turns red"},
    {"k": "currency", "g": "Accounting", "l": "Currency symbol",
     "t": "text", "d": "$", "scope": "live",
     "h": "Prefix on every dollar figure"},

    # ---------------------------------------------------------- status strip
    {"k": "st_model", "g": "Status strip", "l": "Model", "t": "bool",
     "d": True, "scope": "live", "h": "Model name and project"},
    {"k": "st_ctx", "g": "Status strip", "l": "Context", "t": "bool",
     "d": True, "scope": "live", "h": "The bar and percentage"},
    {"k": "st_in", "g": "Status strip", "l": "Input", "t": "bool",
     "d": True, "scope": "live", "h": "Cumulative input tokens"},
    {"k": "st_out", "g": "Status strip", "l": "Output", "t": "bool",
     "d": True, "scope": "live", "h": "Cumulative output tokens"},
    {"k": "st_msgs", "g": "Status strip", "l": "Messages", "t": "bool",
     "d": True, "scope": "live", "h": "Prompts plus replies"},
    {"k": "st_cost", "g": "Status strip", "l": "Cost", "t": "bool",
     "d": True, "scope": "live", "h": "The dollar figures"},

    # ------------------------------------------------------- sessions rail
    {"k": "sess_limit", "g": "Sessions", "l": "Sessions listed", "t": "int",
     "d": 40, "min": 5, "max": 400, "step": 5, "scope": "live",
     "h": "How many recent sessions the rail shows"},
    {"k": "sess_width", "g": "Sessions", "l": "Rail width", "t": "int",
     "d": 240, "min": 160, "max": 420, "step": 4, "cssvar": "--rail",
     "unit": "px", "scope": "live", "h": "Width of the sessions column"},
    {"k": "sess_meta", "g": "Sessions", "l": "Session meta", "t": "bool",
     "d": True, "scope": "live",
     "h": "The project and date line under each session id"},
    {"k": "sess_folders", "g": "Sessions", "l": "Folder filter", "t": "bool",
     "d": True, "scope": "live", "h": "The folder dropdown above the list"},
    {"k": "sess_sort", "g": "Sessions", "l": "Sort by", "t": "enum",
     "d": "recent", "opts": ["recent", "size", "name"], "scope": "live",
     "h": "Order of the session rail"},
    {"k": "sess_tokens", "g": "Sessions", "l": "Transcript size",
     "t": "bool", "d": True, "scope": "live",
     "h": "How large each session's transcript is on disk"},

    # ------------------------------------------------------------------ nav
    {"k": "nav_view_timeline", "g": "Nav", "l": "Timeline button",
     "t": "bool", "d": True, "scope": "live",
     "h": "Show the Timeline view button"},
    {"k": "nav_view_flow", "g": "Nav", "l": "Flow button", "t": "bool",
     "d": True, "scope": "live", "h": "Show the Flow view button"},
    {"k": "nav_view_table", "g": "Nav", "l": "Table button", "t": "bool",
     "d": True, "scope": "live", "h": "Show the Table view button"},
    {"k": "nav_live", "g": "Nav", "l": "Live badge", "t": "bool",
     "d": True, "scope": "live", "h": "The live indicator in the nav"},
    {"k": "nav_stop", "g": "Nav", "l": "Stop button", "t": "bool",
     "d": True, "scope": "live", "h": "Shut the server down from the page"},
    {"k": "nav_brand", "g": "Nav", "l": "Logo", "t": "bool",
     "d": True, "scope": "live", "h": "The wordmark on the left"},
    {"k": "nav_src", "g": "Nav", "l": "Sources dropdown", "t": "bool",
     "d": True, "scope": "live", "h": "The source filter menu"},
    {"k": "nav_clock", "g": "Nav", "l": "Clock", "t": "bool",
     "d": True, "scope": "live", "h": "Current time on the right of the nav"},
    {"k": "nav_export", "g": "Nav", "l": "Export button", "t": "bool",
     "d": True, "scope": "live",
     "h": "The Extract page's way in; off hides it from the nav"},

    # ------------------------------------------------------- inspect & tips
    {"k": "tip_on", "g": "Inspect", "l": "Hover tooltip", "t": "bool",
     "d": True, "scope": "live", "h": "Describe a record on hover"},
    {"k": "tip_excerpt", "g": "Inspect", "l": "Tooltip preview length",
     "t": "int", "d": 110, "min": 0, "max": 400, "step": 10, "scope": "live",
     "h": "Characters of the record shown in the tooltip"},
    {"k": "inspect_pair", "g": "Inspect", "l": "Show the paired record",
     "t": "bool", "d": True, "scope": "live",
     "h": "A tool call and its result are shown together"},
    {"k": "inspect_raw", "g": "Inspect", "l": "Show the raw record",
     "t": "bool", "d": True, "scope": "live",
     "h": "The whole event object as JSON, at the bottom of the panel"},
    {"k": "inspect_width", "g": "Inspect", "l": "Panel width", "t": "int",
     "d": 600, "min": 320, "max": 1100, "step": 10, "cssvar": "--insp",
     "unit": "px", "scope": "live", "h": "Width of the detail sidebar"},
    {"k": "tip_delay", "g": "Inspect", "l": "Tooltip delay (ms)",
     "t": "int", "d": 120, "min": 0, "max": 1500, "step": 20, "scope": "live",
     "h": "Hover time before a tooltip appears"},
    {"k": "inspect_jump", "g": "Inspect", "l": "Jump to row", "t": "bool",
     "d": True, "scope": "live",
     "h": "The button that scrolls the stream to the record"},

    # ------------------------------------------------------------- keyboard
    {"k": "keys_on", "g": "Keyboard", "l": "Keyboard shortcuts",
     "t": "bool", "d": True, "scope": "live",
     "h": "Master switch for the keys below"},
    {"k": "key_views", "g": "Keyboard", "l": "View keys", "t": "text",
     "d": "1,2,3", "scope": "live",
     "h": "Comma-separated: timeline, flow, table"},
    {"k": "key_next", "g": "Keyboard", "l": "Next record", "t": "text",
     "d": "j", "scope": "live",
     "h": "Step the detail panel down the stream"},
    {"k": "key_prev", "g": "Keyboard", "l": "Previous record", "t": "text",
     "d": "k", "scope": "live", "h": "Step the detail panel up the stream"},
    {"k": "key_close", "g": "Keyboard", "l": "Close panels", "t": "text",
     "d": "Escape", "scope": "live",
     "h": "Closes the detail panel and settings"},

    # --------------------------------------------------------------- export
    {"k": "export_format", "g": "Export", "l": "Format", "t": "enum",
     "d": "json", "opts": ["json", "md", "csv"], "scope": "live",
     "h": "What the Export button writes"},
    {"k": "export_scope", "g": "Export", "l": "Scope", "t": "enum",
     "d": "view", "opts": ["view", "session", "turn"], "scope": "live",
     "h": "The filtered view, every record loaded, or the newest turn"},
    {"k": "export_text", "g": "Export", "l": "Include full text",
     "t": "bool", "d": True, "scope": "live",
     "h": "Off writes excerpts only, for a small file"},
    {"k": "export_meta", "g": "Export", "l": "Include totals", "t": "bool",
     "d": True, "scope": "live",
     "h": "Session totals and status at the top of the file"},
    {"k": "export_name", "g": "Export", "l": "File name", "t": "text",
     "d": "trajectory", "scope": "live",
     "h": "Base name, without extension"},
    {"k": "export_confirm", "g": "Export", "l": "Confirm before writing",
     "t": "bool", "d": False, "scope": "live",
     "h": "Ask before a large export starts"},

    # --------------------------------------------------------------- server
    {"k": "port", "g": "Server", "l": "Port", "t": "int",
     "d": 8788, "min": 1024, "max": 65535, "scope": "restart",
     "h": "The port serve binds on"},
    {"k": "bind", "g": "Server", "l": "Bind address", "t": "enum",
     "d": "127.0.0.1", "opts": ["127.0.0.1", "0.0.0.0"], "scope": "restart",
     "h": "0.0.0.0 exposes the session log to the local network"},
    {"k": "open_browser", "g": "Server", "l": "Open a browser on launch",
     "t": "bool", "d": False, "scope": "restart",
     "h": "Launch the default browser when serve starts"},
    {"k": "log_requests", "g": "Server", "l": "Log requests", "t": "bool",
     "d": False, "scope": "restart", "h": "Print every request to serve.log"},

    # ------------------------------------------------------------- advanced
    {"k": "default_view", "g": "Advanced", "l": "View on open", "t": "enum",
     "d": "timeline", "opts": ["timeline", "flow", "table"], "scope": "live",
     "h": "Which of the three views the page starts in"},
    {"k": "payload_cap", "g": "Advanced", "l": "Record text cap",
     "t": "int", "d": 4000, "min": 200, "max": 200000, "step": 200,
     "scope": "restart", "h": "Characters of a record's text sent to the page"},
    {"k": "event_cap", "g": "Advanced", "l": "Events per session",
     "t": "int", "d": 30000, "min": 100, "max": 500000, "step": 100,
     "scope": "restart", "h": "Newest records kept per session"},
    {"k": "debug_json", "g": "Advanced", "l": "Raw records everywhere",
     "t": "bool", "d": False, "scope": "live",
     "h": "Print each event object under its row in the flow and table"},
    {"k": "confirm_stop", "g": "Advanced", "l": "Confirm before stopping",
     "t": "bool", "d": True, "scope": "live",
     "h": "Ask before the Stop button shuts the server down"},
]

CONFIG_BY_KEY = {s["k"]: s for s in CONFIG_SPEC}
# Custom nav filter buttons. The only list-shaped setting: added and removed
# from the page, and the reason this file exists at all rather than a set of
# constants.
CHIP_CAP = 24


HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _coerce(spec, v):
    """A config value forced into its declared type and range, or its default.

    A hand-edited config file must never be able to break the page, so every
    read goes through here rather than trusting the file. A colour that fails
    to parse falls back to the default rather than reaching a stylesheet, and
    a list is bounded in both length and item size.
    """
    t = spec["t"]
    try:
        if t == "bool":
            return bool(v)
        if t == "int":
            n = int(v)
            return max(spec["min"], min(spec["max"], n))
        if t == "float":
            n = float(v)
            return max(float(spec["min"]), min(float(spec["max"]), n))
        if t == "enum":
            return v if v in spec["opts"] else spec["d"]
        if t == "color":
            s = str(v).strip()
            if not s.startswith("#"):
                s = "#" + s
            return s.upper() if HEX_RE.match(s) else spec["d"]
        if t == "list":
            return _clean_list(v)
        return str(v)[:200]
    except Exception:
        return spec["d"]


LIST_CAP = 64


def _clean_list(raw):
    """A bounded list of short strings -- a config file is not trusted."""
    out = []
    for x in raw if isinstance(raw, list) else []:
        s = str(x).strip()[:60]
        if s and s not in out:
            out.append(s)
        if len(out) >= LIST_CAP:
            break
    return out


def default_config():
    """Defaults, with list-valued entries copied so a caller cannot mutate
    the spec itself by editing the config it was handed."""
    cfg = {}
    for s in CONFIG_SPEC:
        cfg[s["k"]] = list(s["d"]) if isinstance(s["d"], list) else s["d"]
    cfg["chips"] = []
    return cfg


def _clean_chips(raw):
    """Custom filter chips, bounded and typed -- a config file is not trusted."""
    out = []
    for c in raw if isinstance(raw, list) else []:
        if not isinstance(c, dict):
            continue
        label = str(c.get("label") or "").strip()[:24]
        prefix = str(c.get("prefix") or "").strip()[:40]
        if label and prefix:
            out.append({"label": label, "prefix": prefix})
        if len(out) >= CHIP_CAP:
            break
    return out


def load_config():
    """The saved settings, over the defaults, with every value coerced."""
    cfg = default_config()
    try:
        with open(CONFIG_PATH) as f:
            raw = json.load(f)
    except Exception:
        return cfg
    if not isinstance(raw, dict):
        return cfg
    for k, spec in CONFIG_BY_KEY.items():
        if k in raw:
            cfg[k] = _coerce(spec, raw[k])
    cfg["chips"] = _clean_chips(raw.get("chips"))
    return cfg


def save_config(patch):
    """Merge a patch into the saved settings and return the full config.

    Unknown keys are ignored rather than stored: the file stays a config, not
    a scratchpad. Two things here are load-bearing:

    - the lock, because serve() is threaded and the page can have several
      writes in flight; without it two read-modify-writes interleave and one
      update is silently lost (seen happening: a chip added while a debounced
      number was still saving).
    - the atomic replace, so a poll reading the file mid-save sees one state
      or the other, never half of each.
    """
    with CONFIG_LOCK:
        cfg = load_config()
        if isinstance(patch, dict):
            for k, v in patch.items():
                if k == "chips":
                    cfg["chips"] = _clean_chips(v)
                elif k in CONFIG_BY_KEY:
                    cfg[k] = _coerce(CONFIG_BY_KEY[k], v)
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = CONFIG_PATH.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, CONFIG_PATH)
        except Exception:
            pass
        return cfg


def vis(s):
    return len(ANSI_RE.sub("", str(s)))


def clip(s, n):
    s = str(s)
    if vis(s) <= n:
        return s
    out, count, i = [], 0, 0
    while i < len(s) and count < n - 1:
        m = ANSI_RE.match(s, i)
        if m:
            out.append(m.group(0))
            i = m.end()
            continue
        out.append(s[i])
        count += 1
        i += 1
    return "".join(out) + RESET + "…"


def box(title, rows, lw=None):
    """Box-drawn table; label padded by VISIBLE width so colour cannot skew it."""
    rows = [(r[0], r[1], r[2] if len(r) > 2 else "") for r in rows] or [
        ("(none)", "", "")
    ]
    # Expand to fit the longest label -- a source name longer than the column
    # silently eats the padding and breaks the row.
    natural = max(vis(r[0]) for r in rows)
    lw = lw or natural
    lw = max(8, min(max(lw, natural), TOTAL_W - 31))
    vw = TOTAL_W - lw - 7
    print()
    print(f"  {BOLD}{CYAN}{title}{RESET}")
    print(f"  {DIM}┌{'─' * (lw + 2)}┬{'─' * (vw + 2)}┐{RESET}")
    for label, value, note in rows:
        v = str(value) + (("  " + DIM + str(note) + RESET) if note else "")
        line = clip(v, vw)
        pad = " " * max(0, lw - vis(label))
        vpad = " " * max(0, vw - vis(line))
        print(f"  {DIM}│{RESET} {label}{pad} {DIM}│{RESET} {line}{vpad} {DIM}│{RESET}")
    print(f"  {DIM}└{'─' * (lw + 2)}┴{'─' * (vw + 2)}┘{RESET}")


def human(n):
    n = int(n)
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}k"
    if n < 1_000_000_000:
        return f"{n / 1_000_000:.2f}M"
    return f"{n / 1_000_000_000:.2f}b"


def est(text):
    """Token estimate from characters -- the ~4 chars/token rule."""
    return max(0, len(str(text)) // 4)


def epoch_ms(ts):
    """Milliseconds since the epoch, or None.

    The waterfall needs real durations. Transcript timestamps carry
    milliseconds, so the whole-second view is enough to read but not enough
    to measure a tool call that took 400ms.
    """
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def hhmmss(ts):
    """Local wall-clock. Records are UTC; the file mtimes beside them are not,
    and two clocks in one view is worse than either."""
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.strftime("%H:%M:%S")
    except Exception:
        return "--:--:--"


def hhmm(ts):
    """Local HH:MM, for bucketing events into minutes."""
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.strftime("%H:%M")
    except Exception:
        return "--:--"


def text_of(content):
    """Flatten a message content field to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if not isinstance(b, dict):
                continue
            t = b.get("type")
            if t == "text":
                parts.append(b.get("text") or "")
            elif t == "thinking":
                parts.append(b.get("thinking") or "")
            elif t == "tool_use":
                parts.append(json.dumps(b.get("input") or {})[:200])
            elif t == "tool_result":
                parts.append(text_of(b.get("content")))
        return "\n".join(parts)
    return ""


# ------------------------------------------------------------- discovery ---
def all_transcripts():
    return sorted(
        PROJECTS.glob("*/*.jsonl"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )


def find_session(arg):
    """Resolve a session argument to a transcript path."""
    if arg:
        for p in PROJECTS.glob(f"*/{arg}*.jsonl"):
            return p
        for p in PROJECTS.glob("*/*.jsonl"):
            if arg in p.name:
                return p
        return None

    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if sid:
        for p in PROJECTS.glob(f"*/{sid}.jsonl"):
            return p

    # Fall back to the newest transcript for this working directory.
    slug = "-" + str(Path.cwd()).strip("/").replace("/", "-")
    cands = sorted(
        (PROJECTS / slug).glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ) if (PROJECTS / slug).is_dir() else []
    return cands[0] if cands else (all_transcripts() or [None])[0]


# ---------------------------------------------------------------- reading ---
def read_records(path):
    """Parse the JSONL, tolerating a half-written trailing line."""
    out = []
    try:
        with open(path, "rb") as f:
            for raw in f:
                if not raw.endswith(b"\n"):
                    break  # partial write -- leave it for next time
                try:
                    r = json.loads(raw)
                except Exception:
                    continue
                if isinstance(r, dict):
                    out.append(r)
    except Exception:
        pass
    return out


TOOL_LABEL = {"Bash": "Bash", "Read": "Read", "Edit": "Edit", "Write": "Write"}


def events_of(records):
    """Flatten records into (timestamp, source, tokens, excerpt, meta) events.

    Assistant records are deduped by message.id; the other types are already
    one record per event. `meta` carries what a flat tuple cannot: the tool
    name, call id and raw input on a call, and the id it answers on a result,
    so a view can pair a call with its result instead of guessing from order.
    """
    events = []
    billed = {"in": 0, "out": 0, "cr": 0, "cw": 0}
    billed_ids = set()
    # message.id -> block keys already emitted for it.
    emitted = {}

    for rec in records:
        rtype = rec.get("type")
        ts = rec.get("timestamp")

        if rtype == "assistant":
            msg = rec.get("message") or {}
            mid = msg.get("id")
            u = msg.get("usage") or {}
            # Every record for one message.id repeats the same usage object
            # verbatim (verified 243/243), so bill it once.
            if mid is None or mid not in billed_ids:
                billed_ids.add(mid)
                billed["in"] += u.get("input_tokens") or 0
                billed["out"] += u.get("output_tokens") or 0
                billed["cr"] += u.get("cache_read_input_tokens") or 0
                billed["cw"] += u.get("cache_creation_input_tokens") or 0

            # A message is NOT written once. Each record holds exactly one
            # content block: the thinking arrives in its own record, then the
            # finished text/tool_use in another -- all under one message.id.
            # Collapsing to a single record therefore loses every tool call,
            # so the blocks are unioned instead. A message that calls two
            # tools really does have two tool_use blocks (12 such ids here),
            # so tool_use is keyed by its own id rather than by content.
            keys = emitted.setdefault(mid, set())
            for b in msg.get("content") or []:
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                key = b.get("id") or (bt, b.get("thinking") or b.get("text") or "")
                if key in keys:
                    continue
                keys.add(key)

                if bt == "thinking":
                    events.append(
                        (ts, "reasoning", est(b.get("thinking")), b.get("thinking"), None)
                    )
                elif bt == "text":
                    events.append((ts, "text", est(b.get("text")), b.get("text"), None))
                elif bt == "tool_use":
                    raw = json.dumps(b.get("input") or {})
                    events.append((
                        ts, "tool call", est(raw), f"{b.get('name','?')} {raw[:150]}",
                        {"name": b.get("name") or "?", "id": b.get("id"), "input": raw},
                    ))

        elif rtype == "user":
            content = (rec.get("message") or {}).get("content")
            blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_result":
                    txt = text_of(b.get("content"))
                    # `is_error` is the harness's own verdict, so the dashboard
                    # can filter failures exactly instead of guessing at text.
                    events.append(
                        (ts, "tool result", est(txt), txt,
                         {"for": b.get("tool_use_id"), "error": bool(b.get("is_error"))})
                    )
                elif b.get("type") == "text":
                    txt = b.get("text") or ""
                    if txt.strip():
                        events.append((ts, "user prompt", est(txt), txt, None))

        elif rtype == "attachment":
            att = rec.get("attachment") or {}
            at = att.get("type") or "?"
            body = json.dumps({k: v for k, v in att.items() if k != "type"})
            events.append((ts, f"inject:{at}", est(body), body, {"type": at}))

        elif rtype == "system":
            sub = rec.get("subtype") or "system"
            body = rec.get("content")
            events.append(
                (ts, f"system:{sub}", est(json.dumps(body or "")), str(body or sub),
                 {"subtype": sub})
            )

        else:
            events.append((ts, "bookkeeping", 0, rtype or "?", None))

    return events, billed


# ----------------------------------------------------------------- render ---
BOOKKEEPING = {"bookkeeping"}


def source_color(src):
    if src.startswith("inject:"):
        return YELLOW
    if src.startswith("system:"):
        return CYAN
    if src == "reasoning":
        return MAGENTA
    if src == "tool call":
        return BLUE
    if src == "tool result":
        return GREEN
    if src == "user prompt":
        return RESET
    return DIM


def render_summary(events, billed, label):
    totals = {}
    order = []
    for _ts, src, tok, _ex, _meta in events:
        if src not in totals:
            totals[src] = [0, 0]
            order.append(src)
        totals[src][0] += 1
        totals[src][1] += tok

    model_total = sum(v[1] for s, v in totals.items() if s not in BOOKKEEPING)
    grand = sum(v[1] for v in totals.values()) or 1

    rows = []
    for src in sorted(order, key=lambda s: (s in BOOKKEEPING, -totals[s][1])):
        n, tok = totals[src]
        if src in BOOKKEEPING:
            continue
        pct = tok / grand * 100
        rows.append(
            (f"{source_color(src)}{src}{RESET}", f"{n:>5}", f"{human(tok):>7}  {pct:>4.1f}%")
        )
    rows.append((f"{DIM}model-visible total{RESET}", "", f"{human(model_total):>7}"))
    bk = [(s, totals[s]) for s in order if s in BOOKKEEPING]
    if bk:
        n = sum(v[0] for _s, v in bk)
        rows.append((f"{DIM}log bookkeeping (not sent){RESET}", "", f"{DIM}{n:>7}{RESET}"))
    box(f"By source  {DIM}({label}){RESET}", rows)

    print()
    print(
        f"  {DIM}sizes above are {RESET}{BOLD}estimated from characters{RESET}{DIM}; "
        f"what the API actually billed for this session:"
    )
    print(
        f"  in {human(billed['in'])} · cache-read {human(billed['cr'])} · "
        f"cache-write {human(billed['cw'])} · out {human(billed['out'])}{RESET}"
    )


def render_events(events, limit, filt):
    # Bookkeeping records have no timestamp and are never sent to the model, so
    # they are counted in the summary but kept out of the stream.
    visible = [e for e in events if e[1] not in BOOKKEEPING]
    shown = [e for e in visible if not filt or filt.lower() in e[1].lower()]
    tail = shown[-limit:]

    src_w = min(24, max([len(e[1]) for e in visible] or [8]))
    exc_w = max(20, TOTAL_W - src_w - 27)

    print()
    print(f"  {BOLD}{CYAN}Event stream{RESET}  {DIM}(last {len(tail)} of {len(shown)}){RESET}")
    print(f"  {DIM}┌──────────┬{'─' * (src_w + 2)}┬────────┬{'─' * (exc_w + 2)}┐{RESET}")
    for ts, src, tok, ex, _meta in tail:
        c = source_color(src)
        label = clip(f"{c}{src}{RESET}", src_w)
        lpad = " " * max(0, src_w - vis(label))
        size = f"{human(tok):>6}"
        exc = clip(" ".join(str(ex or "").split()), exc_w)
        epad = " " * max(0, exc_w - vis(exc))
        print(
            f"  {DIM}│{RESET} {hhmmss(ts)} {DIM}│{RESET} {label}{lpad} "
            f"{DIM}│{RESET} {size} {DIM}│{RESET} {exc}{epad} {DIM}│{RESET}"
        )
    print(f"  {DIM}└──────────┴{'─' * (src_w + 2)}┴────────┴{'─' * (exc_w + 2)}┘{RESET}")
    if len(shown) > len(tail):
        print(f"  {DIM}{len(shown) - len(tail)} earlier events — --limit N to see more{RESET}")


def short_proj(name, n=26):
    """Project dirs are path slugs; show the tail, marked when truncated."""
    s = name.lstrip("-")
    return s if len(s) <= n else "…" + s[-(n - 1):]


def render_all():
    rows = []
    for p in all_transcripts()[:40]:
        try:
            st = p.stat()
            mt = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            rows.append(
                (p.stem[:8], short_proj(p.parent.name), f"{human(st.st_size):>7}  {mt}")
            )
        except Exception:
            continue
    box("Sessions on disk", rows, lw=10)
    print()
    print(f"  {DIM}trajectory.py <id-prefix> to inspect one{RESET}")


def status_block(path, records):
    """The status line's figures, for the dashboard header.

    This deliberately reuses statusline-command.py rather than recomputing
    them: that file owns the dedupe-by-message.id accounting, the byte-offset
    cache and the cost derivation, and two copies of those would drift. Any
    failure just drops the block -- the dashboard is still useful without it.

    Two places are searched, in order: the copy the installer put in the Claude
    Code directory, and the one sitting next to this checkout. That way the
    block appears whether or not the status line was installed.
    """
    import importlib.util

    here = Path(__file__).resolve().parent
    candidates = [CLAUDE / "statusline-command.py",
                  here.parent / "statusline" / "statusline-command.py"]
    sl = None
    for cand in candidates:
        if not cand.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("claude_statusline", cand)
            sl = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sl)
            break
        except Exception:
            sl = None
    if sl is None:
        return None

    try:
        model = cwd = ""
        for r in reversed(records):
            if not model and r.get("type") == "assistant":
                model = ((r.get("message") or {}).get("model")) or ""
            if not cwd:
                cwd = r.get("cwd") or ""
            if model and cwd:
                break

        acc = sl.scan_transcript(str(path), path.stem)
        limit = sl.CONTEXT_LIMIT
        ctx = acc.get("ctx") or 0
        # Two costs, and they disagree by ~2.4x: Claude Code's own figure (which
        # it computes itself -- the gateway reports nothing) and our derivation
        # from the gateway's published ratios. Show Claude Code's as the cost,
        # because that is the number the user sees in the terminal, and keep the
        # derived one alongside it rather than hiding the disagreement.
        reported = float(acc.get("cost_reported") or 0)
        derived = sl.compute_cost({}, acc, model)
        cost = reported if reported > 0 else derived
        # The derived figure is (quota units / quota-per-USD), so ship the
        # numerator. The dashboard's quota knob can then re-price it in the
        # browser instead of the number being frozen at whatever this process
        # happened to read from the environment.
        quota = None
        try:
            ratios = sl.gateway_ratios(model)
            if ratios:
                mr, cr, gr = ratios
                prompt = acc["tin"] + acc["tcr"] + acc["tcw"]
                quota = ((prompt * mr) + (acc["tout"] * mr * cr)) * gr
        except Exception:
            quota = None
        life, as_of = sl.lifetime_total()
        return {
            "model": model,
            "project": os.path.basename(cwd.rstrip("/")) if cwd else "",
            "cwd": cwd,
            "ctx": ctx,
            "window": limit,
            "pct": (ctx / limit * 100.0) if limit else 0.0,
            "in": acc["tin"] + acc["tcr"] + acc["tcw"],
            "out": acc["tout"],
            "cache_read": acc["tcr"],
            "cache_write": acc["tcw"],
            "msgs": acc["prompts"] + acc["replies"],
            "prompts": acc["prompts"],
            "replies": acc["replies"],
            "lifetime": life,
            "lifetime_as_of": as_of,
            "cost": cost,
            "cost_source": "claude-code" if reported > 0 else "gateway-ratios",
            "cost_derived": derived,
            "cost_quota": quota,
        }
    except Exception:
        return None


# ------------------------------------------------------------- dashboards ---
def build_state(session_arg=None, after=0):
    """Everything the dashboard needs, as plain JSON-able data.

    `after` returns only events past that index, so a live page can append
    without re-sending the whole session every couple of seconds.
    """
    current = (os.environ.get("CLAUDE_CODE_SESSION_ID") or "")[:8]
    sessions = []
    for p in all_transcripts()[:80]:
        try:
            st = p.stat()
            sessions.append({
                "id": p.stem[:8],
                "folder": p.parent.name,
                "project": short_proj(p.parent.name, 34),
                "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%m-%d %H:%M"),
                "size": human(st.st_size),
                "size_bytes": st.st_size,
                "current": p.stem[:8] == current,
            })
        except Exception:
            continue

    path = find_session(session_arg)
    if not path or not Path(path).exists():
        return {"sessions": sessions, "session": "", "records": 0, "summary": [],
                "billed": {}, "events": [], "total": 0,
                "config": load_config(), "config_spec": CONFIG_SPEC, "live": True,
                "config_path": str(CONFIG_PATH),
                "script_path": str(Path(__file__).resolve())}

    records = read_records(path)
    events, billed = events_of(records)
    visible = [e for e in events if e[1] not in BOOKKEEPING]

    totals = {}
    for _ts, src, tok, _ex, _meta in visible:
        d = totals.setdefault(src, [0, 0])
        d[0] += 1
        d[1] += tok
    grand = sum(v[1] for v in totals.values()) or 1
    summary = [
        {"source": s, "events": v[0], "tokens": v[1], "pct": v[1] / grand * 100.0}
        for s, v in sorted(totals.items(), key=lambda kv: -kv[1][1])
    ]

    # Volume per minute, for the sparkline. Bounded so a marathon session
    # cannot grow the payload without limit.
    buckets = {}
    for ts, _src, tok, _ex, _meta in visible:
        key = hhmm(ts)
        b = buckets.setdefault(key, [0, 0])
        b[0] += 1
        b[1] += tok
    series = [
        {"t": k, "events": v[0], "tokens": v[1]} for k, v in sorted(buckets.items())
    ][-180:]

    # Full text is only shipped for recent events. A long session can hold
    # thousands of events at up to 4k chars each, and the older ones are
    # rarely expanded -- the excerpt is enough to show, and the dashboard
    # labels the difference rather than pretending it has the whole thing.
    cutoff = max(0, len(visible) - 1500)

    out = []
    for idx, (ts, src, tok, ex, meta) in enumerate(visible[after:], start=after):
        text = " ".join(str(ex or "").split())
        meta = meta or {}
        # A tool call's own text is its input JSON -- the name rides in `name`
        # so the view can render it as a badge and colour the JSON separately.
        if src == "tool call" and meta.get("input"):
            full = meta["input"][:4000]
        else:
            full = text[:4000] if idx >= cutoff else ""
        out.append({
            "t": hhmmss(ts),
            "ts": epoch_ms(ts),
            "source": src,
            "tokens": tok,
            "excerpt": (meta.get("name") + " " + text if src == "tool call"
                        else text)[:240],
            "text": full,
            "name": meta.get("name"),
            "call": meta.get("id"),
            "for": meta.get("for"),
            "error": bool(meta.get("error")),
        })

    return {
        "sessions": sessions,
        "session": path.stem[:8],
        "records": len(records),
        "summary": summary,
        "billed": billed,
        "status": status_block(path, records),
        "events": out,
        "series": series,
        "total": len(visible),
        "config": load_config(),
        "config_spec": CONFIG_SPEC,
        "live": True,
        # Shipped so the page can name the real file rather than assume the
        # author's ~/.claude/scripts layout -- the path is a setting too.
        "config_path": str(CONFIG_PATH),
        "script_path": str(Path(__file__).resolve()),
    }


def open_in_browser(url):
    """Best-effort: a headless box has no opener, and that is not an error."""
    import subprocess
    for cmd in ("xdg-open", "open", "sensible-browser"):
        try:
            subprocess.Popen(
                [cmd, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            continue
    return False


def write_html(session_arg, out_path=None, live=False):
    import trajectory_dashboard as dash

    state = build_state(session_arg)
    state["live"] = live
    html = dash.render(state, live=live)
    out = (
        Path(out_path)
        if out_path
        else CLAUDE / "trajectory" / f"{state['session'] or 'index'}.html"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def _probe(port, timeout=1.0):
    """True if OUR server already answers on this port.

    The check is for a key from the settings schema rather than a bare 200:
    something else listening on 8788 must not be reported as the dashboard,
    and must not be silently reused either.
    """
    import urllib.request
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/config", timeout=timeout
        ) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        return isinstance(d, dict) and "waterfall_turns" in d
    except Exception:
        return False


def spawn_serve(port):
    """Start the dashboard detached, so the caller can return.

    /trajectory runs inside a shell that has to give the prompt back, and
    serve_forever() never returns. The child gets its own session so it
    survives the shell that started it, and its output goes to a log instead
    of to a terminal nobody is watching.
    """
    import subprocess
    import time

    if _probe(port):
        return "already", f"http://127.0.0.1:{port}/"
    log = CLAUDE / "trajectory" / "serve.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as fh:
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "serve", "--port", str(port)],
            stdout=fh, stderr=fh, stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    for _ in range(40):          # up to ~4s: the first render reads a transcript
        time.sleep(0.1)
        if _probe(port, timeout=0.4):
            return "started", f"http://127.0.0.1:{port}/"
    return "failed", str(log)


def serve(port=8765, session_arg=None):
    """Local-only server. Binds 127.0.0.1 so the log never leaves the box."""
    import threading

    import trajectory_dashboard as dash
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlparse, parse_qs

    def page_html():
        """Rendered per request, not cached: a reload has to pick up settings
        saved from another tab. The template substitution is cheap, and `/` is
        fetched once per page load rather than on every poll."""
        return dash.render(build_state(session_arg), live=True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass  # quiet: the default logger writes to stderr every request

        def _send(self, code, body, ctype):
            b = body.encode("utf-8") if isinstance(body, str) else body
            try:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(b)
            except Exception:
                pass  # client hung up mid-write

        def _local(self):
            """Only this machine may stop the server.

            The bind is already loopback-only, but any page the browser is
            showing can reach loopback. Requiring a non-simple POST header
            means a cross-origin caller needs a preflight, which this server
            never approves, so a drive-by fetch cannot kill the dashboard.
            """
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost", "[::1]")

        def do_POST(self):
            u = urlparse(self.path)
            if u.path not in ("/api/shutdown", "/api/config"):
                self._send(404, "not found", "text/plain; charset=utf-8")
                return
            # Same guard as shutdown: a non-simple header forces a preflight
            # that this server never approves, so a page you merely visited
            # cannot write your settings.
            if not self._local() or self.headers.get("X-Trajectory") != "stop":
                self._send(403, "forbidden", "text/plain; charset=utf-8")
                return
            if u.path == "/api/config":
                try:
                    n = max(0, int(self.headers.get("Content-Length") or 0))
                    if n > 65536:
                        self._send(413, "too large", "text/plain; charset=utf-8")
                        return
                    patch = json.loads(self.rfile.read(n) or b"{}")
                except Exception:
                    self._send(400, json.dumps({"error": "bad json"}),
                               "application/json")
                    return
                self._send(200, json.dumps(save_config(patch)),
                           "application/json; charset=utf-8")
                return
            self._send(200, json.dumps({"stopping": True}), "application/json")
            # Answer first, then wind down: shutdown() waits for the serve loop
            # to exit, and that loop cannot exit while this thread is mid-reply.
            threading.Thread(target=srv.shutdown, daemon=True).start()

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path == "/api/state":
                sid = (q.get("session") or [None])[0]
                try:
                    after = max(0, int((q.get("after") or ["0"])[0]))
                except Exception:
                    after = 0
                try:
                    self._send(
                        200,
                        json.dumps(build_state(sid, after), ensure_ascii=False),
                        "application/json; charset=utf-8",
                    )
                except Exception as e:
                    self._send(500, json.dumps({"error": str(e)}), "application/json")
            elif u.path == "/api/config":
                self._send(200, json.dumps(load_config()), "application/json")
            elif u.path in ("/", "/index.html"):
                self._send(200, page_html(), "text/html; charset=utf-8")
            else:
                self._send(404, "not found", "text/plain; charset=utf-8")

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"\n  {BOLD}trajectory dashboard{RESET}  {CYAN}{url}{RESET}")
    print(f"  {DIM}live · ctrl-c to stop, or the Stop button in the page{RESET}")
    print(f"  {DIM}restart: python3 {os.path.abspath(__file__)} serve --port {port}{RESET}\n")
    if load_config().get("open_browser"):
        open_in_browser(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print(f"\n  {DIM}stopped{RESET}\n")


def main():
    args = sys.argv[1:]
    limit, filt, arg = 30, None, None
    # No verb means the dashboard: a live page beats a wall of text, and the
    # page carries the text report's numbers anyway. `--text` asks for the
    # terminal rendering instead.
    mode, port, out = "open", int(load_config().get("port") or 8765), None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--all":
            render_all()
            return
        elif a == "--limit" and i + 1 < len(args):
            try:
                limit = max(1, int(args[i + 1]))
            except Exception:
                pass
            i += 1
        elif a == "--source" and i + 1 < len(args):
            filt = args[i + 1]
            i += 1
        elif a in ("serve", "--serve", "--dashboard", "--html"):
            mode = "serve" if a in ("serve", "--serve", "--dashboard") else "html"
        elif a in ("open", "dashboard-bg", "--open"):
            mode = "open"
        elif a in ("--text", "--terminal", "text"):
            mode = "text"
        elif a == "--port" and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except Exception:
                pass
            i += 1
        elif a in ("--out", "-o") and i + 1 < len(args):
            out = args[i + 1]
            i += 1
        elif not a.startswith("-"):
            arg = a
        i += 1

    if mode == "open":
        cfg = load_config()
        state, url = spawn_serve(port)
        if state == "already":
            print(f"\n  {BOLD}trajectory dashboard{RESET}  {DIM}already running{RESET}")
        elif state == "started":
            print(f"\n  {BOLD}trajectory dashboard{RESET}  {GREEN}started{RESET}")
        else:
            print(f"\n  {YELLOW}could not start the dashboard{RESET}")
            print(f"  {DIM}python3 {os.path.abspath(__file__)} serve --port {port}{RESET}")
            print(f"  {DIM}log: {url}{RESET}\n")
            return
        print(f"  {CYAN}{url}{RESET}")
        print(f"  {DIM}stop it from the page, or: pkill -x -f "
              f"\"{sys.executable} {os.path.abspath(__file__)} serve --port {port}\"{RESET}\n")
        if cfg.get("open_browser"):
            open_in_browser(url)
        return

    if mode == "serve":
        serve(port, arg)
        return

    if mode == "html":
        try:
            dest = write_html(arg, out)
        except ImportError as e:
            print(f"\n  {YELLOW}html mode needs trajectory_dashboard.py{RESET} {DIM}{e}{RESET}\n")
            return
        print(f"\n  {BOLD}trajectory{RESET}  {DIM}static snapshot{RESET}")
        print(f"  {GREEN}{dest}{RESET}")
        print(f"  {DIM}static file -- no live updates; `serve` for that{RESET}\n")
        return

    path = find_session(arg)
    if not path or not Path(path).exists():
        print(f"\n  {YELLOW}no transcript found{RESET} {DIM}{arg or ''}{RESET}")
        print(f"  {DIM}try: trajectory.py --all{RESET}\n")
        return

    records = read_records(path)
    events, billed = events_of(records)
    sid = path.stem[:8]
    print()
    print(f"  {BOLD}SESSION TRAJECTORY{RESET}  {DIM}{sid}{RESET}  {DIM}{path.parent.name}{RESET}")
    render_summary(events, billed, f"{sid} · {len(records)} log records")
    render_events(events, limit, filt)
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never leave the terminal broken
        print(f"\n  trajectory: {e}\n", file=sys.stderr)
        sys.exit(0)
