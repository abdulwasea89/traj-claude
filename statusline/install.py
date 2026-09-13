#!/usr/bin/env python3
"""Install the Claude Code status line.

Copies statusline-command.py into your Claude Code directory and points
`statusLine` at it in settings.json. Run it, restart Claude Code, done.

    python3 install.py              # install, or re-install after an update
    python3 install.py --dry-run    # show what would change, touch nothing
    python3 install.py --uninstall  # remove the statusLine entry again
    python3 install.py --python /usr/bin/python3.12

Works on Linux, macOS, and Windows. Standard library only, Python 3.8+.

On settings.json
----------------
This edits a file Claude Code owns, so it is careful in three specific ways:

  * it backs the file up first, next to the original, before writing anything
  * it only ever sets or removes the single `statusLine` key -- your `env`
    block, permissions, hooks and everything else are read and written back
    untouched
  * it never prints the contents of `env`, because for many people that is
    where a plaintext API token lives

If settings.json is not valid JSON, this refuses to touch it rather than
guessing. A broken settings file is a worse problem than a missing status line.
"""

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "statusline-command.py"
SCRIPT_NAME = "statusline-command.py"
PYTHON_OVERRIDE = None   # set by --python


def claude_dir():
    """Claude Code's directory. CLAUDE_CONFIG_DIR wins if it is set."""
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(override) if override else Path.home() / ".claude"


def python_command():
    """The interpreter to put in settings.json.

    sys.executable is the Python running this script, which is the one the user
    has actually been using. It is an absolute path, so it keeps working when
    the shell's PATH does not have `python` on it -- common on Windows, and the
    reason a bare `python3` here would be a bug.
    """
    if PYTHON_OVERRIDE:
        return PYTHON_OVERRIDE
    return sys.executable or "python"


def quote(path):
    """Quote for a shell command line. Double quotes work in sh and in cmd."""
    return '"{}"'.format(path)


def load_settings(path):
    """Return (settings, error). Never raises: the caller decides what to do."""
    if not path.exists():
        return {}, None
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return None, "cannot read {}: {}".format(path, e)
    if not text.strip():
        return {}, None
    try:
        data = json.loads(text)
    except ValueError as e:
        return None, "{} is not valid JSON: {}".format(path, e)
    if not isinstance(data, dict):
        return None, "{} does not contain a JSON object".format(path)
    return data, None


def save_settings(path, data):
    """Write settings.json, with a timestamped backup and an atomic replace."""
    backup = None
    if path.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(path.name + ".bak-" + stamp)
        shutil.copy2(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
    return backup


def describe(entry):
    if not entry:
        return "(not set)"
    if isinstance(entry, dict):
        return entry.get("command", json.dumps(entry))
    return str(entry)


def install(args):
    cdir = claude_dir()
    settings_path = cdir / "settings.json"
    dest = cdir / SCRIPT_NAME

    if not SOURCE.is_file():
        print("! cannot find {} -- run this from the statusline directory"
              .format(SOURCE))
        return 1

    settings, err = load_settings(settings_path)
    if err:
        print("! " + err)
        print("  Refusing to write. Fix or move that file, then run this again.")
        return 1

    before = settings.get("statusLine")
    command = "{} {}".format(quote(python_command()), quote(dest))
    entry = {"type": "command", "command": command, "padding": 0}

    print("Claude Code directory  {}".format(cdir))
    print("script installs to     {}".format(dest))
    print("settings file          {}".format(settings_path))
    print("statusLine currently   {}".format(describe(before)))
    print("statusLine will be     {}".format(command))

    if args.dry_run:
        print("\n--dry-run: nothing was written.")
        return 0

    try:
        cdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE, dest)
    except OSError as e:
        print("! could not copy the script: {}".format(e))
        return 1
    print("\ncopied -> {}".format(dest))

    settings["statusLine"] = entry
    try:
        backup = save_settings(settings_path, settings)
    except OSError as e:
        print("! could not write settings.json: {}".format(e))
        return 1
    if backup:
        print("backed up -> {}".format(backup))
    print("updated  -> {}".format(settings_path))

    print("\nDone. Restart Claude Code and the bar appears at the bottom.")
    print("If nothing shows up, run:  {} {}".format(
        quote(python_command()), quote(HERE / "statusline-command.py")))
    return 0


def uninstall(args):
    cdir = claude_dir()
    settings_path = cdir / "settings.json"
    settings, err = load_settings(settings_path)
    if err:
        print("! " + err)
        return 1
    if "statusLine" not in settings:
        print("Nothing to do: no statusLine entry in {}".format(settings_path))
        return 0
    print("removing statusLine: {}".format(describe(settings.get("statusLine"))))
    if args.dry_run:
        print("\n--dry-run: nothing was written.")
        return 0
    del settings["statusLine"]
    backup = save_settings(settings_path, settings)
    if backup:
        print("backed up -> {}".format(backup))
    print("updated  -> {}".format(settings_path))
    print("\nThe copy at {} was left in place; delete it if you want."
          .format(cdir / SCRIPT_NAME))
    return 0


def main():
    global PYTHON_OVERRIDE
    ap = argparse.ArgumentParser(
        description="Install the Claude Code status line.")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would change, write nothing")
    ap.add_argument("--uninstall", action="store_true",
                    help="remove the statusLine entry from settings.json")
    ap.add_argument("--python", metavar="PATH",
                    help="interpreter to use in the status line command")
    args = ap.parse_args()
    PYTHON_OVERRIDE = args.python
    return uninstall(args) if args.uninstall else install(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
