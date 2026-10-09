#!/usr/bin/env bash
# open-terminal.sh — run a command in a new terminal window. Detection only.
#
# Extracted from open-diff-review.sh when the lazygit diff-review feature was
# removed. The feature was judged pointless in practice; its OS and terminal
# detection was not, and `start-parallel-cycles.sh` had already grown a second,
# worse copy of it — no iTerm path, no per-emulator handling on Linux. One copy,
# used twice, is the point of this file.
#
# Knows nothing about lazygit, cycles, or git. It opens a window and runs a
# string in it.
#
# Usage:
#   open-terminal.sh [--tab] --cwd DIR [--title TEXT] -- <command string>
#   open-terminal.sh --cwd ~/dev/app --title "cycle #419" -- 'claude "/cycle 419"'
#
# --tab asks for a tab in the current window rather than a new window. Supported
# on Ghostty (>=1.3, via its AppleScript dictionary) and on Windows Terminal;
# anywhere else it silently falls back to a window, because a window is a fine
# outcome and a caller that wanted a tab still got its command running.
#
# Platforms, and the shell each runs the command under:
#   macOS    Ghostty / iTerm / WezTerm / kitty, else Terminal.app — under zsh,
#            the default login shell since Catalina, not bash.
#   Windows  Ghostty if ever built for it, else Windows Terminal, else Git
#            Bash's mintty — under Git Bash, since the command is POSIX.
#   Linux    $TERMINAL, then ghostty / wezterm / kitty / gnome-terminal /
#            konsole / alacritty / xterm — under bash.
#
# Exit: 0 opened a window, 1 could not (no emulator, remote/CI session, bad args).
#
# **The caller decides what a failure means**, which is why this reports rather
# than degrades: open-diff-review.sh treated "no window" as harmless and printed a
# diffstat, while start-parallel-cycles.sh must know, because a cycle that never
# launched is not a cycle. A helper that swallowed the difference would be wrong
# for one of them.

set -uo pipefail

CWD="" TITLE="" CMD="" TAB=0
while [ $# -gt 0 ]; do
  case "$1" in
    --tab)   TAB=1; shift ;;
    --cwd)   CWD="${2:-}"; shift 2 ;;
    --title) TITLE="${2:-}"; shift 2 ;;
    --)      shift; CMD="$*"; break ;;
    # Print the whole leading comment block rather than a hardcoded line range:
    # the range said 2,20 while the header grew to 36, so `--help` stopped
    # mid-sentence and hid the platform table it exists to show.
    -h|--help) sed -n '2,/^[^#]/p' "$0" | sed '$d'; exit 0 ;;
    *) echo "open-terminal: unknown arg '$1'" >&2; exit 1 ;;
  esac
done

[ -n "$CMD" ] || { echo "open-terminal: no command given (use -- <command>)" >&2; exit 1; }
[ -n "$CWD" ] || CWD="$PWD"
[ -d "$CWD" ] || { echo "open-terminal: no such directory: $CWD" >&2; exit 1; }
[ -n "$TITLE" ] || TITLE="terminal"

# Headless and remote contexts have no window server to open into. Not an error
# in itself — the caller is told, and decides.
[ -z "${SSH_CONNECTION:-}${SSH_TTY:-}" ] || { echo "open-terminal: remote session" >&2; exit 1; }
[ -z "${CI:-}" ] || { echo "open-terminal: CI environment" >&2; exit 1; }

INNER="cd $(printf "'%s'" "$(printf '%s' "$CWD" | sed "s/'/'\\\\''/g")") && $CMD"

launch() { "$@" >/dev/null 2>&1 & disown 2>/dev/null; return 0; }

# ---------------------------------------------------------------- platform ----
# `uname -s` under Git Bash and MSYS2 reports MINGW64_NT-10.0, under Cygwin
# CYGWIN_NT-10.0. Neither is Darwin, so before this both fell through to the
# Linux branch, searched for gnome-terminal and friends, found none, and exited 1
# — Windows was not unsupported so much as unconsidered.
case "$(uname -s)" in
  Darwin)                  PLATFORM=mac ;;
  MINGW*|MSYS*|CYGWIN*)    PLATFORM=windows ;;
  *) [ "${OS:-}" = "Windows_NT" ] && PLATFORM=windows || PLATFORM=linux ;;
esac

# The shell that runs the command, per platform.
#
# macOS has defaulted to zsh since Catalina, so `bash -lc` sources login files
# most macOS users stopped maintaining years ago — a different PATH, and none of
# the shell setup the operator actually runs the pipeline under. zsh is the
# correct default here; bash remains the fallback for a machine without it.
#
# `$INNER` is POSIX (`cd 'dir' && cmd`) and runs identically in both, so this
# changes which login files load and nothing else.
#
# The probe path is overridable, like GHOSTTY_APP below: the zsh branch is
# otherwise untestable on a host without /bin/zsh (Linux CI, Windows).
mac_shell() { [ -x "${OPEN_TERMINAL_ZSH:-/bin/zsh}" ] && printf 'zsh' || printf 'bash'; }

# Where Ghostty is installed. An absolute path baked into a conditional cannot be
# driven from a test: on a developer machine that has Ghostty, the no-Ghostty
# fallback is unreachable, which is exactly the branch the macOS default-shell
# behaviour lives in. Overridable so that branch is testable; nobody needs to set
# it in normal use.
GHOSTTY_APP="${OPEN_TERMINAL_GHOSTTY_APP:-/Applications/Ghostty.app}"

# Terminal.app and iTerm cannot take a command as argv from the CLI. Hand them a
# self-deleting launcher script instead.
make_launcher() {
  local f sh
  sh="${1:-bash}"
  # Portable template: `mktemp -t NAME` is BSD-only. This script is macOS-only
  # today, so the BSD form worked — but it is the same latent bug that made
  # deploy.sh's --apply a silent no-op on Linux CI, so it does not stay.
  f="$(mktemp "${TMPDIR:-/tmp}/open-terminal.XXXXXX")" || return 1
  printf '#!/bin/%s\nrm -f -- "$0"\n%s\n' "$sh" "$INNER" > "$f"
  chmod +x "$f"
  printf '%s' "$f"
}

# osascript with a wall-clock bound. An unanswered macOS consent dialog otherwise
# blocks forever, and a launcher that hangs is worse than one that opens a window.
osa_timeout() {
  local secs="$1"; shift
  osascript -e "$1" 2>/dev/null &
  local pid=$!
  ( sleep "$secs"; kill "$pid" 2>/dev/null ) >/dev/null 2>&1 &
  local killer=$!
  wait "$pid" 2>/dev/null
  local rc=$?
  kill "$killer" 2>/dev/null
  return $rc
}

# Escape a string for embedding in an AppleScript double-quoted literal.
osa_str() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }

# A tab in Ghostty's front window. Returns 1 if Ghostty is not running, has no
# window to add to, or the AppleScript interface is unavailable — the caller then
# falls through to opening a window.
ghostty_tab() {
  command -v osascript >/dev/null 2>&1 || return 1
  # pgrep, not System Events: querying System Events needs its own macOS
  # automation grant and blocks on the consent dialog when it has not been given.
  # Measured — it stalled this script for two minutes on first run.
  pgrep -x Ghostty >/dev/null 2>&1 || return 1
  # `count windows` also drives the consent prompt for Ghostty itself, but that
  # grant is needed for the tab anyway, so it is not an extra one. Bound it so a
  # never-answered dialog degrades to a window instead of hanging the launcher.
  local n
  n="$(osa_timeout 5 'tell application "Ghostty" to count windows')" || return 1
  [ "${n:-0}" -gt 0 ] 2>/dev/null || return 1
  # Run the command from a launcher file rather than inlining it: the command
  # string would otherwise need to survive shell quoting, AppleScript quoting and
  # Ghostty's own parsing at once.
  local L
  L="$(make_launcher)" || return 1
  osa_timeout 10 "tell application \"Ghostty\" to new tab in front window with configuration \
    {command:\"$(osa_str "$L")\", initial working directory:\"$(osa_str "$CWD")\", \
     wait after command:true}" >/dev/null || return 1
  return 0
}

if [ "$PLATFORM" = mac ]; then
  SH="$(mac_shell)"
  if [ "$TAB" = 1 ] && ghostty_tab; then
    exit 0
  fi
  case "${TERM_PROGRAM:-}" in
    ghostty)
      launch open -na Ghostty --args --working-directory="$CWD" --title="$TITLE" -e "$SH" -lc "$INNER" ;;
    iTerm.app)
      L="$(make_launcher "$SH")" || { echo "open-terminal: mktemp failed" >&2; exit 1; }
      launch open -a iTerm "$L" ;;
    WezTerm)
      launch wezterm start --cwd "$CWD" -- "$SH" -lc "$INNER" ;;
    *)
      if [ -n "${KITTY_WINDOW_ID:-}" ] && command -v kitty >/dev/null 2>&1; then
        launch kitty --directory "$CWD" --title "$TITLE" "$SH" -lc "$INNER"
      elif [ -d "$GHOSTTY_APP" ]; then
        launch open -na Ghostty --args --working-directory="$CWD" --title="$TITLE" -e "$SH" -lc "$INNER"
      else
        # No Ghostty: Terminal.app, running the command under the operator's
        # actual default shell rather than bash.
        L="$(make_launcher "$SH")" || { echo "open-terminal: mktemp failed" >&2; exit 1; }
        launch open -a Terminal "$L"
      fi ;;
  esac
elif [ "$PLATFORM" = windows ]; then
  # Ghostty first, as everywhere else — it has no Windows build today, so in
  # practice this branch is the fallback the operator asked for, but the order
  # is what matters and it should not have to change when that ships.
  if command -v ghostty >/dev/null 2>&1; then
    launch ghostty --working-directory="$CWD" --title="$TITLE" -e bash -lc "$INNER"
    exit 0
  fi

  # Git Bash, as on every other platform — not PowerShell. The previous branch
  # ran `Set-Location …; <command>` in PowerShell, but the launcher's command is
  # POSIX (`cd /c/… && claude "/cycle N"`): `&&` is a syntax error in Windows
  # PowerShell 5.1, and in 7 the `/c/…` cd fails first, so every window opened
  # and no cycle ever started. Running `$INNER` in the same POSIX shell the
  # pipeline already requires means one command string means one thing.
  #
  # Git's bin\bash.exe, not usr\bin\bash.exe: the bin\ wrapper sets MSYSTEM so
  # the login profile puts git itself on PATH; the bare usr\bin one does not.
  WINCWD="$(cygpath -w "$CWD" 2>/dev/null || printf '%s' "$CWD")"
  GITBASH="${OPEN_TERMINAL_GITBASH:-}"
  if [ -z "$GITBASH" ]; then
    groot="$(cygpath -w / 2>/dev/null)"
    if [ -n "$groot" ] && [ -f "$(cygpath -u "$groot")/bin/bash.exe" ]; then
      GITBASH="${groot%\\}\\bin\\bash.exe"
    else
      GITBASH="$(cygpath -w "$(command -v bash)" 2>/dev/null)"
    fi
  fi
  [ -n "$GITBASH" ] || { echo "open-terminal: no Git Bash found" >&2; exit 1; }
  # Overridable for the same reason as GHOSTTY_APP: a test host has a real
  # mintty in /usr/bin, and the no-Windows-Terminal branch would open it.
  MINTTY="${OPEN_TERMINAL_MINTTY:-$(command -v mintty 2>/dev/null)}"

  # The command goes in a launcher file, as for Terminal.app, and the terminal
  # is handed only its path. Measured: wt.exe re-parses its own command line,
  # so an `-lc "$INNER"` survived only while $INNER had no double quotes — and
  # the launcher's is `claude "/cycle N"` — and wt treats `;` as its own
  # separator. A path carries neither.
  L="$(make_launcher bash)" || { echo "open-terminal: mktemp failed" >&2; exit 1; }
  if command -v wt.exe >/dev/null 2>&1; then
    # Windows Terminal: the only one here that can do a tab. MSYS rewrites any
    # argument that looks like a POSIX path when it starts a native program;
    # conversion is off for this call and every path is given Windows-form.
    LW="$(cygpath -m "$L" 2>/dev/null || printf '%s' "$L")"
    if [ "$TAB" = 1 ]; then
      MSYS2_ARG_CONV_EXCL='*' launch wt.exe -w 0 nt -d "$WINCWD" --title "$TITLE" "$GITBASH" -l "$LW"
    else
      MSYS2_ARG_CONV_EXCL='*' launch wt.exe -d "$WINCWD" --title "$TITLE" "$GITBASH" -l "$LW"
    fi
  elif [ -n "$MINTTY" ] && [ -x "$MINTTY" ]; then
    # mintty is Git Bash's own terminal and an MSYS program, so no conversion.
    launch "$MINTTY" -t "$TITLE" --dir "$CWD" /usr/bin/bash -l "$L"
  else
    echo "open-terminal: no terminal found (Windows Terminal wt.exe, or Git Bash's mintty)" >&2
    exit 1
  fi
else
  for t in "${TERMINAL:-}" ghostty wezterm kitty gnome-terminal konsole alacritty xterm; do
    [ -n "$t" ] && command -v "$t" >/dev/null 2>&1 || continue
    case "$t" in
      wezterm)        launch wezterm start --cwd "$CWD" -- bash -lc "$INNER" ;;
      kitty)          launch kitty --directory "$CWD" --title "$TITLE" bash -lc "$INNER" ;;
      gnome-terminal) launch gnome-terminal --working-directory="$CWD" --title="$TITLE" -- bash -lc "$INNER" ;;
      konsole)        launch konsole --workdir "$CWD" -e bash -lc "$INNER" ;;
      *)              launch "$t" -e bash -lc "$INNER" ;;
    esac
    FOUND=1; break
  done
  [ "${FOUND:-0}" = 1 ] || { echo "open-terminal: no supported terminal emulator found" >&2; exit 1; }
fi

exit 0
