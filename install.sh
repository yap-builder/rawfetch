#!/usr/bin/env bash
# rawfetch installer — choose which sources to install.
#
# YouTube captions and web articles are always included (small, pure Python).
# Reddit is optional: it needs a real browser engine (Playwright WebKit, ~300 MB).
#
#   ./install.sh               ask (interactive), or core only when not run from a terminal
#   ./install.sh --reddit      core + Reddit, no questions (for AI agents and scripts)
#   ./install.sh --no-reddit   core only, no questions
#   ./install.sh --venv DIR    install into DIR instead of ./.venv
#
# No sudo, nothing installed system-wide. Safe to re-run: it upgrades in place.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
REDDIT="ask"

while [ $# -gt 0 ]; do
  case "$1" in
    --reddit) REDDIT="yes" ;;
    --no-reddit) REDDIT="no" ;;
    --venv) shift; VENV="${1:?--venv needs a directory}" ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "install.sh: unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done

say() { printf '%s\n' "$*"; }

# --- Python 3.9+ -------------------------------------------------------------------------
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1 &&
     "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PY="$cand"; break
  fi
done
if [ -z "$PY" ]; then
  say "rawfetch needs Python 3.9 or newer, and none was found on PATH." >&2
  say "Install Python from https://www.python.org/downloads/ and run ./install.sh again." >&2
  exit 1
fi

# --- choose ------------------------------------------------------------------------------
if [ "$REDDIT" = "ask" ]; then
  if [ -t 0 ]; then
    say ""
    say "rawfetch installer"
    say ""
    say "  Always included:"
    say "    - YouTube captions"
    say "    - Web articles"
    say ""
    say "  Optional:"
    say "    - Reddit posts with their top comments, and post lists (search, top of a"
    say "      subreddit). Downloads a browser engine, about 300 MB."
    say ""
    printf "  Install Reddit support? [y/N] "
    read -r answer || answer=""
    case "$answer" in [yY]*) REDDIT="yes" ;; *) REDDIT="no" ;; esac
  else
    REDDIT="no"
    say "Not running in a terminal and no --reddit/--no-reddit given: installing core only."
  fi
fi

# --- install -----------------------------------------------------------------------------
say ""
case "$VENV" in /*) ;; *) VENV="$PWD/$VENV" ;; esac  # absolute, so the printed paths work
say "Installing into $VENV"
if [ ! -x "$VENV/bin/python" ] && ! "$PY" -m venv "$VENV"; then
  say "Could not create a virtual environment. On Debian/Ubuntu install it with:" >&2
  say "  sudo apt install python3-venv     then run ./install.sh again" >&2
  exit 1
fi
"$VENV/bin/python" -m pip install --quiet --upgrade pip
cd "$ROOT"  # ".[reddit]" from inside the repo: an absolute path with spaces + [extras] confuses pip
if [ "$REDDIT" = "yes" ]; then
  "$VENV/bin/python" -m pip install --quiet --upgrade ".[reddit]"
  say "Downloading the WebKit browser engine (one time, ~300 MB)..."
  "$VENV/bin/python" -m playwright install webkit
else
  "$VENV/bin/python" -m pip install --quiet --upgrade .
fi

# --- verify ------------------------------------------------------------------------------
"$VENV/bin/rawfetch" --version
if [ "$REDDIT" = "yes" ]; then
  "$VENV/bin/python" -c "import playwright" && say "Reddit support: installed"
else
  say "Reddit support: not installed (run ./install.sh --reddit to add it later)"
fi

say ""
say "Done. Run it as:"
say "  $VENV/bin/rawfetch <url>"
say "To type just 'rawfetch', add this line to your shell profile:"
say "  export PATH=\"$VENV/bin:\$PATH\""
