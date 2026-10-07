#!/usr/bin/env bash
# test_open_terminal.sh — platform dispatch and the shell each platform uses.
#
# open-terminal.sh had no test. It also had no Windows branch: `uname -s` reports
# MINGW64_NT-10.0 under Git Bash, which is not Darwin, so Windows fell into the
# Linux emulator loop, found no gnome-terminal, and exited 1. And the macOS
# fallback ran the command under `bash -lc` on a platform whose default login
# shell has been zsh since Catalina.
#
# Everything here is driven through stubs on PATH — a fake `uname`, fake
# PowerShell, fake `wt.exe`, fake `open` — each of which records its argv. The
# assertions read those recordings, so they check what would actually be
# launched rather than that the script exited 0.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
S="$ROOT_DIR/.claude/skills/cycle/open-terminal.sh"
FAILED=0
ok()  { printf 'ok    %s\n' "$1"; }
bad() { printf 'FAIL  %s\n     %s\n' "$1" "$2"; FAILED=1; }
chk() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "want [$3] got [$2]"; fi; }
has() { if printf '%s' "$2" | grep -qF -- "$3"; then ok "$1"; else bad "$1" "missing [$3] in: $2"; fi; }
hasnt() { if printf '%s' "$2" | grep -qF -- "$3"; then bad "$1" "unexpected [$3] in: $2"; else ok "$1"; fi; }

R="$(mktemp -d)"
BIN="$R/bin"; REC="$R/rec"; mkdir -p "$BIN" "$REC"
WORK="$R/work"; mkdir -p "$WORK"

# A stub records its own name and argv, one line, and exits 0.
mkstub() {
  cat > "$BIN/$1" <<STUB
#!/usr/bin/env bash
printf '%s %s\n' "\$(basename "\$0")" "\$*" >> "$REC/calls"
exit 0
STUB
  chmod +x "$BIN/$1"
}

# uname is stubbed per-case by rewriting it; everything else is fixed.
set_uname() {
  cat > "$BIN/uname" <<STUB
#!/usr/bin/env bash
[ "\${1:-}" = "-s" ] && printf '%s\n' '$1' || printf '%s\n' '$1'
STUB
  chmod +x "$BIN/uname"
}

for s in open osascript pgrep wezterm kitty; do mkstub "$s"; done
# A hermetic PATH, not `$BIN:$PATH`. The first cut appended the host's PATH and
# the developer machine's real `ghostty` satisfied the Windows branch's
# ghostty-first check, so every Windows assertion saw an empty recording and the
# suite tested the host instead of the script. Only the system directories, so
# mktemp/sed/grep still resolve.
export PATH="$BIN:/usr/bin:/bin:/usr/sbin:/sbin"
# A clean environment: no emulator hints, no remote/CI short-circuit.
unset TERM_PROGRAM KITTY_WINDOW_ID SSH_CONNECTION SSH_TTY CI TERMINAL 2>/dev/null || true

# `launch` backgrounds with `& disown`, so the script exits before the stub has
# necessarily written. Wait for the recording to appear rather than reading it
# immediately — the first cut read an empty file every time and reported a
# missing dispatch that had in fact happened.
run() {
  : > "$REC/calls"
  bash "$S" "$@" >/dev/null 2>&1
  local i=0
  while [ ! -s "$REC/calls" ] && [ "$i" -lt 50 ]; do sleep 0.05; i=$((i+1)); done
  printf '%s' "$(cat "$REC/calls" 2>/dev/null)"
}

# ------------------------------------------------------------------ windows ----
#
# The case the script could not express at all before.
set_uname 'MINGW64_NT-10.0'
mkstub 'powershell.exe'
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "Windows dispatches to PowerShell, not an X11 emulator" "$out" "powershell.exe"
has  "  ... with -NoExit, so the window survives the command" "$out" "-NoExit"
has  "  ... and Set-Location, since POSIX cd && cmd is a 5.1 syntax error" "$out" "Set-Location"
hasnt "  ... and never hands the POSIX string to a shell" "$out" "bash -lc"

mkstub 'pwsh.exe'
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "pwsh is preferred over the bundled powershell.exe" "$out" "pwsh.exe"

mkstub 'wt.exe'
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "Windows Terminal is used when present" "$out" "wt.exe"
hasnt "  ... and without --tab it opens a window, not a tab" "$out" " nt "
out="$(run --tab --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "  ... while --tab asks Windows Terminal for a tab" "$out" " nt "

rm -f "$BIN/wt.exe"
mkstub 'cmd.exe'
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "without Windows Terminal, a new window comes from cmd start" "$out" "cmd.exe /c start"
# `start` takes its first quoted argument as the window title, so the empty ""
# is load-bearing: without it the shell is swallowed and nothing launches.
has  "  ... keeping start's empty title argument" "$out" 'start  pwsh.exe'

rm -f "$BIN/pwsh.exe" "$BIN/powershell.exe"
bash "$S" --cwd "$WORK" -- 'x' >/dev/null 2>"$R/err"; rc=$?
chk "no PowerShell at all refuses rather than silently doing nothing" "$rc" 1
has  "  ... naming what it looked for" "$(cat "$R/err")" "pwsh.exe or powershell.exe"

# -------------------------------------------------------------------- macos ----
#
# No Ghostty: the fallback must run the command under zsh.
set_uname 'Darwin'
# Point the Ghostty check at a path that does not exist. On a machine that has
# Ghostty installed, the no-Ghostty fallback — the branch the zsh default lives
# in — is otherwise unreachable, and this assertion silently tested the
# developer's own install instead.
export OPEN_TERMINAL_GHOSTTY_APP="$R/no-such-Ghostty.app"
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "macOS with no Ghostty falls back to Terminal.app" "$out" "open -a Terminal"
# The launcher is a temp file; read the one the stub was handed.
LP="$(printf '%s' "$out" | sed -n 's/^open -a Terminal //p')"
if [ -n "$LP" ] && [ -r "$LP" ]; then
  has "  ... and the launcher runs zsh, not bash" "$(head -1 "$LP")" "/bin/zsh"
  rm -f "$LP"
else
  bad "  ... and the launcher runs zsh, not bash" "launcher not found: [$LP]"
fi

# WezTerm takes the command as argv, so the shell is visible directly.
export TERM_PROGRAM=WezTerm
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "macOS WezTerm runs the command under zsh" "$out" "zsh -lc"
hasnt "  ... not bash" "$out" "bash -lc"
unset TERM_PROGRAM

# -------------------------------------------------------------------- linux ----
#
# Unchanged: bash is correct here, and a platform with no emulator still fails.
set_uname 'Linux'
export TERMINAL=wezterm
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "Linux still runs the command under bash" "$out" "bash -lc"
unset TERMINAL

printf '\nopen-terminal: %s\n' \
  "$([ $FAILED = 0 ] && echo 'all checks passed.' || echo 'FAILURES above.')"
exit $FAILED
