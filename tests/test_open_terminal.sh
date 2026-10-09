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
# Windows sets OS=Windows_NT for every process, and the script's fallback
# detection reads it — so on a Windows host the stubbed-Linux case ran the
# Windows branch instead.
unset OS 2>/dev/null || true

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
# Pinned, so the assertions do not depend on where this host keeps Git; and the
# host's real mintty is pointed away from, or the no-wt case opens a window.
export OPEN_TERMINAL_GITBASH='C:\Git\bin\bash.exe'
export OPEN_TERMINAL_MINTTY="$R/no-such-mintty"
# The previous branch ran the command in PowerShell. The launcher's command is
# POSIX — `cd … && claude "/cycle N"` — so `&&` failed to parse in 5.1 and the
# MSYS-form cd failed in 7: every window opened and no cycle started.
# wt.exe records MSYS2_ARG_CONV_EXCL too: without it MSYS rewrites the
# arguments it passes to a native program.
cat > "$BIN/wt.exe" <<STUB
#!/usr/bin/env bash
printf 'wt.exe %s CONV=%s\n' "\$*" "\${MSYS2_ARG_CONV_EXCL:-}" >> "$REC/calls"
STUB
chmod +x "$BIN/wt.exe"
for s in powershell.exe pwsh.exe; do mkstub "$s"; done
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "Windows Terminal is used when present" "$out" "wt.exe"
has  "  ... running Git Bash, not PowerShell" "$out" 'C:\Git\bin\bash.exe -l '
hasnt "  ... never PowerShell" "$out" "powershell"
hasnt "  ... nor pwsh" "$out" "pwsh"
has  "  ... with MSYS path conversion off for the call" "$out" "CONV=*"
# wt.exe re-parses its own command line: quotes inside an -lc string did not
# survive it (measured), and `;` is its separator. Only a file path is passed.
hasnt "  ... handing it a file, never the command string" "$out" "/cycle 184"
LW="$(printf '%s' "$out" | sed -n 's/.* -l \([^ ]*\) CONV=.*/\1/p')"
L="$(cygpath -u "$LW" 2>/dev/null || printf '%s' "$LW")"
has  "  ... whose file holds the command, quotes intact" "$(cat "$L" 2>/dev/null)" 'claude "/cycle 184"'
rm -f "$L"
hasnt "  ... and without --tab it opens a window, not a tab" "$out" " nt "
out="$(run --tab --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "  ... while --tab asks Windows Terminal for a tab" "$out" " nt "
rm -f "$(cygpath -u "$(printf '%s' "$out" | sed -n 's/.* -l \([^ ]*\) CONV=.*/\1/p')" 2>/dev/null)"

rm -f "$BIN/wt.exe"
mkstub 'mintty'; export OPEN_TERMINAL_MINTTY="$BIN/mintty"
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "without Windows Terminal, Git Bash's own mintty opens the window" "$out" "mintty -t T --dir"
has  "  ... running the launcher under bash" "$out" "/usr/bin/bash -l "

export OPEN_TERMINAL_MINTTY="$R/no-such-mintty"
bash "$S" --cwd "$WORK" -- 'x' >/dev/null 2>"$R/err"; rc=$?
chk "no terminal at all refuses rather than silently doing nothing" "$rc" 1
has  "  ... naming what it looked for" "$(cat "$R/err")" "wt.exe, or Git Bash's mintty"
unset OPEN_TERMINAL_GITBASH OPEN_TERMINAL_MINTTY

# -------------------------------------------------------------------- macos ----
#
# No Ghostty: the fallback must run the command under zsh.
set_uname 'Darwin'
# Point the Ghostty check at a path that does not exist. On a machine that has
# Ghostty installed, the no-Ghostty fallback — the branch the zsh default lives
# in — is otherwise unreachable, and this assertion silently tested the
# developer's own install instead.
export OPEN_TERMINAL_GHOSTTY_APP="$R/no-such-Ghostty.app"
# And a zsh that exists, since the host may have none at /bin/zsh (Linux CI,
# Windows) — the case is "a Mac", not "this machine".
mkstub zsh; export OPEN_TERMINAL_ZSH="$BIN/zsh"
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
