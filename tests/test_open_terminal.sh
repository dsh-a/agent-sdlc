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

# The root has a space, as a Windows profile path can, so every path below does.
R0="$(mktemp -d)"; R="$R0/with space"; mkdir -p "$R"
trap 'rm -rf "$R0"' EXIT
BIN="$R/bin"; REC="$R/rec"; mkdir -p "$BIN" "$REC"
WORK="$R/work"; mkdir -p "$WORK"
# The script's launchers land in a private TMPDIR whose path has a space, as a
# Windows profile path can, so every case runs against one.
export TMPDIR="$R/tmp dir"; mkdir -p "$TMPDIR"
launchers_left() { find "$TMPDIR" -name 'open-terminal.*' | wc -l | tr -d ' '; }

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
#
# Link the system tools into one directory and take out the programs this suite
# is about, so the only copies on PATH are the stubs. A host may ship its own:
# GitHub's Ubuntu image has `/usr/bin/pwsh`.
SYS="$R/sys"; mkdir -p "$SYS"
for d in /sbin /usr/sbin /bin /usr/bin; do
  ln -sf "$d"/* "$SYS"/ 2>/dev/null || true
done
for x in pwsh pwsh.exe powershell powershell.exe wt.exe cmd.exe cygpath osascript open \
         ghostty wezterm kitty gnome-terminal konsole alacritty xterm uname pgrep; do
  rm -f "$SYS/$x"
done
export PATH="$BIN:$SYS"
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
  : > "$REC/calls"; : > "$REC/launcher"
  bash "$S" "$@" >/dev/null 2>&1
  local i=0
  while [ ! -s "$REC/calls" ] && [ "$i" -lt 50 ]; do sleep 0.05; i=$((i+1)); done
  printf '%s' "$(cat "$REC/calls" 2>/dev/null)"
}

# The stubs never run the launcher, so its self-delete never fires; the suite
# removes each one it is handed.
launcher() { local f; f="$(cat "$REC/launcher")"; cygpath -u "$f" 2>/dev/null || printf '%s' "$f"; }
drop_launcher() { rm -f -- "$(launcher)"; }

# ------------------------------------------------------------------ windows ----
#
# Git Bash's `uname -s`: the command runs under Git Bash in Windows Terminal or
# mintty.
set_uname 'MINGW64_NT-10.0'
# A stand-in `cygpath`. `-w /` names a Git root at $GR. Windows forms put $R at
# C:/R, so `-m` keeps the space in "tmp dir" and `-ms` gives its 8.3 name
# TMPDIR~1 unless $R/no-short-names exists; `-u` maps both back.
GR="$R/Program Files/Git"; mkdir -p "$GR/bin"
CYG="$R/cyg"; mkdir -p "$CYG"
cat > "$CYG/cygpath" <<STUB
#!/usr/bin/env bash
R='$R'; GR='$GR'; p="\$2"
case "\$1 \$p" in
  "-w /") printf '%s\n' 'C:\Program Files\Git\'; exit 0 ;;
  '-u C:\Program Files\Git\') printf '%s\n' "\$GR"; exit 0 ;;
esac
case "\$1" in
  -m|-ms)
    case "\$p" in "\$R"*) p="C:/R\${p#"\$R"}" ;; esac
    [ "\$1" = -ms ] && [ ! -e "\$R/no-short-names" ] && p="\${p//tmp dir/TMPDIR~1}" ;;
  -u)
    p="\${p//\\\\//}"
    case "\$p" in C:/R*) p="\$R\${p#C:/R}" ;; esac
    p="\${p//TMPDIR~1/tmp dir}" ;;
esac
printf '%s\n' "\$p"
STUB
chmod +x "$CYG/cygpath"
export PATH="$CYG:$BIN:$SYS"
unset LOCALAPPDATA OPEN_TERMINAL_LAUNCHER_DIR 2>/dev/null || true
# Pinned, so the assertions do not depend on where this host keeps Git; and the
# host's real mintty is pointed away from, or the no-wt case opens a window.
export OPEN_TERMINAL_GITBASH='C:\Git\bin\bash.exe'
export OPEN_TERMINAL_MINTTY="$R/no-such-mintty"
# The launcher's command is POSIX — `cd … && claude "/cycle N"` — which
# PowerShell cannot run, so it runs under Git Bash. wt.exe records MSYS2_ARG_CONV_EXCL too: without it MSYS rewrites the
# arguments it passes to a native program.
cat > "$BIN/wt.exe" <<STUB
#!/usr/bin/env bash
printf '%s' "\${@: -1}" > "$REC/launcher"
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
# wt.exe re-parses its command line (quotes and `;` are significant), so it
# gets a file path, never the command.
hasnt "  ... handing it a file, never the command string" "$out" "/cycle 184"
has  "  ... whose file holds the command, quotes intact" "$(cat "$(launcher)" 2>/dev/null)" 'claude "/cycle 184"'
# wt.exe re-tokenises its command line, so the path it gets has no space.
has  "  ... given by its 8.3 form when TMPDIR has a space" "$(cat "$REC/launcher")" "C:/R/TMPDIR~1/open-terminal."
drop_launcher
hasnt "  ... and without --tab it opens a window, not a tab" "$out" " nt "
out="$(run --tab --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "  ... while --tab asks Windows Terminal for a tab" "$out" " nt "
drop_launcher

# No 8.3 names: the launcher goes to a directory whose Windows form has no space.
: > "$R/no-short-names"
mkdir -p "$R/launchers" "$R/appdata"
OPEN_TERMINAL_LAUNCHER_DIR="$R/launchers" run --cwd "$WORK" --title T -- 'x' >/dev/null
has  "with no 8.3 names, wt gets a launcher in OPEN_TERMINAL_LAUNCHER_DIR" "$(cat "$REC/launcher")" "C:/R/launchers/open-terminal."
has  "  ... which holds the command" "$(cat "$(launcher)" 2>/dev/null)" 'x'
drop_launcher
LOCALAPPDATA='C:\R\appdata' run --cwd "$WORK" --title T -- 'x' >/dev/null
has  "  ... else in LOCALAPPDATA" "$(cat "$REC/launcher")" "C:/R/appdata/open-terminal."
drop_launcher
bash "$S" --cwd "$WORK" -- 'x' >/dev/null 2>"$R/err"; rc=$?
chk  "  ... and with neither, it refuses" "$rc" 1
has  "  ... naming the setting that fixes it" "$(cat "$R/err")" "OPEN_TERMINAL_LAUNCHER_DIR"
chk  "  ... and leaves no launcher file behind" "$(launchers_left)" 0
rm -f "$R/no-short-names"

rm -f "$BIN/wt.exe"
cat > "$BIN/mintty" <<STUB
#!/usr/bin/env bash
printf '%s' "\${@: -1}" > "$REC/launcher"
printf 'mintty %s\n' "\$*" >> "$REC/calls"
STUB
chmod +x "$BIN/mintty"; export OPEN_TERMINAL_MINTTY="$BIN/mintty"
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "without Windows Terminal, Git Bash's own mintty opens the window" "$out" "mintty -t T --dir"
has  "  ... running the launcher under bash" "$out" "/usr/bin/bash -l "
has  "  ... whose file holds the command" "$(cat "$(launcher)" 2>/dev/null)" 'claude "/cycle 184"'
drop_launcher

export OPEN_TERMINAL_MINTTY="$R/no-such-mintty"
bash "$S" --cwd "$WORK" -- 'x' >/dev/null 2>"$R/err"; rc=$?
chk "no terminal at all refuses rather than silently doing nothing" "$rc" 1
has  "  ... naming what it looked for" "$(cat "$R/err")" "wt.exe, or Git Bash's mintty"
chk  "  ... and leaves no launcher file behind" "$(launchers_left)" 0

# --- Git Bash discovery, with no OPEN_TERMINAL_GITBASH ---------------------------
# The window runs Git's bin\bash.exe in the Git root `cygpath -w /` names.
unset OPEN_TERMINAL_GITBASH
cat > "$BIN/wt.exe" <<STUB
#!/usr/bin/env bash
printf '%s' "\${@: -1}" > "$REC/launcher"
printf 'wt.exe %s CONV=%s\n' "\$*" "\${MSYS2_ARG_CONV_EXCL:-}" >> "$REC/calls"
STUB
chmod +x "$BIN/wt.exe"

: > "$GR/bin/bash.exe"
out="$(run --cwd "$WORK" --title T -- 'x')"
has  "Git Bash is bin\\bash.exe in the Git root cygpath names" "$out" \
     'C:\Program Files\Git\bin\bash.exe -l '
drop_launcher
rm -f "$GR/bin/bash.exe"
out="$(run --cwd "$WORK" --title T -- 'x')"
has  "  ... and the bash on PATH when that root has none" "$out" "$SYS/bash -l "
drop_launcher

export PATH="$BIN:$SYS"
bash "$S" --cwd "$WORK" -- 'x' >/dev/null 2>"$R/err"; rc=$?
chk "with no cygpath to ask, no Git Bash is found and nothing opens" "$rc" 1
has  "  ... naming where it looked" "$(cat "$R/err")" \
     'looked at OPEN_TERMINAL_GITBASH, bin\bash.exe under `cygpath -w /`, and bash on PATH'
chk  "  ... and leaves no launcher file behind" "$(launchers_left)" 0
rm -f "$BIN/wt.exe"
export OPEN_TERMINAL_MINTTY="$BIN/mintty"
out="$(run --cwd "$WORK" --title T -- 'x')"
has  "mintty opens without a Git Bash path, since it runs /usr/bin/bash" "$out" "mintty -t T --dir"
drop_launcher
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
MAC_SH=zsh
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "macOS with no Ghostty falls back to Terminal.app" "$out" "open -a Terminal"
# The launcher is a temp file; read the one the stub was handed.
LP="$(printf '%s' "$out" | sed -n 's/^open -a Terminal //p')"
if [ -n "$LP" ] && [ -r "$LP" ]; then
  has "  ... and the launcher runs zsh, not bash" "$(head -1 "$LP")" "/bin/$MAC_SH"
  rm -f "$LP"
else
  bad "  ... and the launcher runs zsh, not bash" "launcher not found: [$LP]"
fi

# WezTerm takes the command as argv, so the shell is visible directly.
export TERM_PROGRAM=WezTerm
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "macOS WezTerm runs the command under zsh" "$out" "$MAC_SH -lc"
[ "$MAC_SH" = zsh ] && hasnt "  ... not bash" "$out" "bash -lc"
unset TERM_PROGRAM

# -------------------------------------------------------------------- linux ----
#
# bash is correct here, and a platform with no emulator fails.
set_uname 'Linux'
export TERMINAL=wezterm
out="$(run --cwd "$WORK" --title T -- 'claude "/cycle 184"')"
has  "Linux still runs the command under bash" "$out" "bash -lc"
unset TERMINAL

chk "the suite leaves no launcher file behind" "$(launchers_left)" 0

printf '\nopen-terminal: %s\n' \
  "$([ $FAILED = 0 ] && echo 'all checks passed.' || echo 'FAILURES above.')"
exit $FAILED
